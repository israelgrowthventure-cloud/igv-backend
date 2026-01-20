"""
GDPR Consent & Cookie Management Routes
Production-ready, fully compliant
"""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import os
import logging
import hashlib

router = APIRouter(prefix="/api/gdpr")

# MongoDB
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

mongo_client = None
db = None

def get_db():
    global mongo_client, db
    if db is None and mongo_url:
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client[db_name]
    return db


# ==========================================
# MODELS
# ==========================================

class ConsentUpdate(BaseModel):
    consent_analytics: bool = False
    consent_marketing: bool = False
    consent_functional: bool = True  # Always true for essential cookies


class NewsletterSubscribe(BaseModel):
    email: EmailStr
    language: str = "fr"
    consent_marketing: bool = True
    source: Optional[str] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None


class VisitorTracking(BaseModel):
    session_id: str
    page: str
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_term: Optional[str] = None
    utm_content: Optional[str] = None
    language: Optional[str] = None


# ==========================================
# CONSENT MANAGEMENT
# ==========================================

@router.post("/consent")
async def update_consent(consent: ConsentUpdate, request: Request):
    """
    Update user consent preferences (GDPR-compliant)
    Stores consent in visitor record
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get visitor ID (hash of IP + user agent)
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    visitor_id = hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    
    # Update or create visitor record
    now = datetime.now(timezone.utc)
    
    await current_db.visitors.update_one(
        {"visitor_id": visitor_id},
        {
            "$set": {
                "consent_analytics": consent.consent_analytics,
                "consent_marketing": consent.consent_marketing,
                "consent_functional": consent.consent_functional,
                "consent_updated_at": now,
                "last_seen_at": now,
                "ip_hash": ip_hash
            },
            "$setOnInsert": {
                "visitor_id": visitor_id,
                "session_id": "",
                "sessions_count": 0,
                "pages_viewed": [],
                "page_count": 0,
                "first_seen_at": now
            }
        },
        upsert=True
    )
    
    logging.info(f"Consent updated for visitor {visitor_id[:8]}...: analytics={consent.consent_analytics}, marketing={consent.consent_marketing}")
    
    return {
        "status": "success",
        "message": "Consent preferences saved",
        "visitor_id": visitor_id[:8]  # Return partial ID for confirmation
    }


@router.get("/consent")
async def get_consent(request: Request):
    """Get current consent preferences for this visitor"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get visitor ID
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    visitor_id = hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()
    
    visitor = await current_db.visitors.find_one({"visitor_id": visitor_id})
    
    if not visitor:
        return {
            "consent_analytics": False,
            "consent_marketing": False,
            "consent_functional": True
        }
    
    return {
        "consent_analytics": visitor.get("consent_analytics", False),
        "consent_marketing": visitor.get("consent_marketing", False),
        "consent_functional": visitor.get("consent_functional", True),
        "consent_updated_at": visitor.get("consent_updated_at").isoformat() if visitor.get("consent_updated_at") else None
    }


# ==========================================
# VISITOR TRACKING (ONLY WITH CONSENT)
# ==========================================

@router.post("/track/visit")
async def track_visit(tracking: VisitorTracking, request: Request):
    """
    Track visitor page view (ONLY if analytics consent given)
    GDPR-compliant: no tracking without consent
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Get visitor ID
    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    visitor_id = hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()
    
    # Check consent
    visitor = await current_db.visitors.find_one({"visitor_id": visitor_id})
    
    # If no consent given for analytics, DO NOT TRACK
    if not visitor or not visitor.get("consent_analytics", False):
        logging.info(f"Tracking blocked for visitor {visitor_id[:8]}... (no analytics consent)")
        return {"status": "blocked", "reason": "no_analytics_consent"}
    
    # Track visit
    now = datetime.now(timezone.utc)
    
    update_doc = {
        "$set": {
            "last_seen_at": now,
            "last_page": tracking.page,
            "session_id": tracking.session_id,
            "ip_hash": ip_hash
        },
        "$push": {"pages_viewed": {"page": tracking.page, "timestamp": now}},
        "$inc": {"page_count": 1, "sessions_count": 1}
    }
    
    # Set first-touch attribution
    setOnInsert = {
        "visitor_id": visitor_id,
        "first_seen_at": now,
        "first_landing_page": tracking.page
    }
    
    if tracking.utm_source:
        update_doc["$set"]["last_utm_source"] = tracking.utm_source
        setOnInsert["first_utm_source"] = tracking.utm_source
    
    if tracking.utm_medium:
        update_doc["$set"]["last_utm_medium"] = tracking.utm_medium
        setOnInsert["first_utm_medium"] = tracking.utm_medium
    
    if tracking.utm_campaign:
        update_doc["$set"]["last_utm_campaign"] = tracking.utm_campaign
        setOnInsert["first_utm_campaign"] = tracking.utm_campaign
    
    if tracking.referrer:
        update_doc["$set"]["last_referrer"] = tracking.referrer
        setOnInsert["first_referrer"] = tracking.referrer
    
    update_doc["$setOnInsert"] = setOnInsert
    
    await current_db.visitors.update_one(
        {"visitor_id": visitor_id},
        update_doc,
        upsert=True
    )
    
    return {"status": "tracked", "visitor_id": visitor_id[:8]}


# ==========================================
# NEWSLETTER (WITH EXPLICIT CONSENT)
# ==========================================

@router.post("/newsletter/subscribe")
async def newsletter_subscribe(sub: NewsletterSubscribe, request: Request):
    """
    Newsletter subscription (GDPR-compliant)
    Requires EXPLICIT marketing consent
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # GDPR: Marketing consent is MANDATORY
    if not sub.consent_marketing:
        raise HTTPException(status_code=400, detail="Marketing consent required for newsletter")
    
    # Get IP for consent record
    ip = request.client.host if request.client else "unknown"
    
    # Check if already subscribed
    existing = await current_db.newsletter_subscribers.find_one({"email": sub.email})
    
    if existing:
        # Reactivate if was unsubscribed
        if not existing.get("is_active", True):
            await current_db.newsletter_subscribers.update_one(
                {"email": sub.email},
                {
                    "$set": {
                        "is_active": True,
                        "consent_marketing": True,
                        "consent_date": datetime.now(timezone.utc),
                        "consent_ip": ip,
                        "unsubscribed_at": None,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return {"status": "resubscribed", "message": "Newsletter subscription reactivated"}
        else:
            return {"status": "already_subscribed", "message": "Already subscribed to newsletter"}
    
    # Create new subscriber
    subscriber_doc = {
        "email": sub.email,
        "language": sub.language,
        "consent_marketing": True,
        "consent_date": datetime.now(timezone.utc),
        "consent_ip": ip,
        "is_active": True,
        "is_verified": False,
        "source": sub.source,
        "utm_source": sub.utm_source,
        "utm_campaign": sub.utm_campaign,
        "tags": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.newsletter_subscribers.insert_one(subscriber_doc)
    
    # Try to link to existing lead
    lead = await current_db.leads.find_one({"email": sub.email})
    if lead:
        await current_db.newsletter_subscribers.update_one(
            {"_id": result.inserted_id},
            {"$set": {"lead_id": str(lead["_id"])}}
        )
    
    logging.info(f"Newsletter subscription: {sub.email} (consent_ip={ip})")
    
    return {
        "status": "subscribed",
        "message": "Newsletter subscription successful",
        "subscriber_id": str(result.inserted_id)
    }


@router.post("/newsletter/unsubscribe")
async def newsletter_unsubscribe(email: EmailStr, reason: Optional[str] = None):
    """
    Newsletter unsubscribe (GDPR right to withdraw consent)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    subscriber = await current_db.newsletter_subscribers.find_one({"email": email})
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Email not found in newsletter")
    
    if not subscriber.get("is_active", True):
        return {"status": "already_unsubscribed", "message": "Already unsubscribed"}
    
    # Unsubscribe
    await current_db.newsletter_subscribers.update_one(
        {"email": email},
        {
            "$set": {
                "is_active": False,
                "consent_marketing": False,
                "unsubscribed_at": datetime.now(timezone.utc),
                "unsubscribe_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    logging.info(f"Newsletter unsubscribe: {email} (reason={reason})")
    
    return {"status": "unsubscribed", "message": "Successfully unsubscribed from newsletter"}


@router.delete("/newsletter/delete-data")
async def newsletter_delete_data(email: EmailStr):
    """
    Delete all newsletter data (GDPR right to erasure)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    result = await current_db.newsletter_subscribers.delete_one({"email": email})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Email not found")
    
    logging.info(f"Newsletter data deleted: {email} (GDPR erasure)")
    
    return {"status": "deleted", "message": "All newsletter data deleted"}


# ==========================================
# DATA ACCESS & DELETION (GDPR Rights)
# ==========================================

@router.get("/my-data")
async def get_my_data(email: EmailStr):
    """
    Get all data stored for an email (GDPR right of access)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    data = {}
    
    # Lead data
    lead = await current_db.leads.find_one({"email": email})
    if lead:
        lead["_id"] = str(lead["_id"])
        data["lead"] = lead
    
    # Contact data
    contact = await current_db.contacts.find_one({"email": email})
    if contact:
        contact["_id"] = str(contact["_id"])
        data["contact"] = contact
    
    # Newsletter data
    subscriber = await current_db.newsletter_subscribers.find_one({"email": email})
    if subscriber:
        subscriber["_id"] = str(subscriber["_id"])
        data["newsletter_subscriber"] = subscriber
    
    return {
        "email": email,
        "data": data,
        "collected_at": datetime.now(timezone.utc).isoformat()
    }


@router.delete("/delete-all-data")
async def delete_all_data(email: EmailStr, confirmation: str):
    """
    Delete ALL data for an email (GDPR right to erasure)
    Requires confirmation = email address
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Safety check
    if confirmation != email:
        raise HTTPException(status_code=400, detail="Confirmation email does not match")
    
    deleted_count = 0
    
    # Delete from all collections
    result = await current_db.leads.delete_many({"email": email})
    deleted_count += result.deleted_count
    
    result = await current_db.contacts.delete_many({"email": email})
    deleted_count += result.deleted_count
    
    result = await current_db.newsletter_subscribers.delete_many({"email": email})
    deleted_count += result.deleted_count
    
    # Anonymize activities (keep for audit but remove email)
    await current_db.activities.update_many(
        {"$or": [{"user_email": email}, {"metadata.email": email}]},
        {"$set": {"user_email": "deleted@gdpr", "metadata.email": "deleted@gdpr"}}
    )
    
    logging.info(f"GDPR data deletion: {email} ({deleted_count} records deleted)")
    
    return {
        "status": "deleted",
        "message": f"All data for {email} has been permanently deleted",
        "records_deleted": deleted_count
    }
