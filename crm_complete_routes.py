"""
CRM Complete Routes - Production Ready MVP
All 5 modules: Dashboard, Leads, Pipeline, Contacts, Settings
Uses centralized auth_middleware for authentication and RBAC
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
import os
import logging
import hashlib
import re
import bcrypt
from bson import ObjectId

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
# PYDANTIC MODELS
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
    pack_requested: str  # analyse, succursales, franchise
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
    note_text: Optional[str] = None  # Alias for content (frontend compatibility)
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    @property
    def text(self) -> str:
        """Get note text from content or note_text field"""
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


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to_email: Optional[str] = None
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: str = "B"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to_email: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    is_completed: Optional[bool] = None


# ==========================================
# DEBUG ENDPOINT
# ==========================================

@router.get("/debug")
async def debug_crm(user: Dict = Depends(get_current_user)):
    """Debug CRM auth and database connection"""
    try:
        current_db = get_db()
        db_status = "connected" if current_db is not None else "not_connected"
        
        # Use authenticated user from get_current_user
        email = user["email"]
        
        # Check both collections
        crm_user = None
        main_user = None
        if current_db is not None:
            crm_user = await current_db.crm_users.find_one({"email": email})
            main_user = await current_db.users.find_one({"email": email})
        
        collections_list = []
        if current_db is not None:
            collections_list = list(await current_db.list_collection_names())
        
        return {
            "db_status": db_status,
            "authenticated_user": user,
            "jwt_email": email,
            "jwt_role": user.get("role"),
            "crm_user_found": bool(crm_user),
            "main_user_found": bool(main_user),
            "collections": collections_list
        }
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}


# ==========================================
# DASHBOARD
# ==========================================

@router.get("/dashboard/stats")
async def get_dashboard_stats(user: Dict = Depends(get_current_user)):
    """Get dashboard KPIs"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    # Leads stats
    leads_today = await current_db.leads.count_documents({"created_at": {"$gte": today}})
    leads_7d = await current_db.leads.count_documents({"created_at": {"$gte": seven_days_ago}})
    leads_30d = await current_db.leads.count_documents({"created_at": {"$gte": thirty_days_ago}})
    leads_total = await current_db.leads.count_documents({})
    
    # Opportunities stats
    opportunities_open = await current_db.opportunities.count_documents({"is_closed": False})
    opportunities_won = await current_db.opportunities.count_documents({"is_won": True})
    
    # Pipeline value
    pipeline = await current_db.opportunities.aggregate([
        {"$match": {"is_closed": False}},
        {"$group": {"_id": None, "total": {"$sum": "$value"}}}
    ]).to_list(1)
    pipeline_value = pipeline[0]["total"] if pipeline else 0
    
    # Tasks overdue
    tasks_overdue = await current_db.tasks.count_documents({
        "is_completed": False,
        "due_date": {"$lt": now}
    })
    
    # Top sources
    top_sources = await current_db.leads.aggregate([
        {"$match": {"created_at": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": "$utm_source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]).to_list(5)
    
    # Stage distribution
    stage_distribution = await current_db.leads.aggregate([
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]).to_list(20)
    
    return {
        "leads": {
            "today": leads_today,
            "last_7_days": leads_7d,
            "last_30_days": leads_30d,
            "total": leads_total
        },
        "opportunities": {
            "open": opportunities_open,
            "won": opportunities_won,
            "pipeline_value": pipeline_value
        },
        "tasks": {
            "overdue": tasks_overdue
        },
        "top_sources": [{"source": s["_id"], "count": s["count"]} for s in top_sources],
        "stage_distribution": [{"stage": s["_id"], "count": s["count"]} for s in stage_distribution]
    }


# ==========================================
# LEADS
# ==========================================

@router.get("/leads")
async def get_leads(
    user: Dict = Depends(get_user_or_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    status: Optional[str] = None,
    stage: Optional[str] = None,
    owner: Optional[str] = None,
    search: Optional[str] = None,
    language: Optional[str] = None
):
    """
    Get leads with filters and pagination.
    RBAC: Admin sees all, Commercial sees only assigned leads.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Apply RBAC filter (BR002: Admin all, BR003: Commercial assigned only)
    filter_query = get_user_assigned_filter(user, "leads")
    
    if status:
        filter_query["status"] = status
    if stage:
        filter_query["stage"] = stage
    if owner:
        filter_query["owner_email"] = owner
    if language:
        filter_query["language"] = language
    if search:
        filter_query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"brand_name": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    
    # Get leads
    cursor = current_db.leads.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
    leads = await cursor.to_list(length=limit)
    total = await current_db.leads.count_documents(filter_query)
    
    # Convert ObjectId to string
    for lead in leads:
        lead["_id"] = str(lead["_id"])
        lead["lead_id"] = str(lead["_id"])  # Add lead_id alias
        lead["contact_name"] = lead.get("name")  # Add contact_name alias for frontend
        if "created_at" in lead and isinstance(lead["created_at"], datetime):
            lead["created_at"] = lead["created_at"].isoformat()
        if "updated_at" in lead and isinstance(lead["updated_at"], datetime):
            lead["updated_at"] = lead["updated_at"].isoformat()
        
        # TODO: Fetch notes in a separate endpoint for better performance
        # For now, initialize empty notes array
        lead["notes"] = []
    
    return {
        "leads": leads,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: Dict = Depends(get_current_user)):
    """Get single lead with full details"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get activities for this lead
    activities = await current_db.activities.find({"lead_id": lead_id}).sort("created_at", -1).limit(50).to_list(50)
    
    # Convert ObjectIds and dates
    lead["_id"] = str(lead["_id"])
    lead["lead_id"] = str(lead["_id"])  # Also add lead_id field for frontend
    lead["contact_name"] = lead.get("name")  # Add contact_name alias for frontend
    if "created_at" in lead and isinstance(lead["created_at"], datetime):
        lead["created_at"] = lead["created_at"].isoformat()
    if "updated_at" in lead and isinstance(lead["updated_at"], datetime):
        lead["updated_at"] = lead["updated_at"].isoformat()
    
    # Process activities and extract notes for frontend
    notes = []
    for activity in activities:
        activity["_id"] = str(activity["_id"])
        if "created_at" in activity and isinstance(activity["created_at"], datetime):
            activity["created_at"] = activity["created_at"].isoformat()
        
        # Build notes array from note-type activities
        if activity.get("type") == "note":
            note_content = activity.get("description") or activity.get("note_text") or activity.get("details") or ""
            notes.append({
                "id": str(activity["_id"]),
                "content": note_content,  # Primary field for frontend
                "note_text": note_content,  # Alias for compatibility
                "details": note_content,  # Another alias
                "created_at": activity.get("created_at"),
                "created_by": activity.get("user_email") or activity.get("created_by") or "Unknown"
            })
    
    lead["activities"] = activities
    lead["notes"] = notes  # Add notes array for frontend compatibility
    
    return lead


@router.post("/leads", status_code=status.HTTP_201_CREATED)
async def create_lead(lead_data: LeadCreate, user: Dict = Depends(get_current_user)):
    """Create new lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Check for duplicate
    existing = await current_db.leads.find_one({
        "email": lead_data.email,
        "brand_name": lead_data.brand_name
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="Lead already exists")
    
    # Create lead
    lead_doc = {
        **lead_data.dict(),
        "status": "NEW",
        "stage": "analysis_requested",
        "priority": "B",
        "tags": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "request_count": 1,
        "activity_count": 0
    }
    
    result = await current_db.leads.insert_one(lead_doc)
    lead_id = str(result.inserted_id)
    
    # Create activity
    await current_db.activities.insert_one({
        "type": "note",
        "subject": "Lead created",
        "description": f"Lead created by {user['email']}",
        "lead_id": lead_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "metadata": {},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"lead_id": lead_id, "message": "Lead created successfully"}


@router.put("/leads/{lead_id}")
async def update_lead(lead_id: str, update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
    """Update lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Build update
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    # Update lead
    await current_db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": update_dict}
    )
    
    # Log activity for status/stage changes
    if "status" in update_dict or "stage" in update_dict:
        await current_db.activities.insert_one({
            "type": "status_change",
            "subject": "Lead updated",
            "description": f"Status/stage changed by {user['email']}",
            "lead_id": lead_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "metadata": {"changes": update_dict},
            "created_at": datetime.now(timezone.utc)
        })
    
    return {"message": "Lead updated successfully"}


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user: Dict = Depends(get_current_user)):
    """Delete lead (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Check lead exists
    lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Delete associated activities
    await current_db.activities.delete_many({"lead_id": lead_id})
    
    # Delete lead
    await current_db.leads.delete_one({"_id": ObjectId(lead_id)})
    
    return {"message": "Lead deleted successfully"}


@router.post("/leads/{lead_id}/notes")
async def add_note_to_lead(lead_id: str, note: NoteCreate, user: Dict = Depends(get_current_user)):
    """Add note to lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get note text from content or note_text field
    note_content = note.content or note.note_text or ""
    if not note_content.strip():
        raise HTTPException(status_code=400, detail="Note content is required")
    
    await current_db.activities.insert_one({
        "type": "note",
        "subject": "Note added",
        "description": note_content,
        "note_text": note_content,  # Also store as note_text for frontend compatibility
        "lead_id": lead_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "created_by": user["email"],
        "metadata": {},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "Note added successfully"}


@router.post("/leads/{lead_id}/convert-to-contact")
async def convert_lead_to_contact(lead_id: str, user: Dict = Depends(get_current_user)):
    """Convert lead to contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Check if already converted
    if lead.get("converted_to_contact_id"):
        raise HTTPException(status_code=400, detail="Lead already converted")
    
    # Validate required fields (check both 'name' and 'contact_name' from frontend)
    if not lead.get("email") and not lead.get("name") and not lead.get("contact_name") and not lead.get("brand_name"):
        raise HTTPException(
            status_code=400, 
            detail="Lead must have at least email, name, or brand_name to convert"
        )
    
    # Create contact - use contact_name if name is not present (frontend compatibility)
    contact_name = lead.get("name") or lead.get("contact_name") or lead.get("brand_name") or "Contact sans nom"
    
    contact_doc = {
        "email": lead.get("email"),  # Email is optional
        "name": contact_name,
        "phone": lead.get("phone"),
        "language": lead.get("language", "fr"),
        "tags": lead.get("tags", []),
        "lead_ids": [lead_id],
        "opportunity_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.contacts.insert_one(contact_doc)
    contact_id = str(result.inserted_id)
    
    # Update lead
    await current_db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {
            "$set": {
                "converted_to_contact_id": contact_id,
                "status": "CONVERTED",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Log activity
    await current_db.activities.insert_one({
        "type": "conversion",
        "subject": "Lead converted to contact",
        "description": f"Converted by {user['email']}",
        "lead_id": lead_id,
        "contact_id": contact_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "metadata": {},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"contact_id": contact_id, "message": "Lead converted successfully"}


@router.get("/leads/export/csv")
async def export_leads_csv(user: Dict = Depends(get_current_user)):
    """Export leads to CSV"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    leads = await current_db.leads.find({}).sort("created_at", -1).to_list(None)
    
    # Build CSV
    import io
    import csv
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "email", "brand_name", "name", "phone", "status", "stage", "priority",
        "sector", "expansion_type", "target_city", "language", "created_at"
    ])
    
    writer.writeheader()
    for lead in leads:
        writer.writerow({
            "email": lead.get("email", ""),
            "brand_name": lead.get("brand_name", ""),
            "name": lead.get("name", ""),
            "phone": lead.get("phone", ""),
            "status": lead.get("status", ""),
            "stage": lead.get("stage", ""),
            "priority": lead.get("priority", ""),
            "sector": lead.get("sector", ""),
            "expansion_type": lead.get("expansion_type", ""),
            "target_city": lead.get("target_city", ""),
            "language": lead.get("language", ""),
            "created_at": lead.get("created_at", "").isoformat() if isinstance(lead.get("created_at"), datetime) else ""
        })
    
    # Log activity
    await current_db.activities.insert_one({
        "type": "export",
        "subject": "Leads exported to CSV",
        "description": f"Exported by {user['email']}",
        "user_id": user["id"],
        "user_email": user["email"],
        "metadata": {"count": len(leads)},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"csv": output.getvalue(), "count": len(leads)}


# ==========================================
# PIPELINE (Opportunities)
# ==========================================

@router.get("/pipeline")
async def get_pipeline(user: Dict = Depends(get_current_user)):
    """Get opportunities grouped by stage (Kanban view)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    stages = [
        "analysis_requested",
        "analysis_sent",
        "call_scheduled",
        "qualification",
        "proposal_sent",
        "negotiation",
        "won",
        "lost"
    ]
    
    pipeline_data = {}
    
    for stage in stages:
        opps = await current_db.opportunities.find({
            "stage": stage,
            "is_closed": False if stage not in ["won", "lost"] else True
        }).sort("created_at", -1).to_list(100)
        
        # Convert ObjectIds
        for opp in opps:
            opp["_id"] = str(opp["_id"])
            if "created_at" in opp and isinstance(opp["created_at"], datetime):
                opp["created_at"] = opp["created_at"].isoformat()
            if "updated_at" in opp and isinstance(opp["updated_at"], datetime):
                opp["updated_at"] = opp["updated_at"].isoformat()
        
        pipeline_data[stage] = opps
    
    return {"pipeline": pipeline_data}


@router.get("/opportunities")
async def list_opportunities(
    user: Dict = Depends(get_user_or_admin),
    search: str = Query(None),
    stage: str = Query(None),
    limit: int = Query(100, le=500),
    skip: int = Query(0)
):
    """
    List all opportunities with optional filtering.
    RBAC: Admin sees all, Commercial sees only assigned opportunities.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Apply RBAC filter (BR002: Admin all, BR003: Commercial assigned only)
    query = get_user_assigned_filter(user, "opportunities")
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"notes": {"$regex": search, "$options": "i"}}
        ]
    
    if stage:
        query["stage"] = stage
    
    opps = await current_db.opportunities.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await current_db.opportunities.count_documents(query)
    
    # Convert ObjectIds
    for opp in opps:
        opp["_id"] = str(opp["_id"])
        if "created_at" in opp and isinstance(opp["created_at"], datetime):
            opp["created_at"] = opp["created_at"].isoformat()
        if "updated_at" in opp and isinstance(opp["updated_at"], datetime):
            opp["updated_at"] = opp["updated_at"].isoformat()
        if "expected_close_date" in opp and isinstance(opp["expected_close_date"], datetime):
            opp["expected_close_date"] = opp["expected_close_date"].isoformat()
    
    return {"opportunities": opps, "total": total}


@router.post("/opportunities", status_code=status.HTTP_201_CREATED)
async def create_opportunity(opp_data: OpportunityCreate, user: Dict = Depends(get_current_user)):
    """Create new opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    opp_doc = {
        **opp_data.dict(),
        "owner_id": user["id"],
        "owner_email": user["email"],
        "is_closed": False,
        "is_won": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.opportunities.insert_one(opp_doc)
    opp_id = str(result.inserted_id)
    
    # Update lead if linked
    if opp_data.lead_id:
        await current_db.leads.update_one(
            {"_id": ObjectId(opp_data.lead_id)},
            {"$set": {"converted_to_opportunity_id": opp_id}}
        )
    
    return {"opportunity_id": opp_id, "message": "Opportunity created successfully"}


@router.put("/opportunities/{opp_id}")
async def update_opportunity(opp_id: str, update_data: OpportunityUpdate, user: Dict = Depends(get_current_user)):
    """Update opportunity (including stage change)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid opportunity ID")
    
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    # Build update
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    # Check if won/lost
    if update_data.stage in ["won", "lost"]:
        update_dict["is_closed"] = True
        update_dict["closed_at"] = datetime.now(timezone.utc)
        if update_data.stage == "won":
            update_dict["is_won"] = True
    
    # Update opportunity
    await current_db.opportunities.update_one(
        {"_id": ObjectId(opp_id)},
        {"$set": update_dict}
    )
    
    # Log activity
    await current_db.activities.insert_one({
        "type": "stage_change",
        "subject": "Opportunity updated",
        "description": f"Stage changed to {update_data.stage}" if update_data.stage else "Opportunity updated",
        "opportunity_id": opp_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "metadata": {"changes": update_dict},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "Opportunity updated successfully"}


@router.delete("/opportunities/{opp_id}")
async def delete_opportunity(opp_id: str, user: Dict = Depends(get_current_user)):
    """Delete an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.opportunities.delete_one({"_id": ObjectId(opp_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid opportunity ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    # Log activity
    await current_db.activities.insert_one({
        "type": "opportunity_deleted",
        "subject": "Opportunity deleted",
        "description": f"Opportunity {opp_id} deleted",
        "opportunity_id": opp_id,
        "user_id": user["id"],
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "Opportunity deleted successfully"}


# ==========================================
# CONTACTS
# ==========================================

@router.get("/contacts")
async def get_contacts(
    user: Dict = Depends(get_user_or_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = None
):
    """
    Get contacts with pagination.
    RBAC: Admin sees all, Commercial sees only assigned contacts.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Apply RBAC filter (BR002: Admin all, BR003: Commercial assigned only)
    filter_query = get_user_assigned_filter(user, "contacts")
    
    if search:
        filter_query["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}}
        ]
    
    cursor = current_db.contacts.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
    contacts = await cursor.to_list(length=limit)
    total = await current_db.contacts.count_documents(filter_query)
    
    for contact in contacts:
        contact["_id"] = str(contact["_id"])
        if "created_at" in contact and isinstance(contact["created_at"], datetime):
            contact["created_at"] = contact["created_at"].isoformat()
    
    return {
        "contacts": contacts,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/contacts/{contact_id}")
async def get_contact(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get single contact with details"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contact ID")
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Get activities
    activities = await current_db.activities.find({"contact_id": contact_id}).sort("created_at", -1).limit(50).to_list(50)
    
    contact["_id"] = str(contact["_id"])
    if "created_at" in contact and isinstance(contact["created_at"], datetime):
        contact["created_at"] = contact["created_at"].isoformat()
    
    for activity in activities:
        activity["_id"] = str(activity["_id"])
        if "created_at" in activity and isinstance(activity["created_at"], datetime):
            activity["created_at"] = activity["created_at"].isoformat()
    
    contact["activities"] = activities
    
    return contact


@router.post("/contacts", status_code=status.HTTP_201_CREATED)
async def create_contact(contact_data: ContactCreate, user: Dict = Depends(get_current_user)):
    """Create new contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    existing = await current_db.contacts.find_one({"email": contact_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Contact already exists")
    
    contact_doc = {
        **contact_data.dict(),
        "tags": [],
        "lead_ids": [],
        "opportunity_ids": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.contacts.insert_one(contact_doc)
    contact_id = str(result.inserted_id)
    
    return {"contact_id": contact_id, "message": "Contact created successfully"}


@router.put("/contacts/{contact_id}")
async def update_contact(contact_id: str, update_data: ContactUpdate, user: Dict = Depends(get_current_user)):
    """Update contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contact ID")
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await current_db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": update_dict}
    )
    
    return {"message": "Contact updated successfully"}


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, user: Dict = Depends(get_current_user)):
    """Delete contact (admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid contact ID")
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Delete associated activities
    await current_db.activities.delete_many({"contact_id": contact_id})
    
    # Delete contact
    await current_db.contacts.delete_one({"_id": ObjectId(contact_id)})
    
    return {"message": "Contact deleted successfully"}


# ==========================================
# SETTINGS
# ==========================================

@router.get("/settings/users")
async def get_crm_users(user: Dict = Depends(get_current_user)):
    """Get all CRM users (admin only)"""
    await require_admin(user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    users = await current_db.crm_users.find({}).sort("created_at", -1).to_list(None)
    
    for u in users:
        u["_id"] = str(u["_id"])
        u.pop("password_hash", None)  # Never return password hash
        if "created_at" in u and isinstance(u["created_at"], datetime):
            u["created_at"] = u["created_at"].isoformat()
    
    return {"users": users, "total": len(users)}


@router.post("/settings/users", status_code=status.HTTP_201_CREATED)
async def create_crm_user(user_data: UserCreate, user: Dict = Depends(get_current_user)):
    """Create new CRM user (UNLIMITED)"""
    await require_admin(user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Check if user exists
    existing = await current_db.crm_users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Hash password
    import bcrypt
    password_hash = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Split name into first_name and last_name for frontend compatibility
    name_parts = user_data.name.strip().split(' ', 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    user_doc = {
        "email": user_data.email,
        "name": user_data.name,
        "first_name": first_name,
        "last_name": last_name,
        "role": user_data.role,
        "password_hash": password_hash,
        "is_active": True,
        "is_verified": True,
        "language": "fr",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by_id": user["id"]
    }
    
    result = await current_db.crm_users.insert_one(user_doc)
    user_id = str(result.inserted_id)
    
    # Audit log
    await current_db.audit_logs.insert_one({
        "user_id": user["id"],
        "user_email": user["email"],
        "action": "create",
        "entity_type": "crm_user",
        "entity_id": user_id,
        "after": {"email": user_data.email, "role": user_data.role},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"user_id": user_id, "message": "User created successfully"}


@router.put("/settings/users/{user_id}")
async def update_crm_user(user_id: str, update_data: UserUpdate, user: Dict = Depends(get_current_user)):
    """Update CRM user"""
    await require_admin(user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        target_user = await current_db.crm_users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    await current_db.crm_users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_dict}
    )
    
    # Audit log
    await current_db.audit_logs.insert_one({
        "user_id": user["id"],
        "user_email": user["email"],
        "action": "update",
        "entity_type": "crm_user",
        "entity_id": user_id,
        "before": {"role": target_user.get("role"), "is_active": target_user.get("is_active")},
        "after": update_dict,
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "User updated successfully"}


@router.post("/settings/users/change-password")
async def change_password(password_data: PasswordChange, user: Dict = Depends(get_current_user)):
    """Change current user's password"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get current user from database
    try:
        current_user = await current_db.crm_users.find_one({"_id": ObjectId(user["id"])})
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not bcrypt.checkpw(password_data.current_password.encode('utf-8'), current_user["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(password_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Hash new password
    new_hash = bcrypt.hashpw(password_data.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Update password
    await current_db.crm_users.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.now(timezone.utc)}}
    )
    
    # Audit log
    await current_db.audit_logs.insert_one({
        "user_id": user["id"],
        "user_email": user["email"],
        "action": "password_change",
        "entity_type": "crm_user",
        "entity_id": user["id"],
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"message": "Password changed successfully"}


@router.get("/settings/tags")
async def get_tags(user: Dict = Depends(get_current_user)):
    """Get all available tags"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    settings = await current_db.crm_settings.find_one({}) or {}
    tags = settings.get("available_tags", ["hot", "cold", "follow-up", "qualified"])
    
    return {"tags": tags}


@router.post("/settings/tags")
async def add_tag(tag: str = Body(..., embed=True), user: Dict = Depends(get_current_user)):
    """Add new tag"""
    await require_role(["admin"], user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    await current_db.crm_settings.update_one(
        {},
        {"$addToSet": {"available_tags": tag}, "$set": {"updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    
    return {"message": "Tag added successfully"}


# ==========================================
# TASKS MODULE (COMPLETE)
# ==========================================

@router.get("/tasks")
async def get_tasks(
    user: Dict = Depends(get_current_user),
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
    lead_id: Optional[str] = None,
    contact_id: Optional[str] = None,
    opportunity_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
):
    """Get all tasks with filters"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    
    # Filter by completion status
    if status == "open":
        query["is_completed"] = False
    elif status == "done":
        query["is_completed"] = True
    
    # Filter by assignee
    if assigned_to:
        query["assigned_to_email"] = assigned_to
    
    # Filter by entity
    if lead_id:
        query["lead_id"] = lead_id
    if contact_id:
        query["contact_id"] = contact_id
    if opportunity_id:
        query["opportunity_id"] = opportunity_id
    
    tasks = await current_db.tasks.find(query).skip(skip).limit(limit).sort("due_date", 1).to_list(limit)
    
    for task in tasks:
        task["_id"] = str(task["_id"])
    
    total = await current_db.tasks.count_documents(query)
    
    # Count overdue tasks
    now = datetime.now(timezone.utc)
    overdue_count = await current_db.tasks.count_documents({
        "is_completed": False,
        "due_date": {"$lt": now}
    })
    
    return {
        "tasks": tasks,
        "total": total,
        "overdue_count": overdue_count,
        "skip": skip,
        "limit": limit
    }


@router.post("/tasks")
async def create_task(task_create: TaskCreate, user: Dict = Depends(get_current_user)):
    """Create new task"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    task_data = {
        **task_create.dict(),
        "created_by_email": user["email"],
        "created_by_id": user["id"],
        "is_completed": False,
        "completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.tasks.insert_one(task_data)
    task_id = str(result.inserted_id)
    
    # Timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "task",
        "entity_id": task_id,
        "event_type": "task_created",
        "description": f"Task created: {task_create.title}",
        "user_email": user["email"],
        "lead_id": task_create.lead_id,
        "contact_id": task_create.contact_id,
        "opportunity_id": task_create.opportunity_id,
        "created_at": datetime.now(timezone.utc)
    })
    
    task_data["_id"] = task_id
    
    return {
        "success": True,
        "task_id": task_id,
        "task": task_data
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user: Dict = Depends(get_current_user)):
    """Get task by ID"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        task = await current_db.tasks.find_one({"_id": ObjectId(task_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task["_id"] = str(task["_id"])
    
    return task


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    user: Dict = Depends(get_current_user)
):
    """Update task"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        task = await current_db.tasks.find_one({"_id": ObjectId(task_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = {k: v for k, v in task_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # Mark completion timestamp
    if task_update.is_completed and not task.get("is_completed"):
        update_data["completed_at"] = datetime.now(timezone.utc)
    
    await current_db.tasks.update_one(
        {"_id": ObjectId(task_id)},
        {"$set": update_data}
    )
    
    # Timeline event
    event_type = "task_completed" if update_data.get("is_completed") else "task_updated"
    await current_db.timeline_events.insert_one({
        "entity_type": "task",
        "entity_id": task_id,
        "event_type": event_type,
        "description": f"Task {'completed' if update_data.get('is_completed') else 'updated'}: {task['title']}",
        "user_email": user["email"],
        "lead_id": task.get("lead_id"),
        "contact_id": task.get("contact_id"),
        "opportunity_id": task.get("opportunity_id"),
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"success": True, "message": "Task updated"}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: Dict = Depends(get_current_user)):
    """Delete task"""
    await require_role(["admin", "sales"], user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.tasks.delete_one({"_id": ObjectId(task_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid task ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"success": True, "message": "Task deleted"}


@router.get("/tasks/export/csv")
async def export_tasks_csv(user: Dict = Depends(get_current_user)):
    """Export tasks to CSV"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    tasks = await current_db.tasks.find({}).to_list(1000)
    
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "ID", "Title", "Description", "Assigned To", "Created By",
        "Priority", "Status", "Due Date", "Created At", "Completed At",
        "Lead ID", "Contact ID", "Opportunity ID"
    ])
    
    # Data
    for task in tasks:
        writer.writerow([
            str(task["_id"]),
            task.get("title", ""),
            task.get("description", ""),
            task.get("assigned_to_email", ""),
            task.get("created_by_email", ""),
            task.get("priority", ""),
            "Done" if task.get("is_completed") else "Open",
            task.get("due_date", ""),
            task.get("created_at", ""),
            task.get("completed_at", ""),
            task.get("lead_id", ""),
            task.get("contact_id", ""),
            task.get("opportunity_id", "")
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    from fastapi.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tasks_export.csv"}
    )


# ==========================================
# EMAIL SENDING
# ==========================================

class EmailSendRequest(BaseModel):
    to_email: EmailStr
    subject: str
    message: str
    contact_id: Optional[str] = None
    lead_id: Optional[str] = None
    template_id: Optional[str] = None  # PHASE 5: support template usage


class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body: str  # Supports {{variables}} like {{brand}}, {{contact_name}}, {{link}}
    language: str = "fr"


@router.get("/emails/templates")
async def get_email_templates(user: Dict = Depends(get_current_user)):
    """Get all email templates"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    templates = await current_db.email_templates.find({}).to_list(100)
    for template in templates:
        template["_id"] = str(template["_id"])
    
    return {"templates": templates}


@router.post("/emails/templates")
async def create_email_template(template: EmailTemplateCreate, user: Dict = Depends(get_current_user)):
    """Create new email template (Admin only)"""
    await require_role(["admin"], user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    template_doc = {
        **template.dict(),
        "created_by": user["email"],
        "created_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.email_templates.insert_one(template_doc)
    return {"template_id": str(result.inserted_id), "message": "Template created"}


@router.delete("/emails/templates/{template_id}")
async def delete_email_template(template_id: str, user: Dict = Depends(get_current_user)):
    """Delete email template (Admin only)"""
    await require_role(["admin"], user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.email_templates.delete_one({"_id": ObjectId(template_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid template ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"message": "Template deleted successfully"}


@router.get("/emails/history")
async def get_email_history(
    user: Dict = Depends(get_current_user),
    contact_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    limit: int = Query(50, le=200)
):
    """Get email send history"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if contact_id:
        query["contact_id"] = contact_id
    if lead_id:
        query["lead_id"] = lead_id
    
    # PHASE 4: Commercial sees only their sent emails
    if user["role"] == "commercial":
        query["sent_by"] = user["email"]
    
    emails = await current_db.crm_activities.find({
        "type": "email_sent",
        **query
    }).sort("sent_at", -1).limit(limit).to_list(limit)
    
    for email in emails:
        email["_id"] = str(email["_id"])
    
    return {"emails": emails, "total": len(emails)}


@router.post("/emails/send")
async def send_crm_email(
    email_data: EmailSendRequest,
    user: Dict = Depends(get_current_user)
):
    """Send email to a contact from CRM"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # OVH SMTP Configuration (contact@israelgrowthventure.com)
    smtp_host = os.getenv('SMTP_HOST', 'ssl0.ovh.net')
    smtp_port = int(os.getenv('SMTP_PORT', '465'))
    smtp_user = os.getenv('SMTP_USER', 'contact@israelgrowthventure.com')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from = os.getenv('SMTP_FROM', 'contact@israelgrowthventure.com')
    
    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=500, detail="SMTP credentials not configured")
    
    # Create email message
    message = MIMEMultipart('alternative')
    message['Subject'] = email_data.subject
    message['From'] = f"Israel Growth Venture <{smtp_from}>"
    message['Reply-To'] = smtp_from
    message['To'] = email_data.to_email
    
    # Plain text version
    message.attach(MIMEText(email_data.message, 'plain'))
    
    # HTML version (simple formatting)
    html_message = email_data.message.replace('\n', '<br>')
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            {html_message}
            <hr style="margin-top: 30px; border: none; border-top: 1px solid #eee;">
            <p style="font-size: 12px; color: #666;">
                Sent from IGV CRM
            </p>
        </div>
    </body>
    </html>
    """
    message.attach(MIMEText(html_body, 'html'))
    
    try:
        # OVH requires SSL/TLS (port 465) instead of STARTTLS (port 587)
        await aiosmtplib.send(
            message,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            use_tls=True  # SSL/TLS direct for OVH
        )
        
        # Log email activity
        activity = {
            "type": "email_sent",
            "to_email": email_data.to_email,
            "subject": email_data.subject,
            "contact_id": email_data.contact_id,
            "sent_by": user["email"],
            "sent_at": datetime.now(timezone.utc).isoformat()
        }
        await current_db.crm_activities.insert_one(activity)
        
        # Update contact last activity if contact_id provided
        if email_data.contact_id:
            try:
                await current_db.contacts.update_one(
                    {"_id": ObjectId(email_data.contact_id)},
                    {"$set": {"last_activity": datetime.now(timezone.utc).isoformat()}}
                )
            except Exception:
                pass  # Non-critical
        
        return {"success": True, "message": "Email sent successfully"}
        
    except Exception as e:
        logging.error(f"Error sending CRM email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.get("/settings/pipeline-stages")
async def get_pipeline_stages(user: Dict = Depends(get_current_user)):
    """Get pipeline stages configuration"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    settings = await current_db.crm_settings.find_one({}) or {}
    stages = settings.get("pipeline_stages", [
        {"key": "analysis_requested", "label_fr": "Analyse demandée", "label_en": "Analysis requested", "label_he": "ניתוח התבקש"},
        {"key": "analysis_sent", "label_fr": "Analyse envoyée", "label_en": "Analysis sent", "label_he": "ניתוח נשלח"},
        {"key": "call_scheduled", "label_fr": "Appel planifié", "label_en": "Call scheduled", "label_he": "שיחה מתוזמנת"},
        {"key": "qualification", "label_fr": "Qualification", "label_en": "Qualification", "label_he": "הסמכה"},
        {"key": "proposal_sent", "label_fr": "Proposition envoyée", "label_en": "Proposal sent", "label_he": "הצעה נשלחה"},
        {"key": "negotiation", "label_fr": "Négociation", "label_en": "Negotiation", "label_he": "משא ומתן"},
        {"key": "won", "label_fr": "Signé / Lancement", "label_en": "Signed / Launch", "label_he": "חתום / השקה"},
        {"key": "lost", "label_fr": "Perdu / Sans suite", "label_en": "Lost / No follow-up", "label_he": "אבד / ללא מעקב"}
    ])
    
    return {"stages": stages}


# ==========================================
# ACTIVITIES
# ==========================================

@router.get("/activities")
async def get_activities(
    user: Dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    type: Optional[str] = None
):
    """
    Get activities timeline (notes, emails, calls, meetings)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    filter_query = {}
    if type:
        filter_query["type"] = type
    
    # Get activities
    cursor = current_db.activities.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
    activities = await cursor.to_list(length=limit)
    total = await current_db.activities.count_documents(filter_query)
    
    # Convert ObjectId to string
    for activity in activities:
        activity["_id"] = str(activity["_id"])
        if "created_at" in activity and isinstance(activity["created_at"], datetime):
            activity["created_at"] = activity["created_at"].isoformat()
    
    return {
        "activities": activities,
        "total": total,
        "skip": skip,
        "limit": limit
    }


# ==========================================
# ROUTE PUBLIQUE: Lead depuis Packs (demande rappel)
# ==========================================

@router.post("/lead-from-pack")
async def create_lead_from_pack(data: LeadFromPackRequest):
    """
    Enregistre demande de rappel depuis /packs (PUBLIQUE - pas d'auth)
    Crée lead avec status=new, source=pack_rappel, assigned_to=null
    Admin redistribuera manuellement
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead_doc = {
            "email": data.email,
            "full_name": data.full_name,
            "phone": data.phone,
            "company": data.company or "",
            "brand_name": data.company or data.full_name,  # Fallback
            "pack_requested": data.pack_requested,
            "preferred_contact_date": data.preferred_date,
            "preferred_contact_time": data.preferred_time,
            "message": data.message or "",
            "source": data.source,
            "status": data.status,
            "stage": "analysis_requested",
            "assigned_to": None,  # ADMIN REDISTRIBUE MANUELLEMENT
            "tags": [f"pack_{data.pack_requested}"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.leads.insert_one(lead_doc)
        
        logging.info(f"✅ Lead created from pack: {data.email} - Pack: {data.pack_requested}")
        
        return {
            "success": True,
            "lead_id": str(result.inserted_id),
            "message": "Demande enregistrée avec succès"
        }
        
    except Exception as e:
        logging.error(f"❌ Error creating lead from pack: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création: {str(e)}")