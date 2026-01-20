"""
CRM Routes - Lead Management for IGV
Automatic lead creation on every mini-analysis request
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import os
import logging

router = APIRouter(prefix="/api")

# MongoDB connection
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

mongo_client = None
db = None

def get_db():
    """Lazy initialization of MongoDB connection"""
    global mongo_client, db
    if db is None and mongo_url:
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client[db_name]
    return db


class LeadCreate(BaseModel):
    """Lead creation schema"""
    email: EmailStr
    brand_name: str
    name: Optional[str] = None
    phone: Optional[str] = None
    sector: Optional[str] = None
    language: str = "fr"
    status: str = "NEW"  # NEW, QUOTA_BLOCKED, GENERATED, EMAILED, ERROR
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


async def create_lead_in_crm(lead_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    MISSION C: Create lead automatically (with MongoDB fallback if CRM unavailable)
    
    Args:
        lead_data: Lead information dictionary
        request_id: Unique request identifier for logging
    
    Returns:
        dict with status and lead_id
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
            # Update existing lead
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
        
        # Fallback: try to save with minimal data
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


@router.get("/admin/leads")
async def get_leads(limit: int = 10, skip: int = 0):
    """
    MISSION C: Admin endpoint to view leads
    Protected by admin auth (add Depends(get_current_user) later)
    
    Usage: GET /api/admin/leads?limit=10&skip=0
    """
    current_db = get_db()
    
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        leads = await current_db.leads.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        total = await current_db.leads.count_documents({})
        
        return {
            "leads": leads,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    except Exception as e:
        logging.error(f"Error fetching leads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/crm")
async def crm_health_check():
    """
    MISSION B: CRM Health Check
    GET /api/health/crm
    Response: 200 JSON {"status": "ok", "db_connected": true}
    """
    current_db = get_db()
    
    if current_db is None:
        return {
            "status": "degraded",
            "db_connected": False,
            "message": "MongoDB not configured"
        }
    
    try:
        # Test MongoDB connection
        await current_db.command("ping")
        
        # Count leads
        lead_count = await current_db.leads.count_documents({})
        
        return {
            "status": "ok",
            "db_connected": True,
            "lead_count": lead_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"CRM health check failed: {str(e)}")
        return {
            "status": "error",
            "db_connected": False,
            "error": str(e)
        }


# =============================================================================
# NOTES ROUTES - Contact Notes Management
# =============================================================================

class NoteCreate(BaseModel):
    """Note creation schema"""
    content: str

@router.post("/contacts/{contact_id}/notes")
async def create_note(contact_id: str, note: NoteCreate):
    """
    Create a new note for a contact
    POST /api/contacts/{contact_id}/notes
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        from bson import ObjectId
        
        note_record = {
            "content": note.content,
            "contact_id": contact_id,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result = await current_db.notes.insert_one(note_record)
        
        # Also update the contact's notes array
        try:
            await current_db.contacts.update_one(
                {"_id": ObjectId(contact_id)},
                {"$push": {"notes": str(result.inserted_id)}}
            )
        except:
            # Try with string ID
            await current_db.contacts.update_one(
                {"_id": contact_id},
                {"$push": {"notes": str(result.inserted_id)}}
            )
        
        logging.info(f"Note created for contact {contact_id}: {result.inserted_id}")
        return {
            "status": "created",
            "note_id": str(result.inserted_id),
            "content": note.content,
            "created_at": note_record["created_at"].isoformat()
        }
    except Exception as e:
        logging.error(f"Error creating note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contacts/{contact_id}/notes")
async def get_notes(contact_id: str):
    """
    Get all notes for a contact
    GET /api/contacts/{contact_id}/notes
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        notes_cursor = current_db.notes.find({"contact_id": contact_id}).sort("created_at", -1)
        notes = await notes_cursor.to_list(100)
        
        # Serialize ObjectIds
        for note in notes:
            note["_id"] = str(note["_id"])
            if "created_at" in note:
                note["created_at"] = note["created_at"].isoformat() if hasattr(note["created_at"], 'isoformat') else str(note["created_at"])
        
        return {"notes": notes, "count": len(notes)}
    except Exception as e:
        logging.error(f"Error fetching notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contacts/{contact_id}/notes/{note_id}")
async def delete_note(contact_id: str, note_id: str):
    """
    Delete a note
    DELETE /api/contacts/{contact_id}/notes/{note_id}
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        from bson import ObjectId
        
        # Delete the note
        try:
            result = await current_db.notes.delete_one({"_id": ObjectId(note_id)})
        except:
            result = await current_db.notes.delete_one({"_id": note_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Remove from contact's notes array
        try:
            await current_db.contacts.update_one(
                {"_id": ObjectId(contact_id)},
                {"$pull": {"notes": note_id}}
            )
        except:
            await current_db.contacts.update_one(
                {"_id": contact_id},
                {"$pull": {"notes": note_id}}
            )
        
        logging.info(f"Note {note_id} deleted from contact {contact_id}")
        return {"status": "deleted", "note_id": note_id}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
