"""
Admin Routes - Dashboard Statistics & Lead Management
MISSION E: Admin endpoints for stats and lead viewing
MISSION F: Quota Gemini - Process pending analyses with retry mechanism
"""

from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import os
import logging

router = APIRouter(prefix="/api/admin")

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


@router.get("/stats/visits")
async def get_visit_stats_admin(range: str = "7d"):
    """
    MISSION E: Admin dashboard - Visit statistics
    
    GET /api/admin/stats/visits?range=7d|30d|90d
    
    Returns:
        - Total visits in range
        - Visits by page (top 10)
        - Visits by language
        - Top UTM sources
        - Conversion rate (mini-analysis requests)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Calculate time range
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
        
        # Mini-analysis conversions
        total_analyses = await current_db.mini_analyses.count_documents({
            "created_at": {"$gte": start_date}
        })
        
        # Leads created
        total_leads = await current_db.leads.count_documents({
            "created_at": {"$gte": start_date}
        })
        
        # Conversion rate (visits to mini-analysis)
        conversion_rate = (total_analyses / total_visits * 100) if total_visits > 0 else 0
        
        return {
            "range": range,
            "days": days,
            "total_visits": total_visits,
            "total_analyses": total_analyses,
            "total_leads": total_leads,
            "conversion_rate": round(conversion_rate, 2),
            "by_page": [{"page": p["_id"], "visits": p["count"]} for p in pages],
            "by_language": [{"language": l["_id"], "visits": l["count"]} for l in languages],
            "top_utm_sources": [{"source": u["_id"], "visits": u["count"]} for u in utm_sources]
        }
        
    except Exception as e:
        logging.error(f"Error getting admin visit stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/leads")
async def get_lead_stats_admin(range: str = "7d"):
    """
    MISSION E: Admin dashboard - Lead statistics
    
    GET /api/admin/stats/leads?range=7d|30d|90d
    
    Returns:
        - Total leads by status
        - Leads by sector
        - Leads by language
        - Recent leads (last 10)
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Calculate time range
        range_map = {
            "7d": 7,
            "30d": 30,
            "90d": 90
        }
        days = range_map.get(range, 7)
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Leads by status
        status_pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_status = await current_db.leads.aggregate(status_pipeline).to_list(10)
        
        # Leads by sector
        sector_pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$sector", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_sector = await current_db.leads.aggregate(sector_pipeline).to_list(10)
        
        # Leads by language
        lang_pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$language", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        by_language = await current_db.leads.aggregate(lang_pipeline).to_list(10)
        
        # Recent leads (last 10)
        recent_leads = await current_db.leads.find(
            {"created_at": {"$gte": start_date}},
            {"_id": 0, "email": 1, "brand_name": 1, "status": 1, "sector": 1, "language": 1, "created_at": 1}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "range": range,
            "days": days,
            "by_status": [{"status": s["_id"], "count": s["count"]} for s in by_status],
            "by_sector": [{"sector": s["_id"], "count": s["count"]} for s in by_sector],
            "by_language": [{"language": l["_id"], "count": l["count"]} for l in by_language],
            "recent_leads": recent_leads
        }
        
    except Exception as e:
        logging.error(f"Error getting lead stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-pending")
async def process_pending_analyses(limit: int = 10):
    """
    MISSION: Process pending analyses (retry when quota available)
    Protected endpoint - should check admin auth in production
    
    Usage: POST /api/admin/process-pending?limit=10
    """
    current_db = get_db()
    
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Find pending analyses with retry_count < 5
        pending = await current_db.pending_analyses.find({
            "status": "queued",
            "retry_count": {"$lt": 5}
        }).sort("created_at", 1).limit(limit).to_list(limit)
        
        if not pending:
            return {
                "message": "No pending analyses to process",
                "processed": 0,
                "failed": 0
            }
        
        processed = 0
        failed = 0
        results = []
        
        for analysis in pending:
            request_id = analysis.get("request_id", "unknown")
            
            try:
                # Import dynamically to avoid circular imports
                import mini_analysis_routes
                
                gemini_client = mini_analysis_routes.gemini_client
                GEMINI_MODEL = mini_analysis_routes.GEMINI_MODEL
                
                if not gemini_client:
                    logging.error(f"[{request_id}] QUEUE_RETRY: Gemini client not available")
                    failed += 1
                    continue
                
                # Reconstruct request from payload
                form_payload = analysis.get("form_payload", {})
                mini_request = mini_analysis_routes.MiniAnalysisRequest(**form_payload)
                language = analysis.get("language", "fr")
                
                # Build prompt using the function
                prompt = mini_analysis_routes.build_prompt(mini_request, language=language)
                
                # Call Gemini
                logging.info(f"[{request_id}] QUEUE_RETRY: Attempting to generate analysis")
                
                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[prompt]
                )
                
                analysis_text = response.text if hasattr(response, 'text') else str(response)
                
                if not analysis_text or "LANG_FAIL" in analysis_text:
                    raise Exception("Invalid response from Gemini")
                
                # Save successful analysis
                analysis_record = {
                    "brand_slug": analysis.get("brand", "").lower(),
                    "brand_name": analysis.get("brand"),
                    "email": analysis.get("user_email"),
                    "payload_form": form_payload,
                    "created_at": datetime.now(timezone.utc),
                    "provider": "gemini",
                    "model": GEMINI_MODEL,
                    "response_text": analysis_text,
                    "from_pending": True,
                    "original_request_id": request_id
                }
                
                await current_db.mini_analyses.insert_one(analysis_record)
                
                # Update pending status
                await current_db.pending_analyses.update_one(
                    {"_id": analysis["_id"]},
                    {
                        "$set": {
                            "status": "processed",
                            "processed_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                # Send email with analysis - import function if available
                try:
                    import extended_routes
                    await extended_routes.send_analysis_email(
                        analysis.get("user_email"),
                        analysis.get("brand"),
                        analysis_text,
                        language,
                        request_id
                    )
                    logging.info(f"[{request_id}] QUEUE_SENT: Analysis emailed successfully")
                except Exception as email_error:
                    logging.error(f"[{request_id}] EMAIL_SEND_FAIL: {str(email_error)}")
                
                processed += 1
                results.append({
                    "request_id": request_id,
                    "status": "success",
                    "brand": analysis.get("brand")
                })
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Increment retry count
                new_retry_count = analysis.get("retry_count", 0) + 1
                
                if "resource_exhausted" in error_str or "quota" in error_str:
                    # Still quota issue - keep queued
                    await current_db.pending_analyses.update_one(
                        {"_id": analysis["_id"]},
                        {
                            "$set": {
                                "retry_count": new_retry_count,
                                "last_retry_at": datetime.now(timezone.utc),
                                "last_error": "quota_exhausted"
                            }
                        }
                    )
                    logging.warning(f"[{request_id}] QUEUE_RETRY: Quota still exhausted")
                    failed += 1
                else:
                    # Other error - mark as failed
                    await current_db.pending_analyses.update_one(
                        {"_id": analysis["_id"]},
                        {
                            "$set": {
                                "status": "failed",
                                "retry_count": new_retry_count,
                                "failed_at": datetime.now(timezone.utc),
                                "error": str(e)
                            }
                        }
                    )
                    logging.error(f"[{request_id}] QUEUE_FAILED: {str(e)}")
                    failed += 1
                
                results.append({
                    "request_id": request_id,
                    "status": "failed",
                    "error": str(e)[:100]
                })
        
        return {
            "message": f"Processed {processed} analyses, {failed} failed",
            "processed": processed,
            "failed": failed,
            "results": results
        }
        
    except Exception as e:
        logging.error(f"Error processing pending analyses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-stats")
async def get_pending_stats():
    """Get statistics on pending analyses"""
    current_db = get_db()
    
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        queued_count = await current_db.pending_analyses.count_documents({"status": "queued"})
        processed_count = await current_db.pending_analyses.count_documents({"status": "processed"})
        failed_count = await current_db.pending_analyses.count_documents({"status": "failed"})
        
        return {
            "queued": queued_count,
            "processed": processed_count,
            "failed": failed_count,
            "total": queued_count + processed_count + failed_count
        }
    except Exception as e:
        logging.error(f"Error getting pending stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# USER MANAGEMENT ROUTES
# =============================================================================

from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    """User creation schema"""
    email: EmailStr
    name: str
    password: str
    role: str = "user"

class UserUpdate(BaseModel):
    """User update schema"""
    name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None

@router.post("/users")
async def create_user(user: UserCreate):
    """
    Create a new user
    POST /api/admin/users
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        # Check if email already exists
        existing = await current_db.users.find_one({"email": user.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        
        # Hash password
        hashed_password = pwd_context.hash(user.password)
        
        user_record = {
            "email": user.email,
            "name": user.name,
            "password": hashed_password,
            "role": user.role,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "active": True
        }
        
        result = await current_db.users.insert_one(user_record)
        logging.info(f"User created: {user.email}")
        
        return {
            "status": "created",
            "user_id": str(result.inserted_id),
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def list_users():
    """
    List all users (without passwords)
    GET /api/admin/users
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        users_cursor = current_db.users.find({}, {"password": 0})
        users = await users_cursor.to_list(100)
        
        # Serialize ObjectIds
        for user in users:
            user["_id"] = str(user["_id"])
            if "created_at" in user:
                user["created_at"] = user["created_at"].isoformat() if hasattr(user["created_at"], 'isoformat') else str(user["created_at"])
        
        return {"users": users, "count": len(users)}
    except Exception as e:
        logging.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """
    Delete a user
    DELETE /api/admin/users/{user_id}
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        from bson import ObjectId
        
        try:
            result = await current_db.users.delete_one({"_id": ObjectId(user_id)})
        except:
            result = await current_db.users.delete_one({"_id": user_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        
        logging.info(f"User deleted: {user_id}")
        return {"status": "deleted", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SETTINGS ROUTES
# =============================================================================

class SettingsUpdate(BaseModel):
    """Settings update schema"""
    site_name: Optional[str] = None
    default_language: Optional[str] = "fr"
    timezone: Optional[str] = "Europe/Paris"
    maintenance_mode: Optional[bool] = False
    contact_email: Optional[str] = None
    max_leads_per_day: Optional[int] = 100

@router.get("/settings")
async def get_settings():
    """
    Get site settings
    GET /api/admin/settings
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        settings = await current_db.settings.find_one({"_id": "main"})
        
        if settings is None:
            # Return default settings
            return {
                "_id": "main",
                "site_name": "Israel Growth Venture",
                "default_language": "fr",
                "timezone": "Europe/Paris",
                "maintenance_mode": False,
                "contact_email": "contact@israelgrowthventure.com",
                "max_leads_per_day": 100
            }
        
        return settings
    except Exception as e:
        logging.error(f"Error getting settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/settings")
async def update_settings(settings: SettingsUpdate):
    """
    Update site settings
    PUT /api/admin/settings
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        update_data = {k: v for k, v in settings.dict().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        await current_db.settings.update_one(
            {"_id": "main"},
            {"$set": update_data},
            upsert=True
        )
        
        logging.info(f"Settings updated: {list(update_data.keys())}")
        return {"status": "updated", "updated_fields": list(update_data.keys())}
    except Exception as e:
        logging.error(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
