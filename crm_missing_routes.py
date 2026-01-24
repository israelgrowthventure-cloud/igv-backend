"""
CRM Missing Routes - All endpoints needed for complete CRM functionality
Implements: logout, lead activities, lead emails, contact notes/activities/emails,
opportunity details/notes/activities, drafts, settings dispatch/quality/performance
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging

from auth_middleware import (
    get_current_user,
    require_admin,
    require_role,
    get_db
)

router = APIRouter()


# ==========================================
# PYDANTIC MODELS
# ==========================================

class NoteCreate(BaseModel):
    content: Optional[str] = None
    note_text: Optional[str] = None
    
    @property
    def text(self) -> str:
        return self.content or self.note_text or ""


class EmailDraftCreate(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    lead_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None


class EmailDraftUpdate(BaseModel):
    to_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    body: Optional[str] = None


# ==========================================
# LOGOUT ENDPOINT
# ==========================================

@router.post("/api/admin/logout")
async def admin_logout(user: Dict = Depends(get_current_user)):
    """
    Logout endpoint - invalidates session (stateless: just confirms logout)
    Frontend should clear token on its side
    """
    logging.info(f"User {user['email']} logged out")
    return {"success": True, "message": "Logged out successfully"}


# ==========================================
# LEAD ACTIVITIES
# ==========================================

@router.get("/api/crm/leads/{lead_id}/activities")
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
        
        # Get activities from activities collection
        activities_cursor = current_db.activities.find({
            "lead_id": lead_id
        }).sort("created_at", -1).limit(limit)
        
        activities = await activities_cursor.to_list(limit)
        
        # Also get from crm_activities (email sends, etc.)
        crm_activities_cursor = current_db.crm_activities.find({
            "lead_id": lead_id
        }).sort("created_at", -1).limit(limit)
        
        crm_activities = await crm_activities_cursor.to_list(limit)
        
        # Merge and format
        all_activities = []
        
        for act in activities:
            all_activities.append({
                "id": str(act["_id"]),
                "type": act.get("type", "note"),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_at": act.get("created_at").isoformat() if isinstance(act.get("created_at"), datetime) else str(act.get("created_at", "")),
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
        
        return {"activities": all_activities[:limit], "total": len(all_activities)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD EMAILS
# ==========================================

@router.get("/api/crm/leads/{lead_id}/emails")
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
        # Verify lead exists
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Get emails from crm_activities
        emails_cursor = current_db.crm_activities.find({
            "lead_id": lead_id,
            "type": "email_sent"
        }).sort("sent_at", -1).limit(limit)
        
        emails = await emails_cursor.to_list(limit)
        
        formatted_emails = []
        for email in emails:
            formatted_emails.append({
                "id": str(email["_id"]),
                "to_email": email.get("to_email", ""),
                "subject": email.get("subject", ""),
                "body": email.get("body", ""),
                "sent_by": email.get("sent_by", ""),
                "sent_at": email.get("sent_at", ""),
                "status": email.get("status", "sent")
            })
        
        return {"emails": formatted_emails, "total": len(formatted_emails)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching lead emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/crm/leads/{lead_id}/emails/send")
async def send_lead_email(
    lead_id: str,
    email_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Send email to a lead - redirects to main email send with lead_id"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Verify lead exists and get email
        lead = await current_db.leads.find_one({"_id": ObjectId(lead_id)})
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # Use lead email if not provided
        to_email = email_data.get("to_email") or lead.get("email")
        if not to_email:
            raise HTTPException(status_code=400, detail="No email address found")
        
        # Store email activity (actual sending handled by main endpoint)
        email_record = {
            "type": "email_sent",
            "lead_id": lead_id,
            "to_email": to_email,
            "subject": email_data.get("subject", ""),
            "body": email_data.get("body", email_data.get("message", "")),
            "sent_by": user["email"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued"
        }
        
        result = await current_db.crm_activities.insert_one(email_record)
        
        # Log activity
        await current_db.activities.insert_one({
            "type": "email_sent",
            "subject": f"Email sent to {to_email}",
            "description": email_data.get("subject", ""),
            "lead_id": lead_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "email_id": str(result.inserted_id),
            "message": "Email queued for sending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending lead email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LEAD CONVERT ALIAS
# ==========================================

@router.post("/api/crm/leads/{lead_id}/convert")
async def convert_lead_alias(lead_id: str, user: Dict = Depends(get_current_user)):
    """Alias for convert-to-contact endpoint"""
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
        "company": lead.get("brand_name"),
        "source": lead.get("source"),
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
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"success": True, "contact_id": contact_id, "message": "Lead converted successfully"}


# ==========================================
# LEAD PATCH (for status/stage updates)
# ==========================================

@router.patch("/api/crm/leads/{lead_id}")
async def patch_lead(
    lead_id: str,
    update_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """PATCH endpoint for updating lead fields (status, stage, priority, etc.)"""
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
        
        # Commercial cannot reassign
        if "owner_email" in update_data or "assigned_to" in update_data:
            raise HTTPException(status_code=403, detail="Only admin can reassign leads")
    
    # Allowed fields
    allowed_fields = ["status", "stage", "priority", "tags", "name", "phone", 
                      "sector", "target_city", "timeline", "focus_notes"]
    if user["role"] == "admin":
        allowed_fields.extend(["owner_email", "assigned_to"])
    
    # Filter update data
    update_dict = {k: v for k, v in update_data.items() if k in allowed_fields and v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
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
    
    return {"success": True, "message": "Lead updated successfully"}


# ==========================================
# CONTACT NOTES
# ==========================================

@router.get("/api/crm/contacts/{contact_id}/notes")
async def get_contact_notes(
    contact_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all notes for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        notes_cursor = current_db.activities.find({
            "contact_id": contact_id,
            "type": "note"
        }).sort("created_at", -1).limit(limit)
        
        notes = await notes_cursor.to_list(limit)
        
        formatted_notes = []
        for note in notes:
            formatted_notes.append({
                "id": str(note["_id"]),
                "content": note.get("description") or note.get("note_text") or "",
                "note_text": note.get("description") or note.get("note_text") or "",
                "created_by": note.get("user_email", ""),
                "created_at": note.get("created_at").isoformat() if isinstance(note.get("created_at"), datetime) else str(note.get("created_at", ""))
            })
        
        return {"notes": formatted_notes, "total": len(formatted_notes)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching contact notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/crm/contacts/{contact_id}/notes")
async def add_contact_note(
    contact_id: str,
    note: NoteCreate,
    user: Dict = Depends(get_current_user)
):
    """Add note to a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        note_content = note.content or note.note_text or ""
        if not note_content.strip():
            raise HTTPException(status_code=400, detail="Note content is required")
        
        await current_db.activities.insert_one({
            "type": "note",
            "subject": "Note added",
            "description": note_content,
            "note_text": note_content,
            "contact_id": contact_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"success": True, "message": "Note added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error adding contact note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACT ACTIVITIES
# ==========================================

@router.get("/api/crm/contacts/{contact_id}/activities")
async def get_contact_activities(
    contact_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all activities for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        activities_cursor = current_db.activities.find({
            "contact_id": contact_id
        }).sort("created_at", -1).limit(limit)
        
        activities = await activities_cursor.to_list(limit)
        
        formatted = []
        for act in activities:
            formatted.append({
                "id": str(act["_id"]),
                "type": act.get("type", "note"),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_at": act.get("created_at").isoformat() if isinstance(act.get("created_at"), datetime) else str(act.get("created_at", ""))
            })
        
        return {"activities": formatted, "total": len(formatted)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching contact activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# CONTACT EMAILS
# ==========================================

@router.get("/api/crm/contacts/{contact_id}/emails")
async def get_contact_emails(
    contact_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all emails for a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        emails_cursor = current_db.crm_activities.find({
            "contact_id": contact_id,
            "type": "email_sent"
        }).sort("sent_at", -1).limit(limit)
        
        emails = await emails_cursor.to_list(limit)
        
        formatted = []
        for email in emails:
            formatted.append({
                "id": str(email["_id"]),
                "to_email": email.get("to_email", ""),
                "subject": email.get("subject", ""),
                "sent_by": email.get("sent_by", ""),
                "sent_at": email.get("sent_at", ""),
                "status": email.get("status", "sent")
            })
        
        return {"emails": formatted, "total": len(formatted)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching contact emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/crm/contacts/{contact_id}/emails/send")
async def send_contact_email(
    contact_id: str,
    email_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """Send email to a contact"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        contact = await current_db.contacts.find_one({"_id": ObjectId(contact_id)})
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        to_email = email_data.get("to_email") or contact.get("email")
        if not to_email:
            raise HTTPException(status_code=400, detail="No email address found")
        
        email_record = {
            "type": "email_sent",
            "contact_id": contact_id,
            "to_email": to_email,
            "subject": email_data.get("subject", ""),
            "body": email_data.get("body", email_data.get("message", "")),
            "sent_by": user["email"],
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": "queued"
        }
        
        result = await current_db.crm_activities.insert_one(email_record)
        
        await current_db.activities.insert_one({
            "type": "email_sent",
            "subject": f"Email sent to {to_email}",
            "description": email_data.get("subject", ""),
            "contact_id": contact_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"success": True, "email_id": str(result.inserted_id)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error sending contact email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITY DETAIL
# ==========================================

@router.get("/api/crm/opportunities/{opp_id}")
async def get_opportunity_detail(
    opp_id: str,
    user: Dict = Depends(get_current_user)
):
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
    
    # Get related activities
    activities = await current_db.activities.find({
        "opportunity_id": opp_id
    }).sort("created_at", -1).limit(20).to_list(20)
    
    # Get related tasks
    tasks = await current_db.tasks.find({
        "opportunity_id": opp_id
    }).sort("due_date", 1).to_list(20)
    
    # Format response
    opp["_id"] = str(opp["_id"])
    opp["id"] = opp["_id"]
    
    for act in activities:
        act["_id"] = str(act["_id"])
        if isinstance(act.get("created_at"), datetime):
            act["created_at"] = act["created_at"].isoformat()
    
    for task in tasks:
        task["_id"] = str(task["_id"])
        if isinstance(task.get("due_date"), datetime):
            task["due_date"] = task["due_date"].isoformat()
    
    opp["activities"] = activities
    opp["tasks"] = tasks
    
    # Convert datetime fields
    for field in ["created_at", "updated_at", "expected_close_date", "closed_at"]:
        if field in opp and isinstance(opp[field], datetime):
            opp[field] = opp[field].isoformat()
    
    return opp


# ==========================================
# OPPORTUNITY NOTES
# ==========================================

@router.get("/api/crm/opportunities/{opp_id}/notes")
async def get_opportunity_notes(
    opp_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all notes for an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        notes_cursor = current_db.activities.find({
            "opportunity_id": opp_id,
            "type": "note"
        }).sort("created_at", -1).limit(limit)
        
        notes = await notes_cursor.to_list(limit)
        
        formatted = []
        for note in notes:
            formatted.append({
                "id": str(note["_id"]),
                "content": note.get("description") or note.get("note_text") or "",
                "note_text": note.get("description") or note.get("note_text") or "",
                "created_by": note.get("user_email", ""),
                "created_at": note.get("created_at").isoformat() if isinstance(note.get("created_at"), datetime) else str(note.get("created_at", ""))
            })
        
        return {"notes": formatted, "total": len(formatted)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching opportunity notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/crm/opportunities/{opp_id}/notes")
async def add_opportunity_note(
    opp_id: str,
    note: NoteCreate,
    user: Dict = Depends(get_current_user)
):
    """Add note to an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        note_content = note.content or note.note_text or ""
        if not note_content.strip():
            raise HTTPException(status_code=400, detail="Note content is required")
        
        await current_db.activities.insert_one({
            "type": "note",
            "subject": "Note added",
            "description": note_content,
            "note_text": note_content,
            "opportunity_id": opp_id,
            "user_id": user["id"],
            "user_email": user["email"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"success": True, "message": "Note added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error adding opportunity note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# OPPORTUNITY ACTIVITIES
# ==========================================

@router.get("/api/crm/opportunities/{opp_id}/activities")
async def get_opportunity_activities(
    opp_id: str,
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get all activities for an opportunity"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        opp = await current_db.opportunities.find_one({"_id": ObjectId(opp_id)})
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        activities_cursor = current_db.activities.find({
            "opportunity_id": opp_id
        }).sort("created_at", -1).limit(limit)
        
        activities = await activities_cursor.to_list(limit)
        
        formatted = []
        for act in activities:
            formatted.append({
                "id": str(act["_id"]),
                "type": act.get("type", "note"),
                "subject": act.get("subject", ""),
                "description": act.get("description", ""),
                "user_email": act.get("user_email", ""),
                "created_at": act.get("created_at").isoformat() if isinstance(act.get("created_at"), datetime) else str(act.get("created_at", ""))
            })
        
        return {"activities": formatted, "total": len(formatted)}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching opportunity activities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# EMAIL DRAFTS
# ==========================================

@router.get("/api/crm/emails/drafts")
async def get_email_drafts(
    user: Dict = Depends(get_current_user),
    limit: int = Query(50, le=200)
):
    """Get email drafts for current user"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {"status": "draft"}
        
        # Commercial only sees their drafts
        if user["role"] == "commercial":
            query["created_by"] = user["email"]
        
        drafts_cursor = current_db.email_drafts.find(query).sort("updated_at", -1).limit(limit)
        drafts = await drafts_cursor.to_list(limit)
        
        formatted = []
        for draft in drafts:
            formatted.append({
                "id": str(draft["_id"]),
                "to_email": draft.get("to_email", ""),
                "subject": draft.get("subject", ""),
                "body": draft.get("body", ""),
                "lead_id": draft.get("lead_id"),
                "contact_id": draft.get("contact_id"),
                "opportunity_id": draft.get("opportunity_id"),
                "created_by": draft.get("created_by", ""),
                "created_at": draft.get("created_at").isoformat() if isinstance(draft.get("created_at"), datetime) else str(draft.get("created_at", "")),
                "updated_at": draft.get("updated_at").isoformat() if isinstance(draft.get("updated_at"), datetime) else str(draft.get("updated_at", ""))
            })
        
        return {"drafts": formatted, "total": len(formatted)}
        
    except Exception as e:
        logging.error(f"Error fetching email drafts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/crm/emails/drafts")
async def create_email_draft(
    draft: EmailDraftCreate,
    user: Dict = Depends(get_current_user)
):
    """Create new email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        draft_doc = {
            "to_email": draft.to_email,
            "subject": draft.subject,
            "body": draft.body,
            "lead_id": draft.lead_id,
            "contact_id": draft.contact_id,
            "opportunity_id": draft.opportunity_id,
            "status": "draft",
            "created_by": user["email"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await current_db.email_drafts.insert_one(draft_doc)
        
        return {"success": True, "draft_id": str(result.inserted_id)}
        
    except Exception as e:
        logging.error(f"Error creating email draft: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/crm/emails/drafts/{draft_id}")
async def update_email_draft(
    draft_id: str,
    update_data: EmailDraftUpdate,
    user: Dict = Depends(get_current_user)
):
    """Update email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        draft = await current_db.email_drafts.find_one({"_id": ObjectId(draft_id)})
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        # Check ownership for commercial
        if user["role"] == "commercial" and draft.get("created_by") != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        await current_db.email_drafts.update_one(
            {"_id": ObjectId(draft_id)},
            {"$set": update_dict}
        )
        
        return {"success": True, "message": "Draft updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating email draft: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/crm/emails/drafts/{draft_id}")
async def delete_email_draft(
    draft_id: str,
    user: Dict = Depends(get_current_user)
):
    """Delete email draft"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        draft = await current_db.email_drafts.find_one({"_id": ObjectId(draft_id)})
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        
        if user["role"] == "commercial" and draft.get("created_by") != user["email"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        await current_db.email_drafts.delete_one({"_id": ObjectId(draft_id)})
        
        return {"success": True, "message": "Draft deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting email draft: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS - DISPATCH
# ==========================================

@router.get("/api/crm/settings/dispatch")
async def get_dispatch_settings(user: Dict = Depends(require_admin)):
    """Get dispatch view - leads to assign (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get unassigned leads
        unassigned_cursor = current_db.leads.find({
            "$or": [
                {"assigned_to": None},
                {"assigned_to": ""},
                {"owner_email": None},
                {"owner_email": ""}
            ]
        }).sort("created_at", -1).limit(100)
        
        unassigned = await unassigned_cursor.to_list(100)
        
        # Get commercial users for assignment
        commercials = await current_db.crm_users.find({
            "role": {"$in": ["commercial", "sales", "admin"]},
            "is_active": True
        }).to_list(50)
        
        # Get assignment history
        assignment_history = await current_db.activities.find({
            "type": "assignment"
        }).sort("created_at", -1).limit(50).to_list(50)
        
        # Format data
        for lead in unassigned:
            lead["_id"] = str(lead["_id"])
            lead["id"] = lead["_id"]
            if isinstance(lead.get("created_at"), datetime):
                lead["created_at"] = lead["created_at"].isoformat()
        
        for comm in commercials:
            comm["_id"] = str(comm["_id"])
            comm.pop("password_hash", None)
        
        for hist in assignment_history:
            hist["_id"] = str(hist["_id"])
            if isinstance(hist.get("created_at"), datetime):
                hist["created_at"] = hist["created_at"].isoformat()
        
        return {
            "unassigned_leads": unassigned,
            "unassigned_count": len(unassigned),
            "commercials": commercials,
            "assignment_history": assignment_history
        }
        
    except Exception as e:
        logging.error(f"Error fetching dispatch settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS - QUALITY
# ==========================================

@router.get("/api/crm/settings/quality")
async def get_quality_settings(user: Dict = Depends(require_admin)):
    """Get data quality view (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Find duplicate emails in leads
        pipeline = [
            {"$group": {
                "_id": "$email",
                "count": {"$sum": 1},
                "leads": {"$push": {"id": {"$toString": "$_id"}, "brand_name": "$brand_name", "created_at": "$created_at"}}
            }},
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 50}
        ]
        
        duplicates = await current_db.leads.aggregate(pipeline).to_list(50)
        
        # Find leads with missing required fields
        missing_fields_cursor = current_db.leads.find({
            "$or": [
                {"email": {"$in": [None, ""]}},
                {"brand_name": {"$in": [None, ""]}},
                {"phone": {"$in": [None, ""]}}
            ]
        }).limit(50)
        
        incomplete_leads = await missing_fields_cursor.to_list(50)
        
        for lead in incomplete_leads:
            lead["_id"] = str(lead["_id"])
            if isinstance(lead.get("created_at"), datetime):
                lead["created_at"] = lead["created_at"].isoformat()
        
        # Get field completeness stats
        total_leads = await current_db.leads.count_documents({})
        with_phone = await current_db.leads.count_documents({"phone": {"$nin": [None, ""]}})
        with_email = await current_db.leads.count_documents({"email": {"$nin": [None, ""]}})
        with_brand = await current_db.leads.count_documents({"brand_name": {"$nin": [None, ""]}})
        
        return {
            "duplicates": duplicates,
            "duplicate_count": len(duplicates),
            "incomplete_leads": incomplete_leads,
            "incomplete_count": len(incomplete_leads),
            "field_completeness": {
                "total_leads": total_leads,
                "with_phone": with_phone,
                "with_email": with_email,
                "with_brand": with_brand,
                "phone_rate": round(with_phone / total_leads * 100, 1) if total_leads > 0 else 0,
                "email_rate": round(with_email / total_leads * 100, 1) if total_leads > 0 else 0,
                "brand_rate": round(with_brand / total_leads * 100, 1) if total_leads > 0 else 0
            }
        }
        
    except Exception as e:
        logging.error(f"Error fetching quality settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS - PERFORMANCE
# ==========================================

@router.get("/api/crm/settings/performance")
async def get_performance_settings(user: Dict = Depends(require_admin)):
    """Get performance stats (Admin only)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        
        # Overall stats
        total_leads = await current_db.leads.count_documents({})
        leads_this_month = await current_db.leads.count_documents({"created_at": {"$gte": month_start}})
        leads_this_week = await current_db.leads.count_documents({"created_at": {"$gte": week_ago}})
        
        # Conversion stats
        converted = await current_db.leads.count_documents({"status": "CONVERTED"})
        qualified = await current_db.leads.count_documents({"status": "QUALIFIED"})
        
        # Opportunities stats
        total_opps = await current_db.opportunities.count_documents({})
        won_opps = await current_db.opportunities.count_documents({"is_won": True})
        
        # Pipeline value
        pipeline_value = await current_db.opportunities.aggregate([
            {"$match": {"is_closed": False}},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$value", 0]}}}}
        ]).to_list(1)
        
        total_pipeline = pipeline_value[0]["total"] if pipeline_value else 0
        
        # Performance by commercial
        commercial_stats = await current_db.leads.aggregate([
            {"$match": {"owner_email": {"$nin": [None, ""]}}},
            {"$group": {
                "_id": "$owner_email",
                "total_leads": {"$sum": 1},
                "converted": {"$sum": {"$cond": [{"$eq": ["$status", "CONVERTED"]}, 1, 0]}},
                "qualified": {"$sum": {"$cond": [{"$eq": ["$status", "QUALIFIED"]}, 1, 0]}}
            }},
            {"$sort": {"total_leads": -1}},
            {"$limit": 20}
        ]).to_list(20)
        
        # Source performance
        source_stats = await current_db.leads.aggregate([
            {"$group": {
                "_id": "$source",
                "count": {"$sum": 1},
                "converted": {"$sum": {"$cond": [{"$eq": ["$status", "CONVERTED"]}, 1, 0]}}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]).to_list(10)
        
        return {
            "overview": {
                "total_leads": total_leads,
                "leads_this_month": leads_this_month,
                "leads_this_week": leads_this_week,
                "converted": converted,
                "qualified": qualified,
                "conversion_rate": round(converted / total_leads * 100, 1) if total_leads > 0 else 0
            },
            "opportunities": {
                "total": total_opps,
                "won": won_opps,
                "win_rate": round(won_opps / total_opps * 100, 1) if total_opps > 0 else 0,
                "pipeline_value": total_pipeline
            },
            "by_commercial": commercial_stats,
            "by_source": source_stats
        }
        
    except Exception as e:
        logging.error(f"Error fetching performance settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SETTINGS - GENERAL
# ==========================================

@router.get("/api/crm/settings")
async def get_general_settings(user: Dict = Depends(get_current_user)):
    """Get general CRM settings"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        settings = await current_db.crm_settings.find_one({}) or {}
        
        # Get available tags
        tags = settings.get("available_tags", ["hot", "cold", "follow-up", "qualified", "urgent"])
        
        # Get pipeline stages
        stages = settings.get("pipeline_stages", [
            {"key": "analysis_requested", "label": "Analyse demandee", "order": 1},
            {"key": "analysis_sent", "label": "Analyse envoyee", "order": 2},
            {"key": "call_scheduled", "label": "Appel planifie", "order": 3},
            {"key": "qualification", "label": "Qualification", "order": 4},
            {"key": "proposal_sent", "label": "Proposition envoyee", "order": 5},
            {"key": "negotiation", "label": "Negociation", "order": 6},
            {"key": "won", "label": "Gagne", "order": 7},
            {"key": "lost", "label": "Perdu", "order": 8}
        ])
        
        # Get lead statuses
        statuses = ["NEW", "CONTACTED", "QUALIFIED", "CONVERTED", "LOST", "PENDING_QUOTA"]
        
        # User permissions based on role
        permissions = {
            "can_manage_users": user["role"] == "admin",
            "can_manage_templates": user["role"] == "admin",
            "can_manage_pipeline": user["role"] == "admin",
            "can_assign_leads": user["role"] == "admin",
            "can_view_all_leads": user["role"] == "admin",
            "can_export": user["role"] in ["admin", "commercial"],
            "can_send_emails": True
        }
        
        return {
            "tags": tags,
            "stages": stages,
            "statuses": statuses,
            "permissions": permissions,
            "user_role": user["role"],
            "languages": ["fr", "en", "he"]
        }
        
    except Exception as e:
        logging.error(f"Error fetching general settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MINI-ANALYSIS LIST
# ==========================================

@router.get("/api/mini-analysis")
async def list_mini_analyses(
    user: Dict = Depends(get_current_user),
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    skip: int = Query(0, ge=0)
):
    """List mini-analyses (leads with source=mini-analyse)"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {"source": {"$in": ["mini-analyse", "mini_analyse", "mini-analysis", "mini_analysis"]}}
        
        if status:
            query["status"] = status
        
        # RBAC
        if user["role"] == "commercial":
            query["$or"] = [
                {"owner_email": user["email"]},
                {"assigned_to": user["email"]}
            ]
        
        total = await current_db.leads.count_documents(query)
        
        analyses_cursor = current_db.leads.find(query).sort("created_at", -1).skip(skip).limit(limit)
        analyses = await analyses_cursor.to_list(limit)
        
        for analysis in analyses:
            analysis["_id"] = str(analysis["_id"])
            analysis["id"] = analysis["_id"]
            if isinstance(analysis.get("created_at"), datetime):
                analysis["created_at"] = analysis["created_at"].isoformat()
        
        # Get stats
        pending = await current_db.leads.count_documents({**query, "status": "PENDING_QUOTA"})
        sent = await current_db.leads.count_documents({**query, "status": {"$in": ["CONTACTED", "QUALIFIED", "CONVERTED"]}})
        
        return {
            "analyses": analyses,
            "total": total,
            "stats": {
                "pending": pending,
                "sent": sent,
                "total": total
            }
        }
        
    except Exception as e:
        logging.error(f"Error fetching mini-analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
