"""
CRM Unified Router - Phase 2
Consolidated from: crm_routes.py, crm_complete_routes.py, crm_missing_routes.py, crm_additional_routes.py
ALL CRM routes centralized in app/routers/crm/
CRITICAL: URLs and JSON response formats unchanged for frontend compatibility
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Path, status
from pydantic import BaseModel, EmailStr, Field
from typing import Annotated, Optional, List, Dict, Any
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
    get_db,
    VALID_CRM_ROLES
)

# CRM Router with /api/crm prefix
router = APIRouter(prefix="/api/crm", tags=["CRM"])


# ==========================================
# PYDANTIC MODELS (unified from all CRM files)
# ==========================================

class LeadCreate(BaseModel):
    email: EmailStr
    brand_name: str
    name: Optional[str] = None
    contact_name: Optional[str] = None  # Frontend sends contact_name
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
    status: Optional[str] = None  # Frontend sends status
    priority: Optional[str] = None  # Frontend sends priority


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
        
        # Leads today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        leads_today_filter = {**user_filter, "created_at": {"$gte": today_start}}
        leads_today = await current_db.leads.count_documents(leads_today_filter)
        
        # Leads last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        leads_30d_filter = {**user_filter, "created_at": {"$gte": thirty_days_ago}}
        leads_last_30_days = await current_db.leads.count_documents(leads_30d_filter)
        
        # Total contacts
        total_contacts = await current_db.contacts.count_documents({})
        
        # Mini-analyses count (from mini_analyses collection + leads with source=mini-analyse)
        mini_analyses_count = 0
        try:
            # Count from dedicated collection
            mini_analyses_count = await current_db.mini_analyses.count_documents({})
        except:
            pass
        
        # Also count leads with mini-analyse source
        mini_leads = await current_db.leads.count_documents({
            "source": {"$regex": "mini.?analy", "$options": "i"}
        })
        mini_analyses_total = mini_analyses_count + mini_leads
        
        # Return in format expected by frontend (nested structure)
        return {
            # Flat structure (legacy)
            "total_leads": total_leads,
            "total_opportunities": total_opportunities,
            "total_contacts": total_contacts,
            "pipeline_value": pipeline_value,
            "leads_by_status": leads_by_status,
            "recent_leads": recent_leads,
            "mini_analyses": mini_analyses_total,
            # Nested structure (frontend expected)
            "leads": {
                "total": total_leads,
                "today": leads_today,
                "last_7_days": recent_leads,
                "last_30_days": leads_last_30_days,
                "by_status": leads_by_status
            },
            "opportunities": {
                "total": total_opportunities,
                "pipeline_value": pipeline_value
            },
            "contacts": {
                "total": total_contacts
            }
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
                {"contact_name": {"$regex": search, "$options": "i"}},
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
            lead["lead_id"] = lead["_id"]  # Frontend expects lead_id
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


@router.get("/leads/overdue-actions")
async def get_leads_overdue_actions_early(user: Dict = Depends(get_current_user), limit: int = Query(20, ge=1, le=100)):
    """Get leads with overdue next actions — static route must come before /leads/{lead_id}"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        user_filter = get_user_assigned_filter(user)
        now = datetime.now(timezone.utc)
        overdue_filter = {
            **user_filter,
            "$or": [
                {"next_action_date": {"$lt": now, "$ne": None}},
                {"next_action.date": {"$lt": now, "$ne": None}}
            ],
            "status": {"$nin": ["converted", "lost"]}
        }
        leads_cursor = current_db.leads.find(overdue_filter).sort("next_action_date", 1).limit(limit)
        leads = await leads_cursor.to_list(limit)
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
            # Calculate days_overdue from whichever date field is present
            action_date = lead.get("next_action_date") or (lead.get("next_action") or {}).get("date")
            if action_date:
                if isinstance(action_date, str):
                    try:
                        from datetime import datetime as dt
                        action_date = dt.fromisoformat(action_date.replace("Z", "+00:00"))
                    except Exception:
                        action_date = None
                if action_date:
                    delta = now - action_date if action_date.tzinfo else now.replace(tzinfo=None) - action_date
                    lead["days_overdue"] = max(0, delta.days)
                else:
                    lead["days_overdue"] = 0
            else:
                lead["days_overdue"] = 0
        return {"success": True, "leads": leads, "data": leads, "total": len(leads)}
    except Exception as e:
        logging.error(f"[CRM Leads] Error getting overdue actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/missing-next-action")
async def get_leads_missing_next_action_early(
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    priority: Optional[str] = Query(None)
):
    """Get leads without next action defined — static route must come before /leads/{lead_id}"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        user_filter = get_user_assigned_filter(user)
        missing_filter = {
            **user_filter,
            "$or": [
                {"next_action": {"$exists": False}},
                {"next_action": None},
                {"next_action": ""},
                {"next_action_date": {"$exists": False}},
                {"next_action_date": None}
            ],
            "status": {"$nin": ["converted", "lost"]}
        }
        if priority:
            missing_filter["priority"] = priority
        leads_cursor = current_db.leads.find(missing_filter).sort("created_at", -1).limit(limit)
        leads = await leads_cursor.to_list(limit)
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
        return {"success": True, "leads": leads, "data": leads, "total": len(leads)}
    except Exception as e:
        logging.error(f"[CRM Leads] Error getting missing next actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/{lead_id}")
async def get_lead_detail(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], user: Dict = Depends(get_current_user)):
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
        lead["lead_id"] = lead["_id"]  # Frontend expects lead_id
        
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
        # Check if lead with this email already exists
        existing_lead = await current_db.leads.find_one({"email": lead_data.email})
        if existing_lead:
            raise HTTPException(
                status_code=409, 
                detail=f"Lead with email {lead_data.email} already exists"
            )
        
        lead_dict = lead_data.dict(exclude_none=True)
        new_lead = {
            **lead_dict,
            "status": lead_dict.get("status", "NEW"),  # Use frontend value or default
            "stage": "lead",
            "priority": lead_dict.get("priority", "C"),  # Use frontend value or default
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"],
            "owner_email": user["email"]
        }
        
        result = await current_db.leads.insert_one(new_lead)
        
        # Log activity
        try:
            await log_audit_event(
                user, "lead_created", "lead", str(result.inserted_id),
                details={"email": lead_data.email, "brand_name": lead_data.brand_name}
            )
        except Exception as audit_error:
            logging.warning(f"Failed to log audit event: {audit_error}")
        
        return {"message": "Lead created successfully", "lead_id": str(result.inserted_id), "status": "created"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating lead: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
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
    try:
        await log_audit_event(
            user, "lead_updated", "lead", lead_id,
            details={"changes": {k: str(v) for k, v in update_dict.items()}}
        )
    except Exception:
        pass
    
    return {"message": "Lead updated successfully"}


@router.patch("/leads/{lead_id}")
async def patch_lead(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
    """PATCH lead (partial update) - from crm_additional_routes"""
    return await update_lead(lead_id, update_data, user)


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], user: Dict = Depends(require_admin)):
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
    try:
        await log_audit_event(user, "lead_deleted", "lead", lead_id)
    except Exception:
        pass
    
    return {"message": "Lead deleted successfully"}


@router.post("/leads/bulk-delete")
async def bulk_delete_leads(data: Dict = Body(...), user: Dict = Depends(require_admin)):
    """Delete multiple leads at once (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    lead_ids = data.get("lead_ids", [])
    if not lead_ids:
        raise HTTPException(status_code=400, detail="No lead IDs provided")
    try:
        object_ids = [ObjectId(lid) for lid in lead_ids if lid and len(str(lid)) == 24]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")
    if not object_ids:
        raise HTTPException(status_code=400, detail="No valid lead IDs")
    try:
        result = await current_db.leads.delete_many({"_id": {"$in": object_ids}})
        try:
            await log_audit_event(
                user, "leads_bulk_deleted", "lead", "bulk",
                details={"count": result.deleted_count, "ids": lead_ids}
            )
        except Exception:
            pass
        return {"success": True, "deleted_count": result.deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD ACTIVITIES (from crm_missing_routes + crm_additional_routes)
# ==========================================

@router.get("/leads/{lead_id}/activities")
async def get_lead_activities(
    lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")],
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


@router.post("/leads/{lead_id}/activities")
async def create_lead_activity(
    lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")],
    activity_data: dict,
    user: Dict = Depends(get_current_user)
):
    """Create an activity linked to a specific lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        new_activity = {
            **activity_data,
            "lead_id": lead_id,
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await current_db.crm_activities.insert_one(new_activity)
        new_activity["_id"] = str(result.inserted_id)
        new_activity["id"] = new_activity["_id"]
        return {"success": True, "activity": new_activity, "id": new_activity["_id"]}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating lead activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD EMAILS (from crm_missing_routes)
# ==========================================

@router.get("/leads/{lead_id}/emails")
async def get_lead_emails(
    lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")],
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
    limit: int = Query(25, ge=1, le=500),
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


@router.get("/opportunities/{opp_id}")
async def get_opportunity(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get single opportunity by ID"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        opp["_id"] = str(opp["_id"])
        opp["id"] = opp["_id"]
        return opp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/opportunities/{opp_id}")
async def update_opportunity(opp_id: str, opp_data: OpportunityUpdate, user: Dict = Depends(get_current_user)):
    """Update opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        update_fields = {k: v for k, v in opp_data.dict().items() if v is not None}
        update_fields["updated_at"] = datetime.now(timezone.utc)
        result = await current_db.opportunities.update_one(
            {"_id": ObjectId(opp_id)},
            {"$set": update_fields}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return {"message": "Opportunity updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/opportunities/{opp_id}")
async def delete_opportunity(opp_id: str, user: Dict = Depends(get_current_user)):
    """Delete opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.opportunities.delete_one({"_id": ObjectId(opp_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return {"message": "Opportunity deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
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


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get single contact by ID"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        contact["_id"] = str(contact["_id"])
        contact["id"] = contact["_id"]
        return contact
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contacts/{contact_id}")
async def update_contact(contact_id: str, contact_data: ContactUpdate, user: Dict = Depends(get_current_user)):
    """Update contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        update_fields = {k: v for k, v in contact_data.dict().items() if v is not None}
        update_fields["updated_at"] = datetime.now(timezone.utc)
        result = await current_db.contacts.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": update_fields}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        return {"message": "Contact updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, user: Dict = Depends(get_current_user)):
    """Delete contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.contacts.delete_one({"_id": ObjectId(contact_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        return {"message": "Contact deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
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


@router.delete("/contacts/{contact_id}/notes/{note_id}")
async def delete_contact_note(contact_id: str, note_id: str, user: Dict = Depends(get_current_user)):
    """Delete a note from a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.notes.delete_one({"_id": ObjectId(note_id), "contact_id": contact_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        return {"message": "Note deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EMAIL DRAFTS— unified with email_export_routes (uses 'emails' collection, status=draft)
# Legacy path /drafts kept for backward compat; canonical path is /emails/drafts
# ==========================================

@router.get("/drafts")
async def get_email_drafts(user: Dict = Depends(get_current_user), limit: int = Query(50, le=200)):
    """Get all email drafts for current user (unified with /emails/drafts endpoint)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Unified: read from 'emails' collection (same as email_export_routes.py /emails/drafts)
        drafts = await current_db.emails.find({
            "status": "draft",
            "created_by": user["email"]
        }).sort("updated_at", -1).limit(limit).to_list(limit)
        
        # Fallback: also check legacy email_drafts collection
        if not drafts:
            legacy = await current_db.email_drafts.find({
                "created_by": user["email"]
            }).sort("created_at", -1).limit(limit).to_list(limit)
            drafts = legacy

        for draft in drafts:
            draft["_id"] = str(draft["_id"])
        
        return {"drafts": drafts, "total": len(drafts)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/drafts")
async def create_email_draft(draft_data: EmailDraftCreate, user: Dict = Depends(get_current_user)):
    """Create new email draft (unified: writes to 'emails' collection)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        now = datetime.now(timezone.utc)
        new_draft = {
            "to": draft_data.to_email,
            "subject": draft_data.subject,
            "body": draft_data.body or draft_data.message,
            "lead_id": draft_data.lead_id,
            "contact_id": draft_data.contact_id,
            "opportunity_id": draft_data.opportunity_id,
            "status": "draft",
            "created_by": user["email"],
            "created_at": now,
            "updated_at": now,
        }
        
        result = await current_db.emails.insert_one(new_draft)
        
        return {"message": "Draft created successfully", "draft_id": str(result.inserted_id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/drafts/{draft_id}")
async def delete_email_draft_legacy(draft_id: str, user: Dict = Depends(get_current_user)):
    """Delete an email draft (unified: deletes from 'emails' collection)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.emails.delete_one({
            "_id": ObjectId(draft_id),
            "status": "draft",
            "created_by": user["email"]
        })
        if result.deleted_count == 0:
            # Try legacy email_drafts collection
            result = await current_db.email_drafts.delete_one({
                "_id": ObjectId(draft_id),
                "created_by": user["email"]
            })
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        return {"success": True, "message": "Draft deleted"}
    except HTTPException:
        raise
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


# NOTE: Route /settings/users is defined below at line ~1492
# This duplicate has been removed to avoid conflicts


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


@router.post("/settings/tags")
async def create_tag(data: Dict[str, Any] = Body(...), user: Dict = Depends(get_current_user)):
    """Create a new CRM tag"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        tag_name = data.get("name", "").strip()
        if not tag_name:
            raise HTTPException(status_code=400, detail="Tag name required")
        existing = await current_db.crm_tags.find_one({"name": tag_name})
        if existing:
            raise HTTPException(status_code=409, detail="Tag already exists")
        result = await current_db.crm_tags.insert_one({
            "name": tag_name,
            "created_at": datetime.now(timezone.utc),
            "created_by": user["email"]
        })
        return {"success": True, "tag_id": str(result.inserted_id), "name": tag_name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/tags/{tag_id}")
async def delete_tag(tag_id: str, user: Dict = Depends(get_current_user)):
    """Delete a CRM tag"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.crm_tags.delete_one({"_id": ObjectId(tag_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Tag not found")
        return {"success": True, "message": "Tag deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


_DEFAULT_PIPELINE_STAGES = [
    {"id": "qualification", "name": "Qualification", "order": 0, "color": "#3B82F6", "probability": 10},
    {"id": "proposal", "name": "Proposition", "order": 1, "color": "#F59E0B", "probability": 30},
    {"id": "negotiation", "name": "Négociation", "order": 2, "color": "#8B5CF6", "probability": 60},
    {"id": "closed_won", "name": "Gagné", "order": 3, "color": "#10B981", "probability": 100},
    {"id": "closed_lost", "name": "Perdu", "order": 4, "color": "#EF4444", "probability": 0},
]


async def _load_pipeline_stages(db) -> list:
    """Load stages from DB or return defaults."""
    try:
        setting = await db.settings.find_one({"key": "pipeline_stages"})
        if setting:
            val = setting["value"]
            return val if isinstance(val, list) else list(val)
    except Exception:
        pass
    return [dict(s) for s in _DEFAULT_PIPELINE_STAGES]


async def _save_pipeline_stages(db, stages: list):
    await db.settings.update_one(
        {"key": "pipeline_stages"},
        {"$set": {"key": "pipeline_stages", "value": stages, "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )


@router.get("/settings/pipeline-stages")
async def get_pipeline_stages(user: Dict = Depends(get_current_user)):
    """Get available pipeline stages"""
    current_db = get_db()
    if current_db is None:
        return {"success": True, "stages": _DEFAULT_PIPELINE_STAGES}
    try:
        stages = await _load_pipeline_stages(current_db)
        return {"success": True, "stages": stages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/pipeline-stages")
async def create_pipeline_stage(data: Dict = Body(...), user: Dict = Depends(get_current_user)):
    """Add a new pipeline stage"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    stage_id = data.get("id", "").strip()
    name = data.get("name", "").strip()
    if not stage_id or not name:
        raise HTTPException(status_code=400, detail="id and name are required")
    try:
        stages = await _load_pipeline_stages(current_db)
        if any(s["id"] == stage_id for s in stages):
            raise HTTPException(status_code=400, detail="Stage id already exists")
        new_stage = {
            "id": stage_id,
            "name": name,
            "order": data.get("order", len(stages)),
            "color": data.get("color", "#3B82F6"),
            "probability": data.get("probability", 0),
        }
        stages.append(new_stage)
        await _save_pipeline_stages(current_db, stages)
        return {"success": True, "stages": stages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/pipeline-stages/{stage_id}")
async def update_pipeline_stage(stage_id: str, data: Dict = Body(...), user: Dict = Depends(get_current_user)):
    """Update a pipeline stage"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        stages = await _load_pipeline_stages(current_db)
        found = False
        for stage in stages:
            if stage["id"] == stage_id:
                for field in ("name", "order", "color", "probability"):
                    if field in data:
                        stage[field] = data[field]
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="Stage not found")
        await _save_pipeline_stages(current_db, stages)
        return {"success": True, "stages": stages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/pipeline-stages/{stage_id}")
async def delete_pipeline_stage(stage_id: str, user: Dict = Depends(get_current_user)):
    """Delete a pipeline stage"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        stages = await _load_pipeline_stages(current_db)
        new_stages = [s for s in stages if s["id"] != stage_id]
        if len(new_stages) == len(stages):
            raise HTTPException(status_code=404, detail="Stage not found")
        await _save_pipeline_stages(current_db, new_stages)
        return {"success": True, "stages": new_stages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/quality")
async def get_quality_settings(user: Dict = Depends(get_current_user)):
    """Get CRM quality thresholds"""
    current_db = get_db()
    if current_db is None:
        return {"success": True, "data": {"response_time_hours": 24, "follow_up_days": 7, "min_interactions": 3}}
    try:
        setting = await current_db.settings.find_one({"key": "crm_quality"})
        if setting:
            import json
            data = json.loads(setting["value"]) if isinstance(setting["value"], str) else setting["value"]
            return {"success": True, "data": data}
        return {"success": True, "data": {"response_time_hours": 24, "follow_up_days": 7, "min_interactions": 3}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/settings/performance")
async def get_performance_settings(user: Dict = Depends(get_current_user)):
    """Get CRM performance targets"""
    current_db = get_db()
    if current_db is None:
        return {"success": True, "data": {"monthly_deals_target": 10, "conversion_rate_target": 20, "revenue_target": 50000}}
    try:
        setting = await current_db.settings.find_one({"key": "crm_performance"})
        if setting:
            import json
            data = json.loads(setting["value"]) if isinstance(setting["value"], str) else setting["value"]
            return {"success": True, "data": data}
        return {"success": True, "data": {"monthly_deals_target": 10, "conversion_rate_target": 20, "revenue_target": 50000}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pack-rappel-requests")
async def get_pack_rappel_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Get pack rappel requests (leads with source=pack_rappel)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        query = {"source": "pack_rappel"}
        if status:
            query["status"] = status
        total = await current_db.leads.count_documents(query)
        skip = (page - 1) * limit
        leads = await current_db.leads.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
        return {"success": True, "data": leads, "total": total, "page": page, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pack-rappel-requests/{lead_id}/assign")
async def assign_pack_rappel_request(
    lead_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Assign pack rappel request to a consultant"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"assigned_to": data.get("assigned_to"), "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Request not found")
        return {"success": True, "message": "Request assigned"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pack-rappel-requests/{lead_id}/status")
async def update_pack_rappel_status(
    lead_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Update pack rappel request status"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        result = await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {"$set": {"status": data.get("status"), "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Request not found")
        return {"success": True, "message": "Status updated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
@router.put("/leads/{lead_id}/next-action")
async def update_lead_next_action(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], data: Dict[str, Any] = Body(...), user: Dict = Depends(get_current_user)):
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
        try:
            await log_audit_event(
                user, "next_action_updated", "lead", lead_id,
                details={"next_action": data.get("next_action"), "next_action_date": str(data.get("next_action_date"))}
            )
        except Exception:
            pass
        
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


# ==========================================
# KPI ENDPOINTS
# ==========================================

def _kpi_start_date(period: str):
    now = datetime.now(timezone.utc)
    days = {"week": 7, "month": 30, "quarter": 90, "year": 365}.get(period, 30)
    return now - timedelta(days=days)


@router.get("/kpi/response-times")
async def get_response_times_kpi(
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """Get average response times using MongoDB aggregation (optimized)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        start_date = _kpi_start_date(period)
        
        pipeline = [
            # Filtre: leads dans la periode
            {
                "$match": {
                    "created_at": {"$gte": start_date}
                }
            },
            # Jointure avec activités
            {
                "$lookup": {
                    "from": "crm_activities",
                    "localField": "lead_id",
                    "foreignField": "lead_id",
                    "as": "activities"
                }
            },
            # Filtre: leads ayant au moins 1 activité
            {
                "$match": {
                    "activities.0": {"$exists": True}
                }
            },
            # Calcul: temps de première réponse
            {
                "$project": {
                    "status": 1,
                    "lead_created": "$created_at",
                    "first_activity": {"$min": "$activities.created_at"},
                    "response_time_ms": {
                        "$subtract": [
                            {"$min": "$activities.created_at"},
                            "$created_at"
                        ]
                    }
                }
            },
            # Agrégation: moyenne par statut
            {
                "$group": {
                    "_id": "$status",
                    "avg_response_time_ms": {"$avg": "$response_time_ms"},
                    "total_leads": {"$sum": 1}
                }
            },
            {
                "$sort": {"avg_response_time_ms": 1}
            }
        ]
        
        result = await current_db.leads.aggregate(pipeline).to_list(None)
        
        # Convert milliseconds to hours
        for item in result:
            if item.get("avg_response_time_ms"):
                item["avg_response_time_hours"] = round(item["avg_response_time_ms"] / (1000 * 60 * 60), 2)
            else:
                item["avg_response_time_hours"] = 0
        
        return {"success": True, "data": result, "period": period}
    except Exception as e:
        logging.error(f"KPI response-times error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/conversion-times")
async def get_conversion_times_kpi(
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """Get average conversion times by source"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        start_date = _kpi_start_date(period)
        pipeline = [
            {"$match": {"status": "converted", "created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$source", "avg_conversion_time": {"$avg": "$conversion_time"}, "count": {"$sum": 1}}},
            {"$sort": {"avg_conversion_time": 1}}
        ]
        result = await current_db.leads.aggregate(pipeline).to_list(None)
        return {"success": True, "data": result, "period": period}
    except Exception as e:
        logging.error(f"KPI conversion-times error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/source-performance")
async def get_source_performance_kpi(
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """Get performance metrics by source"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        start_date = _kpi_start_date(period)
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {
                "_id": "$source",
                "total_leads": {"$sum": 1},
                "converted": {"$sum": {"$cond": [{"$eq": ["$status", "converted"]}, 1, 0]}}
            }},
            {"$addFields": {
                "source": "$_id",
                "conversion_rate": {"$divide": ["$converted", "$total_leads"]}
            }},
            {"$sort": {"conversion_rate": -1}}
        ]
        result = await current_db.leads.aggregate(pipeline).to_list(None)
        return {"success": True, "data": result, "period": period}
    except Exception as e:
        logging.error(f"KPI source-performance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/funnel")
async def get_funnel_kpi(
    period: str = Query("month", pattern="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """Get funnel conversion rates by stage"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        start_date = _kpi_start_date(period)
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = await current_db.leads.aggregate(pipeline).to_list(None)
        return {"success": True, "data": result, "period": period}
    except Exception as e:
        logging.error(f"KPI funnel error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# RBAC ENDPOINTS
# ==========================================

@router.get("/rbac/roles")
async def get_rbac_roles(user: Dict = Depends(get_current_user)):
    """Get all available roles and permissions"""
    try:
        roles = {
            "admin": {"name": "Admin", "permissions": ["read", "write", "delete", "manage_users", "manage_team"]},
            "manager": {"name": "Manager", "permissions": ["read", "write", "manage_team"]},
            "commercial": {"name": "Commercial", "permissions": ["read", "write"]},
            "support": {"name": "Support", "permissions": ["read", "write"]},
            "readonly": {"name": "Readonly", "permissions": ["read"]}
        }
        return {"success": True, "data": roles, "valid_roles": VALID_CRM_ROLES}
    except Exception as e:
        logging.error(f"RBAC roles error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rbac/permissions")
async def get_rbac_permissions(user: Dict = Depends(get_current_user)):
    """Get all available permissions"""
    try:
        permissions = [
            {"id": "read", "name": "Read", "description": "View CRM data"},
            {"id": "write", "name": "Write", "description": "Create and edit CRM data"},
            {"id": "delete", "name": "Delete", "description": "Delete CRM data"},
            {"id": "manage_users", "name": "Manage Users", "description": "Create and edit users"},
            {"id": "manage_team", "name": "Manage Team", "description": "Manage team members"}
        ]
        return {"success": True, "data": permissions}
    except Exception as e:
        logging.error(f"RBAC permissions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/role")
async def update_user_role(user_id: str, data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Update user role (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        new_role = data.get("role")
        if new_role not in VALID_CRM_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Valid roles: {VALID_CRM_ROLES}")
        
        result = await current_db.crm_users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": new_role, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            await log_audit_event(admin, "user_role_updated", "user", str(user_id), details={"new_role": new_role})
        except Exception:
            pass
        return {"success": True, "message": "Role updated"}
    except Exception as e:
        logging.error(f"Update role error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}/permissions")
async def set_custom_permissions(user_id: str, data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Set custom permissions for user (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        permissions = data.get("permissions", [])
        result = await current_db.crm_users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"custom_permissions": permissions, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            await log_audit_event(admin, "user_permissions_updated", "user", str(user_id), details={"permissions": permissions})
        except Exception:
            pass
        return {"success": True, "message": "Permissions updated"}
    except Exception as e:
        logging.error(f"Update permissions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# AUDIT LOG ENDPOINTS
# ==========================================

@router.get("/audit-logs")
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
    user_email: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Get audit logs with pagination and filtering"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        query = {}
        if event_type:
            query["event_type"] = event_type
        if user_email:
            query["user_email"] = user_email
        
        logs = await current_db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
        total = await current_db.audit_logs.count_documents(query)
        
        for log in logs:
            log["_id"] = str(log["_id"])
        
        return {"success": True, "data": logs, "total": total, "skip": skip, "limit": limit}
    except Exception as e:
        logging.error(f"Audit logs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs/stats")
async def get_audit_stats(user: Dict = Depends(get_current_user)):
    """Get audit log statistics"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        pipeline = [
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        result = await current_db.audit_logs.aggregate(pipeline).to_list(None)
        return {"success": True, "data": result}
    except Exception as e:
        logging.error(f"Audit stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs/entity/{entity_type}/{entity_id}")
async def get_entity_audit_logs(entity_type: str, entity_id: str, user: Dict = Depends(get_current_user)):
    """Get audit logs for specific entity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        query = {
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        logs = await current_db.audit_logs.find(query).sort("timestamp", -1).to_list(100)
        for log in logs:
            log["_id"] = str(log["_id"])
        return {"success": True, "data": logs}
    except Exception as e:
        logging.error(f"Entity audit logs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-logs/user/{email}")
async def get_user_audit_logs(email: str, user: Dict = Depends(get_current_user)):
    """Get audit logs for specific user"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        logs = await current_db.audit_logs.find({"user_email": email}).sort("timestamp", -1).to_list(100)
        for log in logs:
            log["_id"] = str(log["_id"])
        return {"success": True, "data": logs}
    except Exception as e:
        logging.error(f"User audit logs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# USER MANAGEMENT ENDPOINTS (CRUD)
# ==========================================

@router.get("/settings/users")
async def get_crm_users(user: Dict = Depends(require_admin)):
    """Get all CRM users — admin only"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        users = await current_db.crm_users.find({}).to_list(None)
        for u in users:
            u["_id"] = str(u["_id"])
            u.pop("password", None)
            # Ensure name exists for backward compatibility
            if not u.get("name") and (u.get("first_name") or u.get("last_name")):
                u["name"] = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        return {"success": True, "users": users}
    except Exception as e:
        logging.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/users")
async def create_crm_user(data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Create new CRM user (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        from passlib.hash import bcrypt
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "viewer")
        name = data.get("name", "")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        is_active = data.get("is_active", True)
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        # Use name if provided, otherwise build from first_name + last_name
        if not name and (first_name or last_name):
            name = f"{first_name} {last_name}".strip()
        
        existing = await current_db.crm_users.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="User already exists")
        
        hashed_password = bcrypt.hash(password)
        new_user = {
            "email": email,
            "password": hashed_password,
            "role": role,
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": is_active,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result = await current_db.crm_users.insert_one(new_user)
        new_user["_id"] = str(result.inserted_id)
        new_user.pop("password")
        
        try:
            await log_audit_event(admin, "user_created", "user", str(email), details={"role": role, "name": name})
        except Exception:
            pass
        return {"success": True, "data": new_user}
    except Exception as e:
        logging.error(f"Create user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings/users/{user_id}")
async def update_crm_user(user_id: str, data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Update CRM user (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        update_data = {"updated_at": datetime.now(timezone.utc)}
        if "email" in data:
            update_data["email"] = data["email"]
        if "role" in data:
            update_data["role"] = data["role"]
        if "name" in data:
            update_data["name"] = data["name"]
        if "first_name" in data:
            update_data["first_name"] = data["first_name"]
        if "last_name" in data:
            update_data["last_name"] = data["last_name"]
        if "is_active" in data:
            update_data["is_active"] = data["is_active"]
        if "password" in data and data["password"]:
            from passlib.hash import bcrypt
            update_data["password"] = bcrypt.hash(data["password"])
        
        result = await current_db.crm_users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            await log_audit_event(admin, "user_updated", "user", str(user_id), details={"changes": update_data})
        except Exception:
            pass
        return {"success": True, "message": "User updated"}
    except Exception as e:
        logging.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/settings/users/{user_id}")
async def delete_crm_user(user_id: str, admin: Dict = Depends(require_admin)):
    """Delete CRM user (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        user = await current_db.crm_users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        result = await current_db.crm_users.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            await log_audit_event(admin, "user_deleted", "user", str(user_id), details={"user_email": user.get("email")})
        except Exception:
            pass
        return {"success": True, "message": "User deleted"}
    except Exception as e:
        logging.error(f"Delete user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/users/{user_id}/assign")
async def assign_user_to_entity(user_id: str, data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Assign user to entity (leads, contacts, etc.)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        entity_type = data.get("entity_type")
        entity_id = data.get("entity_id")
        
        if entity_type not in ["lead", "contact", "opportunity"]:
            raise HTTPException(status_code=400, detail="Invalid entity type")
        
        collection_map = {"lead": "leads", "contact": "contacts", "opportunity": "opportunities"}
        collection = current_db[collection_map[entity_type]]
        
        result = await collection.update_one(
            {"_id": ObjectId(entity_id)},
            {"$set": {"assigned_to": user_id, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        try:
            await log_audit_event(admin, "user_assigned", "user", str(user_id), details={"entity_type": entity_type, "entity_id": entity_id})
        except Exception:
            pass
        return {"success": True, "message": "User assigned"}
    except Exception as e:
        logging.error(f"Assign user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/users/change-password")
async def change_own_password(data: Dict = Body(...), user: Dict = Depends(get_current_user)):
    """Self-service: change current user's own password (verifies current password)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        from passlib.hash import bcrypt
        current_password = data.get("current_password")
        new_password = data.get("new_password")
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="current_password and new_password are required")
        crm_user = await current_db.crm_users.find_one({"email": user["email"]})
        if not crm_user:
            raise HTTPException(status_code=404, detail="User not found")
        if not bcrypt.verify(current_password, crm_user["password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        hashed = bcrypt.hash(new_password)
        await current_db.crm_users.update_one(
            {"email": user["email"]},
            {"$set": {"password": hashed, "updated_at": datetime.now(timezone.utc)}}
        )
        try:
            await log_audit_event(user, "password_changed", "user", user["email"])
        except Exception:
            pass
        return {"success": True, "message": "Password changed"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Change own password error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/users/{user_id}/change-password")
async def change_user_password(user_id: str, data: Dict = Body(...), admin: Dict = Depends(require_admin)):
    """Change user password (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        from passlib.hash import bcrypt
        new_password = data.get("password")
        
        if not new_password:
            raise HTTPException(status_code=400, detail="Password required")
        
        hashed_password = bcrypt.hash(new_password)
        result = await current_db.crm_users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": hashed_password, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            await log_audit_event(admin, "password_changed", "user", str(user_id))
        except Exception:
            pass
        return {"success": True, "message": "Password changed"}
    except Exception as e:
        logging.error(f"Change password error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ROLES ALIAS (for /api/crm/roles route)
# ==========================================

@router.get("/roles")
async def get_roles_alias(user: Dict = Depends(get_current_user)):
    """Alias for /rbac/roles - for frontend compatibility"""
    return await get_rbac_roles(user)


# ==========================================
# PIPELINE, ACTIVITIES, EMAILS ENDPOINTS
# ==========================================

@router.get("/pipeline")
async def get_pipeline_view(user: Dict = Depends(get_current_user)):
    """Get pipeline view with opportunities grouped by stage"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        pipeline = [
            {"$group": {
                "_id": "$stage",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$estimated_value"}
            }},
            {"$sort": {"_id": 1}}
        ]
        result = await current_db.opportunities.aggregate(pipeline).to_list(None)
        return {"success": True, "data": result}
    except Exception as e:
        logging.error(f"Pipeline view error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pipeline/opportunities/{opp_id}")
async def update_opportunity_pipeline_stage(
    opp_id: str,
    data: Dict[str, Any] = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Update opportunity stage from pipeline kanban view"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        update_fields = {"updated_at": datetime.now(timezone.utc)}
        if "stage" in data:
            update_fields["stage"] = data["stage"]
        if "estimated_value" in data:
            update_fields["estimated_value"] = data["estimated_value"]
        result = await current_db.opportunities.update_one(
            {"_id": ObjectId(opp_id)},
            {"$set": update_fields}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        return {"success": True, "message": "Stage updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/activities")
async def get_activities(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    type: Optional[str] = None,
    search: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Get CRM activities with pagination, optional type filter and search"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        query = {}
        if type:
            query["type"] = type
        if search:
            query["$or"] = [
                {"subject": {"$regex": search, "$options": "i"}},
                {"notes": {"$regex": search, "$options": "i"}}
            ]
        activities = await current_db.crm_activities.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await current_db.crm_activities.count_documents(query)

        for activity in activities:
            activity["_id"] = str(activity["_id"])

        return {"success": True, "data": activities, "activities": activities, "total": total, "skip": skip, "limit": limit}
    except Exception as e:
        logging.error(f"Activities error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emails/history")
async def get_email_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    lead_id: Optional[str] = None,
    user: Dict = Depends(get_current_user)
):
    """Get email history — reads from canonical 'emails' collection (status != draft),
    with fallback to legacy 'email_history' collection for older records."""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        query = {"status": {"$ne": "draft"}}
        if lead_id:
            query["lead_id"] = lead_id

        emails = await current_db.emails.find(query).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await current_db.emails.count_documents(query)

        # Fallback: also fetch legacy email_history records not already present
        if not emails:
            legacy_query = {}
            if lead_id:
                legacy_query["lead_id"] = lead_id
            emails = await current_db.email_history.find(legacy_query).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
            total = await current_db.email_history.count_documents(legacy_query)

        for email in emails:
            email["_id"] = str(email["_id"])

        return {"success": True, "emails": emails, "data": emails, "total": total, "skip": skip, "limit": limit}
    except Exception as e:
        logging.error(f"Email history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD NOTES (required by frontend)
# ==========================================

@router.get("/leads/{lead_id}/notes")
async def get_lead_notes(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], user: Dict = Depends(get_current_user)):
    """Get notes for a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        notes = await current_db.notes.find({"lead_id": lead_id}).sort("created_at", -1).to_list(100)
        
        for note in notes:
            note["_id"] = str(note["_id"])
            note["id"] = note["_id"]
        
        return {"notes": notes, "total": len(notes)}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/notes")
async def add_lead_note(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], note_data: NoteCreate, user: Dict = Depends(get_current_user)):
    """Add a note to a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        new_note = {
            "lead_id": lead_id,
            "note_text": note_data.text,
            "content": note_data.text,
            "created_by": user["email"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.notes.insert_one(new_note)
        
        return {"message": "Note added", "note_id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error adding lead note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD CONVERSION (required by frontend)
# ==========================================

@router.post("/leads/{lead_id}/convert-to-contact")
async def convert_lead_to_contact(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], user: Dict = Depends(get_current_user)):
    """Convert a lead to a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Check if already converted
        if lead.get("status", "").lower() == "converted":
            raise HTTPException(status_code=400, detail="Lead already converted")
        
        # Check minimum required fields
        email = lead.get("email")
        name = lead.get("contact_name") or lead.get("name") or lead.get("brand_name")
        
        if not email and not name:
            raise HTTPException(status_code=400, detail="Lead must have at least email or name to be converted")
        
        # Create contact from lead
        new_contact = {
            "email": email or "",
            "name": name or email or "Unknown",
            "phone": lead.get("phone", ""),
            "company": lead.get("brand_name", ""),
            "position": "",
            "tags": lead.get("tags", []),
            "source": "converted_lead",
            "source_lead_id": lead_id,
            "language": lead.get("language", "fr"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"]
        }
        
        result = await current_db.contacts.insert_one(new_contact)
        contact_id = str(result.inserted_id)
        
        # Update lead status to CONVERTED
        await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {
                "$set": {
                    "status": "CONVERTED",
                    "converted_at": datetime.now(timezone.utc),
                    "converted_contact_id": contact_id,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Log activity
        try:
            await log_audit_event(
                user, "lead_converted", "lead", lead_id,
                details={"contact_id": contact_id}
            )
        except Exception:
            pass
        
        return {
            "message": "Lead converted to contact successfully",
            "contact_id": contact_id,
            "lead_id": lead_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error converting lead to contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD ASSIGNMENT (required by frontend)
# ==========================================

@router.post("/leads/{lead_id}/assign")
async def assign_lead(lead_id: Annotated[str, Path(pattern=r"^[a-f0-9]{24}$")], assign_data: dict, user: Dict = Depends(get_current_user)):
    """Assign a lead to a commercial"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        commercial_email = assign_data.get("commercial_email")
        if not commercial_email:
            raise HTTPException(status_code=400, detail="commercial_email is required")
        
        await current_db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {
                "$set": {
                    "assigned_to": commercial_email,
                    "assigned_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return {"message": "Lead assigned successfully", "assigned_to": commercial_email}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error assigning lead: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ACTIVITIES CRUD (create, update, delete)
# ==========================================

@router.post("/activities")
async def create_activity(activity_data: dict, user: Dict = Depends(get_current_user)):
    """Create a new CRM activity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        new_activity = {
            **activity_data,
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": activity_data.get("status", "pending"),
        }
        result = await current_db.crm_activities.insert_one(new_activity)
        new_activity["_id"] = str(result.inserted_id)
        new_activity["id"] = new_activity["_id"]
        return {"success": True, "activity": new_activity, "id": new_activity["_id"]}
    except Exception as e:
        logging.error(f"Error creating activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/activities/{activity_id}")
async def update_activity(activity_id: str, update_data: dict, user: Dict = Depends(get_current_user)):
    """Update an existing CRM activity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        update_data.pop("_id", None)
        update_data["updated_at"] = datetime.now(timezone.utc)
        result = await current_db.crm_activities.update_one(
            {"_id": ObjectId(activity_id)},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Activity not found")
        return {"success": True, "message": "Activity updated"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/activities/{activity_id}")
async def delete_activity(activity_id: str, user: Dict = Depends(get_current_user)):
    """Delete a CRM activity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        result = await current_db.crm_activities.delete_one({"_id": ObjectId(activity_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Activity not found")
        return {"success": True, "message": "Activity deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACTS - ACTIVITIES & EMAILS
# ==========================================

@router.get("/contacts/{contact_id}/activities")
async def get_contact_activities(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get all activities for a specific contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        activities = await current_db.crm_activities.find(
            {"contact_id": contact_id}
        ).sort("created_at", -1).to_list(100)
        for act in activities:
            act["_id"] = str(act["_id"])
            act["id"] = act["_id"]
        return {"activities": activities, "total": len(activities)}
    except Exception as e:
        logging.error(f"Error fetching contact activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts/{contact_id}/activities")
async def create_contact_activity(contact_id: str, activity_data: dict, user: Dict = Depends(get_current_user)):
    """Create an activity linked to a specific contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        new_activity = {
            **activity_data,
            "contact_id": contact_id,
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        result = await current_db.crm_activities.insert_one(new_activity)
        new_activity["_id"] = str(result.inserted_id)
        new_activity["id"] = new_activity["_id"]
        return {"success": True, "activity": new_activity, "id": new_activity["_id"]}
    except Exception as e:
        logging.error(f"Error creating contact activity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contacts/{contact_id}/emails")
async def get_contact_emails(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get all emails for a specific contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        # Get contact to find email address
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        query = {"contact_id": contact_id}
        if contact and contact.get("email"):
            query = {"$or": [{"contact_id": contact_id}, {"recipient_email": contact["email"]}]}

        emails = await current_db.email_history.find(query).sort("sent_at", -1).to_list(100)
        for email in emails:
            email["_id"] = str(email["_id"])
            email["id"] = email["_id"]
        return {"emails": emails, "total": len(emails)}
    except Exception as e:
        logging.error(f"Error fetching contact emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITIES - NOTES & ACTIVITIES
# ==========================================

@router.get("/opportunities/{opp_id}/notes")
async def get_opportunity_notes(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get notes for an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        notes = await current_db.notes.find(
            {"opportunity_id": opp_id}
        ).sort("created_at", -1).to_list(100)
        for note in notes:
            note["_id"] = str(note["_id"])
            note["id"] = note["_id"]
        return {"notes": notes, "total": len(notes)}
    except Exception as e:
        logging.error(f"Error fetching opportunity notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opp_id}/notes")
async def create_opportunity_note(opp_id: str, note_data: NoteCreate, user: Dict = Depends(get_current_user)):
    """Add a note to an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        new_note = {
            "opportunity_id": opp_id,
            "content": note_data.text,
            "author": user["email"],
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
        }
        result = await current_db.notes.insert_one(new_note)
        return {"message": "Note added", "note_id": str(result.inserted_id)}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating opportunity note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/opportunities/{opp_id}/activities")
async def get_opportunity_activities(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get activities for an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        activities = await current_db.crm_activities.find(
            {"opportunity_id": opp_id}
        ).sort("created_at", -1).to_list(100)
        for act in activities:
            act["_id"] = str(act["_id"])
            act["id"] = act["_id"]
        return {"activities": activities, "total": len(activities)}
    except Exception as e:
        logging.error(f"Error fetching opportunity activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EMAILS - DELETE
# ==========================================

@router.delete("/emails/{email_id}")
async def delete_email(email_id: str, user: Dict = Depends(get_current_user)):
    """Delete an email from canonical emails collection (with legacy email_history fallback)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    try:
        # Try primary emails collection first
        result = await current_db.emails.delete_one({"_id": ObjectId(email_id)})
        if result.deleted_count == 0:
            # Fallback to legacy email_history collection
            result = await current_db.email_history.delete_one({"_id": ObjectId(email_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Email not found")
        # Also remove from email_history mirror if present
        await current_db.email_history.delete_one({"email_id": email_id})
        return {"success": True, "message": "Email deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


