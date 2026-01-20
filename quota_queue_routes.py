"""
Gemini Quota Queue System
Handles analysis requests when quota is exceeded
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import os
import logging
from bson import ObjectId

router = APIRouter(prefix="/api/quota")

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

class PendingAnalysisCreate(BaseModel):
    lead_id: str
    email: EmailStr
    brand_name: str
    sector: Optional[str] = None
    language: str = "fr"


# ==========================================
# QUEUE MANAGEMENT
# ==========================================

@router.post("/queue-analysis")
async def queue_analysis(analysis: PendingAnalysisCreate):
    """
    Queue an analysis request when quota is exceeded
    Called automatically by mini-analysis when quota reached
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Check if already queued
    existing = await current_db.pending_analyses.find_one({
        "lead_id": analysis.lead_id,
        "status": "pending"
    })
    
    if existing:
        return {
            "status": "already_queued",
            "message": "Analysis already in queue",
            "queue_position": await get_queue_position(current_db, str(existing["_id"]))
        }
    
    # Create queue entry
    queue_doc = {
        **analysis.dict(),
        "status": "pending",
        "attempts": 0,
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.pending_analyses.insert_one(queue_doc)
    queue_id = str(result.inserted_id)
    
    # Update lead status
    try:
        await current_db.leads.update_one(
            {"_id": ObjectId(analysis.lead_id)},
            {
                "$set": {
                    "status": "PENDING_QUOTA",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    except Exception as e:
        logging.error(f"Failed to update lead status: {e}")
    
    # Log activity
    try:
        await current_db.activities.insert_one({
            "type": "note",
            "subject": "Analysis queued (quota exceeded)",
            "description": f"Analysis request queued due to quota limit. Will be processed within 24-48h.",
            "lead_id": analysis.lead_id,
            "metadata": {"queue_id": queue_id},
            "created_at": datetime.now(timezone.utc)
        })
    except Exception as e:
        logging.error(f"Failed to log queue activity: {e}")
    
    queue_position = await get_queue_position(current_db, queue_id)
    
    logging.info(f"Analysis queued: {analysis.email} / {analysis.brand_name} (queue_id={queue_id}, position={queue_position})")
    
    return {
        "status": "queued",
        "message": "Analysis queued successfully",
        "queue_id": queue_id,
        "queue_position": queue_position,
        "estimated_time": "24-48 hours"
    }


async def get_queue_position(db, queue_id: str) -> int:
    """Get position in queue"""
    try:
        queue_item = await db.pending_analyses.find_one({"_id": ObjectId(queue_id)})
        if not queue_item:
            return 0
        
        # Count items created before this one
        earlier_count = await db.pending_analyses.count_documents({
            "status": "pending",
            "created_at": {"$lt": queue_item["created_at"]}
        })
        
        return earlier_count + 1
    except:
        return 0


@router.get("/queue-status/{queue_id}")
async def get_queue_status(queue_id: str):
    """Get status of queued analysis"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        queue_item = await current_db.pending_analyses.find_one({"_id": ObjectId(queue_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid queue ID")
    
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    queue_item["_id"] = str(queue_item["_id"])
    if "created_at" in queue_item and isinstance(queue_item["created_at"], datetime):
        queue_item["created_at"] = queue_item["created_at"].isoformat()
    if "updated_at" in queue_item and isinstance(queue_item["updated_at"], datetime):
        queue_item["updated_at"] = queue_item["updated_at"].isoformat()
    
    queue_item["queue_position"] = await get_queue_position(current_db, queue_id)
    
    return queue_item


@router.get("/admin/pending-analyses")
async def get_pending_analyses(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None
):
    """
    Get all pending analyses (admin only)
    Used to process the queue
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    filter_query = {}
    if status:
        filter_query["status"] = status
    else:
        filter_query["status"] = "pending"
    
    cursor = current_db.pending_analyses.find(filter_query).sort("created_at", 1).skip(skip).limit(limit)
    analyses = await cursor.to_list(length=limit)
    total = await current_db.pending_analyses.count_documents(filter_query)
    
    for analysis in analyses:
        analysis["_id"] = str(analysis["_id"])
        if "created_at" in analysis and isinstance(analysis["created_at"], datetime):
            analysis["created_at"] = analysis["created_at"].isoformat()
        if "updated_at" in analysis and isinstance(analysis["updated_at"], datetime):
            analysis["updated_at"] = analysis["updated_at"].isoformat()
    
    return {
        "analyses": analyses,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/admin/process-pending/{queue_id}")
async def process_pending_analysis(queue_id: str):
    """
    Process a single pending analysis
    Admin endpoint to manually trigger processing
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        queue_item = await current_db.pending_analyses.find_one({"_id": ObjectId(queue_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid queue ID")
    
    if not queue_item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    if queue_item["status"] != "pending":
        raise HTTPException(status_code=400, detail="Analysis not in pending status")
    
    # Update status to processing
    await current_db.pending_analyses.update_one(
        {"_id": ObjectId(queue_id)},
        {
            "$set": {
                "status": "processing",
                "last_attempt_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            "$inc": {"attempts": 1}
        }
    )
    
    # Here you would trigger the actual analysis generation
    # For now, we'll mark it as needing manual processing
    
    return {
        "status": "processing",
        "message": "Analysis processing started",
        "queue_id": queue_id,
        "lead_id": queue_item["lead_id"],
        "email": queue_item["email"]
    }


@router.post("/admin/retry-failed")
async def retry_failed_analyses():
    """
    Retry all failed analyses
    Admin endpoint for bulk retry
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Reset failed analyses back to pending
    result = await current_db.pending_analyses.update_many(
        {"status": "failed", "attempts": {"$lt": 3}},
        {
            "$set": {
                "status": "pending",
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {
        "status": "success",
        "message": f"{result.modified_count} analyses reset to pending",
        "count": result.modified_count
    }
