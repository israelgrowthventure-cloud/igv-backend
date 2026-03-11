"""
Tracking Routes - Cookies Consent & Visit Tracking
MISSION D: Cookie banner + visit database
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import os
import logging

router = APIRouter(prefix="/api/track")

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


class VisitTrack(BaseModel):
    """Visit tracking schema"""
    page: str
    referrer: Optional[str] = None
    language: str = "fr"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    consent_analytics: bool = True


@router.post("/visit")
async def track_visit(visit: VisitTrack, request: Request):
    """
    MISSION D: Track visitor activity (only if consent_analytics=true)
    
    POST /api/track/visit
    Body: {
        "page": "/fr/mini-analyse",
        "referrer": "https://google.com",
        "language": "fr",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "israel-expansion",
        "consent_analytics": true
    }
    """
    
    # Respect cookie consent
    if not visit.consent_analytics:
        logging.info("Visit tracking skipped: no analytics consent")
        return {"status": "skipped", "reason": "no_consent"}
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Extract client metadata
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")
        
        visit_record = {
            "page": visit.page,
            "referrer": visit.referrer,
            "language": visit.language,
            "utm_source": visit.utm_source,
            "utm_medium": visit.utm_medium,
            "utm_campaign": visit.utm_campaign,
            "ip_address": client_ip,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc)
        }
        
        result = await current_db.visits.insert_one(visit_record)
        logging.info(f"VISIT_TRACK_OK: visit_id={result.inserted_id} page={visit.page}")
        
        return {
            "status": "tracked",
            "visit_id": str(result.inserted_id)
        }
        
    except Exception as e:
        logging.error(f"VISIT_TRACK_ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_visit_stats(range: str = "7d"):
    """
    MISSION E: Get visit statistics
    
    GET /api/track/stats?range=7d|30d|90d
    
    Returns:
        - Total visits
        - Visits by page
        - Visits by language
        - Top UTM sources
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Calculate time range
        from datetime import timedelta
        range_map = {
            "7d": 7,
            "30d": 30,
            "90d": 90
        }
        days = range_map.get(range, 7)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Total visits in range
        total_visits = await current_db.visits.count_documents({
            "timestamp": {"$gte": start_date}
        })
        
        # Visits by page (top 10)
        page_pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {"$group": {"_id": "$page", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        pages = await current_db.visits.aggregate(page_pipeline).to_list(10)
        
        # Visits by language
        lang_pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        languages = await current_db.visits.aggregate(lang_pipeline).to_list(10)
        
        # Top UTM sources
        utm_pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}, "utm_source": {"$ne": None}}},
            {"$group": {"_id": "$utm_source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        utm_sources = await current_db.visits.aggregate(utm_pipeline).to_list(10)
        
        return {
            "range": range,
            "days": days,
            "total_visits": total_visits,
            "by_page": [{"page": p["_id"], "visits": p["count"]} for p in pages],
            "by_language": [{"language": l["_id"], "visits": l["count"]} for l in languages],
            "top_utm_sources": [{"source": u["_id"], "visits": u["count"]} for u in utm_sources]
        }
        
    except Exception as e:
        logging.error(f"Error getting visit stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
