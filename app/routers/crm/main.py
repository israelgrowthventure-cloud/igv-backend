"""
CRM Unified Router - Phase 2
Consolidated from: crm_routes.py, crm_complete_routes.py, crm_missing_routes.py, crm_additional_routes.py
ALL CRM routes centralized in app/routers/crm/
CRITICAL: URLs and JSON response formats unchanged for frontend compatibility
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging

# Import centralized auth middleware
from auth_middleware import (
    get_current_user,
    get_user_or_admin,
    require_admin,
    require_role,
    get_user_assigned_filter,
    get_user_write_permission,
    log_audit_event,
    get_db
)

router = APIRouter(prefix="/api/crm")


# ==========================================
# PYDANTIC MODELS (unified from all CRM files)
# ==========================================

class LeadCreate(BaseModel):
    email: EmailStr
    brand_name: str
    name: Optional[str] = None
    phone: Optional[str] = None
    sector: Optional[str] = None
    language: str = "fr"
    expansion_type: Optional[str] = None
    format: Optional[str] = None
    budget_estimated: Optional[float] = None
    target_city: Optional[str] = None
    timeline: Optional[str] = None
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class LeadFromPackRequest(BaseModel):
    """Demande de rappel depuis page Packs"""
    email: EmailStr
    full_name: str
    phone: str
    company: Optional[str] = None
    pack_requested: str
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    message: Optional[str] = None
    source: str = "pack_rappel"
    status: str = "new"


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    stage: Optional[str] = None
    priority: Optional[str] = None
    owner_email: Optional[str] = None
    tags: Optional[List[str]] = None
    expansion_type: Optional[str] = None
    sector: Optional[str] = None
    format: Optional[str] = None
    budget_estimated: Optional[float] = None
    target_city: Optional[str] = None
    timeline: Optional[str] = None
    focus_notes: Optional[str] = None


class NoteCreate(BaseModel):
    content: Optional[str] = None
    note_text: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    @property
    def text(self) -> str:
        return self.content or self.note_text or ""


class OpportunityCreate(BaseModel):
    name: str
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    value: Optional[float] = None
    stage: str = "qualification"
    probability: int = 50
    expected_close_date: Optional[datetime] = None


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    value: Optional[float] = None
    probability: Optional[int] = None
    owner_email: Optional[str] = None
    next_step: Optional[str] = None
    next_action_date: Optional[datetime] = None


class ContactCreate(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None
    position: Optional[str] = None
    language: str = "fr"


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "viewer"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class EmailDraftCreate(BaseModel):
    to_email: Optional[str] = None
    subject: str = ""
    message: str = ""
    body: str = ""
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None


class EmailDraftUpdate(BaseModel):
    to_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    body: Optional[str] = None


# ==========================================
# HELPER FUNCTIONS
# ==========================================

async def create_lead_in_crm(lead_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    Create lead automatically with MongoDB fallback if CRM unavailable
    From crm_routes.py MISSION C
    """
    current_db = get_db()
    
    if current_db is None:
        logging.error(f"[{request_id}] LEAD_CRM_FAIL_NO_DB: MongoDB not configured")
        return {"status": "error", "error": "Database not configured"}
    
    try:
        # Check for duplicate (same email + brand in last 24h)
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        
        existing_lead = await current_db.leads.find_one({
            "email": lead_data["email"],
            "brand_name": lead_data["brand_name"],
            "created_at": {"$gte": twenty_four_hours_ago}
        })
        
        if existing_lead:
            await current_db.leads.update_one(
                {"_id": existing_lead["_id"]},
                {
                    "$set": {
                        "status": lead_data.get("status", "NEW"),
                        "updated_at": datetime.now(timezone.utc),
                        "last_request_id": request_id
                    },
                    "$inc": {"request_count": 1}
                }
            )
            logging.info(f"[{request_id}] LEAD_CRM_OK_UPDATED: lead_id={existing_lead['_id']}")
            return {"status": "updated", "lead_id": str(existing_lead["_id"])}
        
        # Create new lead
        lead_record = {
            **lead_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "request_count": 1,
            "last_request_id": request_id
        }
        
        result = await current_db.leads.insert_one(lead_record)
        logging.info(f"[{request_id}] LEAD_CRM_OK: lead_id={result.inserted_id}")
        
        return {"status": "created", "lead_id": str(result.inserted_id)}
        
    except Exception as e:
        logging.error(f"[{request_id}] LEAD_CRM_FAIL_FALLBACK_MONGO: {str(e)}")
        
        try:
            minimal_lead = {
                "email": lead_data.get("email"),
                "brand_name": lead_data.get("brand_name"),
                "status": "ERROR",
                "error": str(e),
                "created_at": datetime.now(timezone.utc)
            }
            result = await current_db.leads_fallback.insert_one(minimal_lead)
            logging.warning(f"[{request_id}] LEAD_FALLBACK_OK: lead_id={result.inserted_id}")
            return {"status": "fallback", "lead_id": str(result.inserted_id)}
        except Exception as fallback_error:
            logging.error(f"[{request_id}] LEAD_FALLBACK_FAIL: {str(fallback_error)}")
            return {"status": "error", "error": str(fallback_error)}


# ==========================================
# DASHBOARD
# ==========================================

@router.get("/dashboard/stats")
async def get_dashboard_stats(user: Dict = Depends(get_current_user)):
    """Get CRM dashboard statistics (production endpoint from crm_complete_routes)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get user filter (RBAC: commercial sees only their leads)
        user_filter = get_user_assigned_filter(user)
        
        # Total leads
        total_leads = await current_db.leads.count_documents(user_filter)
        
        # Leads by status
        pipeline = [
            {"$match": user_filter},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        leads_by_status = {doc["_id"]: doc["count"] async for doc in current_db.leads.aggregate(pipeline)}
        
        # Total opportunities
        total_opportunities = await current_db.opportunities.count_documents(user_filter if user["role"] != "admin" else {})
        
        # Pipeline value (sum of all opportunity values)
        pipeline_value_agg = [
            {"$match": user_filter if user["role"] != "admin" else {}},
            {"$group": {"_id": None, "total": {"$sum": "$value"}}}
        ]
        pipeline_value_result = await current_db.opportunities.aggregate(pipeline_value_agg).to_list(1)
        pipeline_value = pipeline_value_result[0]["total"] if pipeline_value_result else 0
        
        # Recent leads (last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_leads_filter = {**user_filter, "created_at": {"$gte": seven_days_ago}}
        recent_leads = await current_db.leads.count_documents(recent_leads_filter)
        
        # Total contacts
        total_contacts = await current_db.contacts.count_documents({})
        
        return {
            "total_leads": total_leads,
            "total_opportunities": total_opportunities,
            "total_contacts": total_contacts,
            "pipeline_value": pipeline_value,
            "leads_by_status": leads_by_status,
            "recent_leads": recent_leads
        }
        
    except Exception as e:
        logging.error(f"Error fetching dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEADS (production endpoints from crm_complete_routes)
# ==========================================

@router.get("/leads")
async def get_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    stage: Optional[str] = None,
    priority: Optional[str] = None,
    owner_email: Optional[str] = None,
    search: Optional[str] = None,
    tag: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """List all leads with filters and RBAC"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Build filter with RBAC
        filter_query = get_user_assigned_filter(user)
        
        if status:
            filter_query["status"] = status
        if stage:
            filter_query["stage"] = stage
        if priority:
            filter_query["priority"] = priority
        if owner_email:
            filter_query["owner_email"] = owner_email
        if tag:
            filter_query["tags"] = tag
        if search:
            filter_query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}},
                {"brand_name": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}}
            ]
        
        # Count total
        total = await current_db.leads.count_documents(filter_query)
        
        # Get leads with pagination
        skip = (page - 1) * limit
        cursor = current_db.leads.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
        leads = await cursor.to_list(limit)
        
        # Format leads
        leads_formatted = []
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
            leads_formatted.append(lead)
        
        return {
            "leads": leads_formatted,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }
        
    except Exception as e:
        logging.error(f"Error fetching leads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/{lead_id}")
async def get_lead_detail(lead_id: str, user: Dict = Depends(get_current_user)):
    """Get single lead by ID"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        try:
            lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        except:
            raise HTTPException(status_code=400, detail="Invalid lead ID")
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # RBAC check
        if user["role"] == "commercial":
            if lead.get("assigned_to") != user["email"] and lead.get("owner_email") != user["email"]:
                raise HTTPException(status_code=403, detail="Access denied")
        
        lead["_id"] = str(lead["_id"])
        lead["id"] = lead["_id"]
        
        return lead
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead {lead_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads")
async def create_lead(lead_data: LeadCreate, user: Dict = Depends(get_current_user)):
    """Create new lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_lead = {
            **lead_data.dict(),
            "status": "NEW",
            "stage": "lead",
            "priority": "medium",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"],
            "owner_email": user["email"]
        }
        
        result = await current_db.leads.insert_one(new_lead)
        
        # Log activity
        await log_audit_event(
            current_db,
            user_id=user["id"],
            user_email=user["email"],
            action="lead_created",
            resource_type="lead",
            resource_id=str(result.inserted_id),
            details={"email": lead_data.email, "brand_name": lead_data.brand_name}
        )
        
        return {"message": "Lead created successfully", "lead_id": str(result.inserted_id)}
        
    except Exception as e:
        logging.error(f"Error creating lead: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
    """Update lead (full update)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # RBAC check
    if user["role"] == "commercial":
        if lead.get("assigned_to") != user["email"] and lead.get("owner_email") != user["email"]:
            raise HTTPException(status_code=403, detail="You can only update leads assigned to you")
        if update_data.owner_email is not None:
            raise HTTPException(status_code=403, detail="Only admin can reassign leads")
    
    # Build update
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await current_db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": update_dict}
    )
    
    # Log activity
    await log_audit_event(
        current_db,
        user_id=user["id"],
        user_email=user["email"],
        action="lead_updated",
        resource_type="lead",
        resource_id=lead_id,
        details={"changes": {k: str(v) for k, v in update_dict.items()}}
    )
    
    return {"message": "Lead updated successfully"}


@router.patch("/leads/{lead_id}")
async def patch_lead(lead_id: str, update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
    """PATCH lead (partial update) - from crm_additional_routes"""
    return await update_lead(lead_id, update_data, user)


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user: Dict = Depends(require_admin)):
    """Delete lead (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.leads.delete_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Log activity
    await log_audit_event(
        current_db,
        user_id=user["id"],
        user_email=user["email"],
        action="lead_deleted",
        resource_type="lead",
        resource_id=lead_id,
        details={}
    )
    
    return {"message": "Lead deleted successfully"}


# ==========================================
# LEAD ACTIVITIES (from crm_missing_routes + crm_additional_routes)
# ==========================================

@router.get("/leads/{lead_id}/activities")
async def get_lead_activities(
    lead_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all activities for a specific lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Verify lead exists
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get activities
        activities = await current_db.activities.find(
            {"lead_id": lead_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Get crm_activities (email sends, etc.)
        crm_activities = await current_db.crm_activities.find(
            {"lead_id": lead_id}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Merge and format
        all_activities = []
        
        for act in activities:
            all_activities.append({
                "id": str(act["_id"]),
                "_id": str(act["_id"]),
                "type": act.get("type", "note"),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_by": act.get("created_by", act.get("user_email", "")),
                "created_at": act["created_at"].isoformat() if isinstance(act.get("created_at"), datetime) else str(act.get("created_at", "")),
                "metadata": act.get("metadata", {})
            })
        
        for act in crm_activities:
            all_activities.append({
                "id": str(act["_id"]),
                "type": act.get("type", "email"),
                "subject": act.get("subject", ""),
                "description": f"Email to {act.get('to_email', '')}",
                "user_email": act.get("sent_by", ""),
                "created_at": act.get("sent_at", act.get("created_at", "")),
                "metadata": {"to_email": act.get("to_email")}
            })
        
        # Sort by date
        all_activities.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return {"activities": all_activities[:limit], "total": len(all_activities), "count": len(all_activities), "lead_id": lead_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD EMAILS (from crm_missing_routes)
# ==========================================

@router.get("/leads/{lead_id}/emails")
async def get_lead_emails(
    lead_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all emails sent to/from a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get email activities
        emails = await current_db.crm_activities.find({
            "lead_id": lead_id,
            "type": "email"
        }).sort("sent_at", -1).limit(limit).to_list(limit)
        
        formatted = []
        for email in emails:
            formatted.append({
                "id": str(email["_id"]),
                "to_email": email.get("to_email"),
                "subject": email.get("subject"),
                "body": email.get("body"),
                "sent_by": email.get("sent_by"),
                "sent_at": email.get("sent_at"),
                "status": email.get("status", "sent")
            })
        
        return {"emails": formatted, "total": len(formatted)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITIES (from crm_complete_routes)
# ==========================================

@router.get("/opportunities")
async def get_opportunities(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    stage: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """List all opportunities"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        filter_query = get_user_assigned_filter(user)
        if stage:
            filter_query["stage"] = stage
        
        total = await current_db.opportunities.count_documents(filter_query)
        skip = (page - 1) * limit
        
        opportunities = await current_db.opportunities.find(filter_query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        for opp in opportunities:
            opp["_id"] = str(opp["_id"])
            opp["id"] = opp["_id"]
        
        return {"opportunities": opportunities, "total": total, "page": page, "limit": limit}
        
    except Exception as e:
        logging.error(f"Error fetching opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities")
async def create_opportunity(opp_data: OpportunityCreate, user: Dict = Depends(get_current_user)):
    """Create new opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_opp = {
            **opp_data.dict(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"],
            "owner_email": user["email"]
        }
        
        result = await current_db.opportunities.insert_one(new_opp)
        
        return {"message": "Opportunity created successfully", "opportunity_id": str(result.inserted_id)}
        
    except Exception as e:
        logging.error(f"Error creating opportunity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACTS (from crm_complete_routes)
# ==========================================

@router.get("/contacts")
async def get_contacts(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """List all contacts"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        filter_query = {}
        if search:
            filter_query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}}
            ]
        
        total = await current_db.contacts.count_documents(filter_query)
        skip = (page - 1) * limit
        
        contacts = await current_db.contacts.find(filter_query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        for contact in contacts:
            contact["_id"] = str(contact["_id"])
            contact["id"] = contact["_id"]
        
        return {"contacts": contacts, "total": total, "page": page, "limit": limit}
        
    except Exception as e:
        logging.error(f"Error fetching contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts")
async def create_contact(contact_data: ContactCreate, user: Dict = Depends(get_current_user)):
    """Create new contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_contact = {
            **contact_data.dict(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"]
        }
        
        result = await current_db.contacts.insert_one(new_contact)
        
        return {"message": "Contact created successfully", "contact_id": str(result.inserted_id)}
        
    except Exception as e:
        logging.error(f"Error creating contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACT NOTES/ACTIVITIES (from crm_missing_routes)
# ==========================================

@router.get("/contacts/{contact_id}/notes")
async def get_contact_notes(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get notes for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        notes = await current_db.notes.find({"contact_id": contact_id}).sort("created_at", -1).to_list(100)
        
        for note in notes:
            note["_id"] = str(note["_id"])
        
        return {"notes": notes, "total": len(notes)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts/{contact_id}/notes")
async def create_contact_note(contact_id: str, note_data: NoteCreate, user: Dict = Depends(get_current_user)):
    """Create note for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        new_note = {
            "contact_id": contact_id,
            "content": note_data.text,
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.notes.insert_one(new_note)
        
        return {"message": "Note created successfully", "note_id": str(result.inserted_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EMAIL DRAFTS (from crm_missing_routes)
# ==========================================

@router.get("/drafts")
async def get_email_drafts(user: Dict = Depends(get_current_user), limit: int = Query(50, le=200)):
    """Get all email drafts for current user"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        drafts = await current_db.email_drafts.find({
            "created_by": user["email"]
        }).sort("created_at", -1).limit(limit).to_list(limit)
        
        for draft in drafts:
            draft["_id"] = str(draft["_id"])
        
        return {"drafts": drafts, "total": len(drafts)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts")
async def create_email_draft(draft_data: EmailDraftCreate, user: Dict = Depends(get_current_user)):
    """Create new email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_draft = {
            "to_email": draft_data.to_email,
            "subject": draft_data.subject,
            "body": draft_data.body or draft_data.message,
            "lead_id": draft_data.lead_id,
            "contact_id": draft_data.contact_id,
            "opportunity_id": draft_data.opportunity_id,
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.email_drafts.insert_one(new_draft)
        
        return {"message": "Draft created successfully", "draft_id": str(result.inserted_id)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS (dispatch, users, tags)
# ==========================================

@router.get("/settings/dispatch")
async def get_dispatch_settings(user: Dict = Depends(get_current_user)):
    """Get lead dispatch/routing settings"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Return dispatch settings from settings collection
        settings_cursor = current_db.settings.find({
            "$or": [
                {"category": "dispatch"},
                {"key": {"$regex": "^dispatch_"}}
            ]
        })
        
        settings_list = await settings_cursor.to_list(100)
        dispatch_settings = {s["key"]: s.get("value") for s in settings_list}
        
        # Default settings if empty
        if not dispatch_settings:
            dispatch_settings = {
                "auto_assign_enabled": False,
                "round_robin_enabled": True,
                "notify_on_assign": True
            }
        
        return {"success": True, "data": dispatch_settings}
        
    except Exception as e:
        logging.error(f"[CRM Settings] Error getting dispatch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/dispatch")
async def update_dispatch_settings(data: Dict[str, Any] = Body(...), user: Dict = Depends(get_current_user)):
    """Update dispatch settings (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Admin check
    if user["role"] not in ["admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        import json
        
        for key, value in data.items():
            await current_db.settings.update_one(
                {"key": key},
                {
                    "$set": {
                        "category": "dispatch",
                        "key": key,
                        "value": json.dumps(value) if isinstance(value, (dict, list)) else str(value),
                        "updated_at": datetime.now(timezone.utc),
                        "updated_by": user["email"]
                    }
                },
                upsert=True
            )
        
        return {"success": True, "message": "Dispatch settings updated"}
        
    except Exception as e:
        logging.error(f"[CRM Settings] Error updating dispatch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/users")
async def get_crm_users_list(user: Dict = Depends(get_current_user)):
    """Get CRM users list for assignment"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get active CRM users
        users_cursor = current_db.crm_users.find(
            {"is_active": True},
            {"email": 1, "name": 1, "role": 1, "_id": 0}
        )
        
        users = await users_cursor.to_list(100)
        
        return {"success": True, "data": users}
        
    except Exception as e:
        logging.error(f"[CRM Settings] Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/tags")
async def get_available_tags(user: Dict = Depends(get_current_user)):
    """Get available tags from leads and contacts"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Aggregate distinct tags from leads
        tags_set = set()
        
        leads_cursor = current_db.leads.find({"tags": {"$exists": True, "$ne": []}}, {"tags": 1})
        async for lead in leads_cursor:
            if lead.get("tags"):
                tags_set.update(lead["tags"])
        
        contacts_cursor = current_db.contacts.find({"tags": {"$exists": True, "$ne": []}}, {"tags": 1})
        async for contact in contacts_cursor:
            if contact.get("tags"):
                tags_set.update(contact["tags"])
        
        return {"success": True, "data": sorted(list(tags_set))}
        
    except Exception as e:
        logging.error(f"[CRM Settings] Error getting tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEADS - ADVANCED QUERIES (overdue, missing actions)
# ==========================================

@router.get("/leads/overdue-actions")
async def get_leads_overdue_actions(user: Dict = Depends(get_current_user)):
    """Get leads with overdue next actions"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get user filter for RBAC
        user_filter = get_user_assigned_filter(user)
        
        # Find leads with overdue actions
        now = datetime.now(timezone.utc)
        overdue_filter = {
            **user_filter,
            "next_action_date": {"$lt": now},
            "status": {"$nin": ["converted", "lost"]}
        }
        
        leads_cursor = current_db.leads.find(overdue_filter).sort("next_action_date", 1).limit(100)
        leads = await leads_cursor.to_list(100)
        
        # Format leads
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
        
        return {"success": True, "data": leads, "total": len(leads)}
        
    except Exception as e:
        logging.error(f"[CRM Leads] Error getting overdue actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/missing-next-action")
async def get_leads_missing_next_action(user: Dict = Depends(get_current_user)):
    """Get leads without next action defined"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get user filter for RBAC
        user_filter = get_user_assigned_filter(user)
        
        # Find leads without next action
        missing_filter = {
            **user_filter,
            "$or": [
                {"next_action": {"$exists": False}},
                {"next_action": None},
                {"next_action": ""}
            ],
            "status": {"$nin": ["converted", "lost"]}
        }
        
        leads_cursor = current_db.leads.find(missing_filter).sort("created_at", -1).limit(100)
        leads = await leads_cursor.to_list(100)
        
        # Format leads
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
        
        return {"success": True, "data": leads, "total": len(leads)}
        
    except Exception as e:
        logging.error(f"[CRM Leads] Error getting missing next actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/leads/{lead_id}/next-action")
async def update_lead_next_action(lead_id: str, data: Dict[str, Any] = Body(...), user: Dict = Depends(get_current_user)):
    """Update lead next action and date"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # RBAC check
    if user["role"] == "commercial":
        if lead.get("assigned_to") != user["email"] and lead.get("owner_email") != user["email"]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        update_dict = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if "next_action" in data:
            update_dict["next_action"] = data["next_action"]
        if "next_action_date" in data:
            # Parse date string if needed
            if isinstance(data["next_action_date"], str):
                try:
                    update_dict["next_action_date"] = datetime.fromisoformat(data["next_action_date"].replace('Z', '+00:00'))
                except:
                    update_dict["next_action_date"] = data["next_action_date"]
            else:
                update_dict["next_action_date"] = data["next_action_date"]
        
        await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": update_dict}
        )
        
        # Log activity
        await log_audit_event(
            current_db,
            user_id=user["id"],
            user_email=user["email"],
            action="next_action_updated",
            resource_type="lead",
            resource_id=lead_id,
            details={"next_action": data.get("next_action"), "next_action_date": str(data.get("next_action_date"))}
        )
        
        return {"success": True, "message": "Next action updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[CRM Leads] Error updating next action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LOGOUT (from crm_missing_routes)
# ==========================================

@router.post("/logout")
async def crm_logout(user: Dict = Depends(get_current_user)):
    """Logout endpoint - stateless confirmation (frontend clears token)"""
    logging.info(f"User {user['email']} logged out from CRM")
    return {"success": True, "message": "Logged out successfully"}


# ==========================================
# ADMIN - GET LEADS (backward compatibility from crm_routes.py)
# ==========================================

@router.get("/admin/leads")
async def admin_get_leads(limit: int = Query(10, le=200), skip: int = 0, user: Dict = Depends(require_admin)):
    """Admin endpoint to view leads (legacy from crm_routes.py)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        leads = await current_db.leads.find({}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await current_db.leads.count_documents({})
        
        for lead in leads:
            lead["_id"] = str(lead["_id"])
        
        return {"leads": leads, "total": total, "limit": limit, "skip": skip}
        
    except Exception as e:
        logging.error(f"Error fetching admin leads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
