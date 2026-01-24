"""
CRM Additional Routes - Phase 2 Fix (24/01/2026)
Endpoints manquants identifiés par l'audit
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging

# Import from main module
from auth_middleware import (
    get_current_user,
    require_admin,
    get_db
)

router = APIRouter(prefix="/api/crm")


# ==========================================
# PYDANTIC MODELS
# ==========================================

class NoteCreate(BaseModel):
    content: Optional[str] = None
    note_text: Optional[str] = None


class EmailDraftCreate(BaseModel):
    to_email: Optional[str] = None
    subject: str = ""
    message: str = ""
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None


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


# ==========================================
# PATCH LEAD (alias pour PUT)
# ==========================================

@router.patch("/leads/{lead_id}")
async def patch_lead(lead_id: str, update_data: LeadUpdate, user: Dict = Depends(get_current_user)):
    """
    PATCH lead - Permet de modifier status, stage, priority, tags, owner_email
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # RBAC: Commercial can only update their own leads
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
    if "status" in update_dict or "stage" in update_dict:
        await current_db.activities.insert_one({
            "type": "status_change",
            "subject": "Lead updated",
            "description": f"Status/stage changed by {user['email']}",
            "lead_id": lead_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "metadata": {"changes": {k: str(v) for k, v in update_dict.items()}},
            "created_at": datetime.now(timezone.utc)
        })
    
    return {"message": "Lead updated successfully"}


# ==========================================
# LEAD ACTIVITIES
# ==========================================

@router.get("/leads/{lead_id}/activities")
async def get_lead_activities(lead_id: str, user: Dict = Depends(get_current_user)):
    """Get all activities for a specific lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        activities = await current_db.activities.find(
            {"lead_id": lead_id}
        ).sort("created_at", -1).to_list(100)
        
        formatted = []
        for act in activities:
            formatted.append({
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
        
        return {"activities": formatted, "count": len(formatted), "lead_id": lead_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/activities")
async def add_lead_activity(lead_id: str, activity: Dict, user: Dict = Depends(get_current_user)):
    """Add an activity to a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        new_activity = {
            "lead_id": lead_id,
            "type": activity.get("type", "note"),
            "description": activity.get("description", ""),
            "subject": activity.get("subject", ""),
            "created_at": datetime.utcnow(),
            "created_by": user.get("email", "unknown"),
            "user_email": user.get("email", "unknown"),
            "metadata": activity.get("metadata", {})
        }
        
        result = await current_db.activities.insert_one(new_activity)
        new_activity["_id"] = str(result.inserted_id)
        new_activity["id"] = str(result.inserted_id)
        new_activity["created_at"] = new_activity["created_at"].isoformat()
        
        return {"message": "Activity added", "activity": new_activity}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD EMAILS
# ==========================================

@router.get("/leads/{lead_id}/emails")
async def get_lead_emails(lead_id: str, user: Dict = Depends(get_current_user)):
    """Get all emails for a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        emails = await current_db.crm_activities.find({
            "type": "email_sent",
            "$or": [
                {"lead_id": lead_id},
                {"to_email": lead.get("email")}
            ]
        }).sort("sent_at", -1).to_list(50)
        
        formatted = []
        for email in emails:
            formatted.append({
                "id": str(email["_id"]),
                "to_email": email.get("to_email", ""),
                "subject": email.get("subject", ""),
                "sent_by": email.get("sent_by", ""),
                "sent_at": email.get("sent_at", ""),
                "status": "sent"
            })
        
        return {"emails": formatted, "count": len(formatted), "lead_id": lead_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/emails/send")
async def send_lead_email(lead_id: str, email_data: Dict = Body(...), user: Dict = Depends(get_current_user)):
    """Send email to a lead"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Log as activity for now (actual send via main endpoint)
        await current_db.crm_activities.insert_one({
            "type": "email_sent",
            "to_email": email_data.get("to_email") or lead.get("email"),
            "subject": email_data.get("subject", ""),
            "lead_id": lead_id,
            "sent_by": user["email"],
            "sent_at": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True, "message": "Email logged (use main send endpoint for actual delivery)"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD CONVERT (alias)
# ==========================================

@router.post("/leads/{lead_id}/convert")
async def convert_lead_alias(lead_id: str, user: Dict = Depends(get_current_user)):
    """Alias for convert-to-contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    if lead.get("converted_to_contact_id"):
        raise HTTPException(status_code=400, detail="Lead already converted")
    
    # Create contact
    contact_name = lead.get("name") or lead.get("contact_name") or lead.get("brand_name") or "Contact"
    
    contact_doc = {
        "email": lead.get("email"),
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
        {"$set": {
            "converted_to_contact_id": contact_id,
            "status": "CONVERTED",
            "updated_at": datetime.now(timezone.utc)
        }}
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


# ==========================================
# CONTACT NOTES
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
        
        notes = await current_db.activities.find({
            "contact_id": contact_id,
            "type": "note"
        }).sort("created_at", -1).to_list(100)
        
        formatted = []
        for note in notes:
            content = note.get("description") or note.get("note_text") or ""
            formatted.append({
                "id": str(note["_id"]),
                "content": content,
                "note_text": content,
                "created_at": note["created_at"].isoformat() if isinstance(note.get("created_at"), datetime) else "",
                "created_by": note.get("user_email", "")
            })
        
        return {"notes": formatted, "count": len(formatted)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts/{contact_id}/notes")
async def add_contact_note(contact_id: str, note: NoteCreate, user: Dict = Depends(get_current_user)):
    """Add note to contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        content = note.content or note.note_text or ""
        if not content.strip():
            raise HTTPException(status_code=400, detail="Note content required")
        
        await current_db.activities.insert_one({
            "type": "note",
            "subject": "Note added",
            "description": content,
            "contact_id": contact_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Note added successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACT ACTIVITIES
# ==========================================

@router.get("/contacts/{contact_id}/activities")
async def get_contact_activities(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get activities for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        activities = await current_db.activities.find(
            {"contact_id": contact_id}
        ).sort("created_at", -1).to_list(100)
        
        formatted = []
        for act in activities:
            formatted.append({
                "id": str(act["_id"]),
                "type": act.get("type", "note"),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_by": act.get("created_by", act.get("user_email", "")),
                "created_at": act["created_at"].isoformat() if isinstance(act.get("created_at"), datetime) else ""
            })
        
        return {"activities": formatted, "count": len(formatted)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts/{contact_id}/activities")
async def add_contact_activity(contact_id: str, activity: Dict, user: Dict = Depends(get_current_user)):
    """Add an activity to a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        new_activity = {
            "contact_id": contact_id,
            "type": activity.get("type", "note"),
            "description": activity.get("description", ""),
            "subject": activity.get("subject", ""),
            "created_at": datetime.utcnow(),
            "created_by": user.get("email", "unknown"),
            "user_email": user.get("email", "unknown"),
            "metadata": activity.get("metadata", {})
        }
        
        result = await current_db.activities.insert_one(new_activity)
        new_activity["_id"] = str(result.inserted_id)
        new_activity["id"] = str(result.inserted_id)
        new_activity["created_at"] = new_activity["created_at"].isoformat()
        
        return {"message": "Activity added", "activity": new_activity}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACT EMAILS
# ==========================================

@router.get("/contacts/{contact_id}/emails")
async def get_contact_emails(contact_id: str, user: Dict = Depends(get_current_user)):
    """Get emails for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        emails = await current_db.crm_activities.find({
            "type": "email_sent",
            "$or": [
                {"contact_id": contact_id},
                {"to_email": contact.get("email")}
            ]
        }).sort("sent_at", -1).to_list(50)
        
        formatted = []
        for email in emails:
            formatted.append({
                "id": str(email["_id"]),
                "to_email": email.get("to_email", ""),
                "subject": email.get("subject", ""),
                "sent_by": email.get("sent_by", ""),
                "sent_at": email.get("sent_at", "")
            })
        
        return {"emails": formatted, "count": len(formatted)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITY DETAIL
# ==========================================

@router.get("/opportunities/{opp_id}")
async def get_opportunity_detail(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get opportunity details"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid opportunity ID")
    
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    
    # Get activities
    activities = await current_db.activities.find(
        {"opportunity_id": opp_id}
    ).sort("created_at", -1).to_list(50)
    
    opp["_id"] = str(opp["_id"])
    opp["id"] = str(opp["_id"])
    if isinstance(opp.get("created_at"), datetime):
        opp["created_at"] = opp["created_at"].isoformat()
    if isinstance(opp.get("updated_at"), datetime):
        opp["updated_at"] = opp["updated_at"].isoformat()
    if isinstance(opp.get("expected_close_date"), datetime):
        opp["expected_close_date"] = opp["expected_close_date"].isoformat()
    
    opp["activities"] = [{
        "id": str(a["_id"]),
        "type": a.get("type", ""),
        "description": a.get("description", ""),
        "created_at": a["created_at"].isoformat() if isinstance(a.get("created_at"), datetime) else ""
    } for a in activities]
    
    return opp


# ==========================================
# OPPORTUNITY NOTES
# ==========================================

@router.get("/opportunities/{opp_id}/notes")
async def get_opportunity_notes(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get notes for opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        notes = await current_db.activities.find({
            "opportunity_id": opp_id,
            "type": "note"
        }).sort("created_at", -1).to_list(100)
        
        formatted = []
        for note in notes:
            content = note.get("description") or note.get("note_text") or ""
            formatted.append({
                "id": str(note["_id"]),
                "content": content,
                "created_at": note["created_at"].isoformat() if isinstance(note.get("created_at"), datetime) else "",
                "created_by": note.get("user_email", "")
            })
        
        return {"notes": formatted, "count": len(formatted)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opportunities/{opp_id}/notes")
async def add_opportunity_note(opp_id: str, note: NoteCreate, user: Dict = Depends(get_current_user)):
    """Add note to opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        content = note.content or note.note_text or ""
        if not content.strip():
            raise HTTPException(status_code=400, detail="Note content required")
        
        await current_db.activities.insert_one({
            "type": "note",
            "subject": "Note added",
            "description": content,
            "opportunity_id": opp_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"message": "Note added successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITY ACTIVITIES
# ==========================================

@router.get("/opportunities/{opp_id}/activities")
async def get_opportunity_activities(opp_id: str, user: Dict = Depends(get_current_user)):
    """Get activities for opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        activities = await current_db.activities.find(
            {"opportunity_id": opp_id}
        ).sort("created_at", -1).to_list(100)
        
        formatted = []
        for act in activities:
            formatted.append({
                "id": str(act["_id"]),
                "type": act.get("type", ""),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_at": act["created_at"].isoformat() if isinstance(act.get("created_at"), datetime) else ""
            })
        
        return {"activities": formatted, "count": len(formatted)}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EMAIL DRAFTS
# ==========================================

@router.get("/emails/drafts")
async def get_email_drafts(user: Dict = Depends(get_current_user)):
    """Get email drafts for current user"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        drafts = await current_db.email_drafts.find({
            "user_email": user["email"]
        }).sort("updated_at", -1).to_list(50)
        
        formatted = []
        for draft in drafts:
            formatted.append({
                "id": str(draft["_id"]),
                "to_email": draft.get("to_email", ""),
                "subject": draft.get("subject", ""),
                "message": draft.get("message", ""),
                "lead_id": draft.get("lead_id"),
                "contact_id": draft.get("contact_id"),
                "created_at": draft["created_at"].isoformat() if isinstance(draft.get("created_at"), datetime) else "",
                "updated_at": draft["updated_at"].isoformat() if isinstance(draft.get("updated_at"), datetime) else ""
            })
        
        return {"drafts": formatted, "count": len(formatted)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emails/drafts")
async def create_email_draft(draft: EmailDraftCreate, user: Dict = Depends(get_current_user)):
    """Create email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        now = datetime.now(timezone.utc)
        draft_doc = {
            "to_email": draft.to_email or "",
            "subject": draft.subject,
            "message": draft.message,
            "lead_id": draft.lead_id,
            "contact_id": draft.contact_id,
            "user_email": user["email"],
            "created_at": now,
            "updated_at": now
        }
        
        result = await current_db.email_drafts.insert_one(draft_doc)
        
        return {"draft_id": str(result.inserted_id), "message": "Draft saved"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/emails/drafts/{draft_id}")
async def delete_email_draft(draft_id: str, user: Dict = Depends(get_current_user)):
    """Delete email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.email_drafts.delete_one({
            "_id": ObjectId(draft_id),
            "user_email": user["email"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        return {"message": "Draft deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS
# ==========================================

@router.get("/settings")
async def get_settings(user: Dict = Depends(get_current_user)):
    """Get CRM settings"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    settings = await current_db.crm_settings.find_one({}) or {}
    
    return {
        "available_tags": settings.get("available_tags", ["hot", "cold", "follow-up", "qualified"]),
        "default_language": settings.get("default_language", "fr"),
        "email_notifications": settings.get("email_notifications", True),
        "roles": ["admin", "commercial", "viewer", "technique"]
    }


@router.get("/settings/dispatch")
async def get_dispatch_settings(user: Dict = Depends(require_admin)):
    """Get dispatch settings (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Unassigned leads
    unassigned = await current_db.leads.find({
        "$or": [
            {"owner_email": None},
            {"owner_email": ""},
            {"assigned_to": None},
            {"assigned_to": ""}
        ]
    }).sort("created_at", -1).to_list(100)
    
    leads_list = []
    for lead in unassigned:
        leads_list.append({
            "id": str(lead["_id"]),
            "email": lead.get("email", ""),
            "brand_name": lead.get("brand_name", ""),
            "status": lead.get("status", "NEW"),
            "created_at": lead["created_at"].isoformat() if isinstance(lead.get("created_at"), datetime) else ""
        })
    
    # Commercial users
    commercials = await current_db.crm_users.find({
        "role": {"$in": ["commercial", "admin"]},
        "is_active": True
    }).to_list(50)
    
    users_list = [{"id": str(u["_id"]), "email": u.get("email", ""), "name": u.get("name", "")} for u in commercials]
    
    return {
        "unassigned_leads": leads_list,
        "unassigned_count": len(leads_list),
        "commercials": users_list
    }


@router.get("/settings/quality")
async def get_quality_settings(user: Dict = Depends(require_admin)):
    """Get data quality metrics (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Duplicates
    pipeline = [
        {"$group": {"_id": "$email", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$limit": 20}
    ]
    duplicates = await current_db.leads.aggregate(pipeline).to_list(20)
    
    # Missing fields
    missing_phone = await current_db.leads.count_documents({"$or": [{"phone": None}, {"phone": ""}]})
    missing_email = await current_db.leads.count_documents({"$or": [{"email": None}, {"email": ""}]})
    total = await current_db.leads.count_documents({})
    
    return {
        "duplicates": [{"email": d["_id"], "count": d["count"]} for d in duplicates],
        "incomplete": [
            {"type": "missing_phone", "count": missing_phone},
            {"type": "missing_email", "count": missing_email}
        ],
        "missing_phone": missing_phone,
        "missing_email": missing_email,
        "total_leads": total,
        "quality_score": round((1 - (missing_phone + missing_email) / max(total * 2, 1)) * 100, 1)
    }


@router.get("/settings/performance")
async def get_performance_stats(user: Dict = Depends(require_admin)):
    """Get performance stats (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    
    leads_30d = await current_db.leads.count_documents({"created_at": {"$gte": thirty_days_ago}})
    converted_30d = await current_db.leads.count_documents({
        "created_at": {"$gte": thirty_days_ago},
        "status": "CONVERTED"
    })
    opportunities_count = await current_db.opportunities.count_documents({}) if "opportunities" in await current_db.list_collection_names() else 0
    
    # Performance by commercial
    by_commercial = []
    commercials = await current_db.crm_users.find({"role": {"$in": ["commercial", "admin"]}}).to_list(50)
    for c in commercials:
        c_email = c.get("email", "")
        c_leads = await current_db.leads.count_documents({"owner_email": c_email})
        c_converted = await current_db.leads.count_documents({"owner_email": c_email, "status": "CONVERTED"})
        by_commercial.append({
            "email": c_email,
            "name": c.get("name", ""),
            "leads": c_leads,
            "converted": c_converted,
            "rate": round((c_converted / max(c_leads, 1)) * 100, 1)
        })
    
    return {
        "period": "30 days",
        "leads_this_month": leads_30d,
        "leads_converted": converted_30d,
        "conversion_rate": round((converted_30d / max(leads_30d, 1)) * 100, 1),
        "opportunities_count": opportunities_count,
        "by_commercial": by_commercial
    }


# ==========================================
# LEAD ASSIGNMENT (Admin only)
# ==========================================

class LeadAssignment(BaseModel):
    commercial_email: EmailStr


@router.post("/leads/{lead_id}/assign")
async def assign_lead_to_commercial(
    lead_id: str,
    assignment: LeadAssignment,
    user: Dict = Depends(require_admin)
):
    """Assign a lead to a commercial (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid lead ID")
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Verify commercial exists
    commercial = await current_db.admin_users.find_one({
        "email": assignment.commercial_email,
        "role": "commercial"
    })
    
    if not commercial:
        raise HTTPException(status_code=404, detail="Commercial user not found")
    
    # Update lead
    await current_db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$set": {
            "assigned_to": assignment.commercial_email,
            "assigned_at": datetime.now(timezone.utc),
            "assigned_by": user["email"],
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Log activity
    await current_db.activities.insert_one({
        "type": "assignment",
        "subject": "Lead assigned",
        "description": f"Lead assigned to {assignment.commercial_email} by {user['email']}",
        "lead_id": lead_id,
        "user_id": user.get("id", ""),
        "user_email": user["email"],
        "metadata": {"commercial_email": assignment.commercial_email},
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "message": "Lead assigned successfully",
        "lead_id": lead_id,
        "assigned_to": assignment.commercial_email
    }


# ==========================================
# MINI-ANALYSES LIST
# ==========================================

@router.get("/mini-analyses")
async def list_mini_analyses(
    user: Dict = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200)
):
    """List mini-analyses"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    filter_query = {
        "$or": [
            {"source": "mini-analyse"},
            {"source": "mini_analyse"},
            {"source": {"$regex": "mini", "$options": "i"}}
        ]
    }
    
    leads = await current_db.leads.find(filter_query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await current_db.leads.count_documents(filter_query)
    
    formatted = []
    for lead in leads:
        formatted.append({
            "id": str(lead["_id"]),
            "email": lead.get("email", ""),
            "brand_name": lead.get("brand_name", ""),
            "status": lead.get("status", "NEW"),
            "created_at": lead["created_at"].isoformat() if isinstance(lead.get("created_at"), datetime) else ""
        })
    
    return {"mini_analyses": formatted, "total": total}
