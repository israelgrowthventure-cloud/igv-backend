"""
Mini-Analysis Workflow & Audit Logs Routes - CRM IGV
Points 10, 12 de la mission:
- Mini-analyse workflow complet
- Logs d'audit complets
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["mini-analysis-audit"])


# ==========================================
# POINT 10: MINI-ANALYSE WORKFLOW COMPLET
# ==========================================

@router.get("/mini-analyses")
async def list_mini_analyses(
    status: Optional[str] = Query(None, description="pending|processing|completed|archived"),
    assigned_to: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    skip: int = Query(0),
    user: Dict = Depends(get_current_user)
):
    """
    List mini-analyses with workflow status
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {}
        
        if status:
            query["workflow_status"] = status
        
        if assigned_to:
            query["assigned_to"] = assigned_to
        
        # RBAC - commercial sees only their assigned
        if user.get("role") == "commercial":
            query["assigned_to"] = user.get("email")
        
        total = await db.mini_analyses.count_documents(query)
        analyses = await db.mini_analyses.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
        
        for analysis in analyses:
            analysis['_id'] = str(analysis['_id'])
            if 'lead_id' not in analysis:
                analysis['lead_id'] = analysis['_id']
        
        return {
            "mini_analyses": analyses,
            "total": total,
            "limit": limit,
            "skip": skip
        }
        
    except Exception as e:
        logger.error(f"Error listing mini-analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: /stats MUST be registered before /{analysis_id} — FastAPI uses first-match routing
@router.get("/mini-analyses/stats")
async def get_mini_analysis_stats(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """Get mini-analysis statistics"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        now = datetime.now(timezone.utc)
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=365)
        
        # Count by status
        pipeline = [
            {"$match": {"created_at": {"$gte": start_date}}},
            {"$group": {"_id": "$workflow_status", "count": {"$sum": 1}}}
        ]
        
        status_counts = {}
        async for doc in db.mini_analyses.aggregate(pipeline):
            status_counts[doc["_id"] or "pending"] = doc["count"]
        
        total = sum(status_counts.values())
        
        # Conversion rate
        converted = await db.mini_analyses.count_documents({
            "converted_to_lead": True,
            "created_at": {"$gte": start_date}
        })
        
        conversion_rate = round((converted / total) * 100, 1) if total > 0 else 0
        
        return {
            "period": period,
            "total": total,
            "by_status": status_counts,
            "converted": converted,
            "conversion_rate": conversion_rate
        }
        
    except Exception as e:
        logger.error(f"Error getting mini-analysis stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mini-analyses/{analysis_id}")
async def get_mini_analysis(
    analysis_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get mini-analysis details"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        try:
            analysis = await db.mini_analyses.find_one({"_id": ObjectId(analysis_id)})
        except:
            analysis = await db.mini_analyses.find_one({"analysis_id": analysis_id})
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Mini-analysis not found")
        
        analysis['_id'] = str(analysis['_id'])
        
        # Get related activities
        activities = await db.activities.find({
            "$or": [
                {"mini_analysis_id": analysis_id},
                {"lead_id": analysis_id}
            ]
        }).sort("created_at", -1).to_list(length=50)
        
        for act in activities:
            act['_id'] = str(act['_id'])
        
        analysis['activities'] = activities
        
        return {"mini_analysis": analysis}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting mini-analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/mini-analyses/{analysis_id}/status")
async def update_mini_analysis_status(
    analysis_id: str,
    status_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """
    Update mini-analysis workflow status
    
    status_data: {
        "status": "pending|processing|completed|archived",
        "notes": "Optional notes"
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_status = status_data.get("status")
        valid_statuses = ["pending", "processing", "completed", "archived", "follow_up"]
        
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        try:
            analysis = await db.mini_analyses.find_one({"_id": ObjectId(analysis_id)})
        except:
            analysis = await db.mini_analyses.find_one({"analysis_id": analysis_id})
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Mini-analysis not found")
        
        old_status = analysis.get("workflow_status", "pending")
        
        # Update
        update_data = {
            "workflow_status": new_status,
            "workflow_updated_at": datetime.now(timezone.utc),
            "workflow_updated_by": user.get("email")
        }
        
        if new_status == "completed":
            update_data["completed_at"] = datetime.now(timezone.utc)
        
        await db.mini_analyses.update_one(
            {"_id": analysis["_id"]},
            {"$set": update_data}
        )
        
        # Log activity
        await db.activities.insert_one({
            "type": "status_change",
            "mini_analysis_id": analysis_id,
            "lead_id": analysis_id,
            "description": f"Statut changé: {old_status} → {new_status}",
            "old_value": old_status,
            "new_value": new_status,
            "notes": status_data.get("notes"),
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc)
        })
        
        # Audit log
        await db.audit_logs.insert_one({
            "action": "mini_analysis_status_change",
            "entity_type": "mini_analysis",
            "entity_id": analysis_id,
            "user_email": user.get("email"),
            "old_value": old_status,
            "new_value": new_status,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "old_status": old_status,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating mini-analysis status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mini-analyses/{analysis_id}/assign")
async def assign_mini_analysis(
    analysis_id: str,
    assign_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """
    Assign mini-analysis to a user
    Manager/Admin only
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        assign_to = assign_data.get("assign_to")
        if not assign_to:
            raise HTTPException(status_code=400, detail="assign_to required")
        
        try:
            analysis = await db.mini_analyses.find_one({"_id": ObjectId(analysis_id)})
        except:
            analysis = await db.mini_analyses.find_one({"analysis_id": analysis_id})
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Mini-analysis not found")
        
        old_assignee = analysis.get("assigned_to") or analysis.get("owner_email")

        await db.mini_analyses.update_one(
            {"_id": analysis["_id"]},
            {
                "$set": {
                    "assigned_to": assign_to,
                    "owner_email": assign_to,
                    "assigned_at": datetime.now(timezone.utc),
                    "assigned_by": user.get("email")
                }
            }
        )
        
        # Activity log
        await db.activities.insert_one({
            "type": "assignment",
            "mini_analysis_id": analysis_id,
            "lead_id": analysis_id,
            "description": f"Assigné à {assign_to}",
            "old_value": old_assignee,
            "new_value": assign_to,
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "assigned_to": assign_to,
            "previous_assignee": old_assignee
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning mini-analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mini-analyses/{analysis_id}/convert")
async def convert_mini_analysis_to_lead(
    analysis_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Convert a mini-analysis to a full lead for CRM tracking
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Find analysis
        try:
            analysis = await db.mini_analyses.find_one({"_id": ObjectId(analysis_id)})
        except:
            analysis = None
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Mini-analysis not found")
        
        # Create lead from analysis
        lead_data = {
            "email": analysis.get("email"),
            "name": analysis.get("name") or analysis.get("contact_name"),
            "phone": analysis.get("phone"),
            "brand_name": analysis.get("brand_name") or analysis.get("business_name"),
            "sector": analysis.get("sector") or analysis.get("activity_type"),
            "source": "mini-analyse",
            "status": "nouveau",
            "stage": "new",
            "priority": "medium",
            "language": analysis.get("language", "fr"),
            "mini_analysis_id": analysis_id,
            "mini_analysis_data": {
                "original_request": analysis.get("request"),
                "ai_response": analysis.get("response"),
                "created_at": analysis.get("created_at")
            },
            "owner_email": user.get("email"),
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await db.leads.insert_one(lead_data)
        lead_id = str(result.inserted_id)
        
        # Update mini-analysis
        await db.mini_analyses.update_one(
            {"_id": analysis["_id"]},
            {
                "$set": {
                    "converted_to_lead": True,
                    "lead_id": lead_id,
                    "converted_at": datetime.now(timezone.utc),
                    "converted_by": user.get("email"),
                    "workflow_status": "completed"
                }
            }
        )
        
        # Activity log
        await db.activities.insert_one({
            "type": "conversion",
            "mini_analysis_id": analysis_id,
            "lead_id": lead_id,
            "description": "Mini-analyse convertie en lead",
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "lead_id": lead_id,
            "message": "Mini-analysis converted to lead"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting mini-analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================

# REMOVED: audit-log routes � active versions in crm/main.py (registered first):
# GET /audit-logs               � see main.py line 1966
# GET /audit-logs/stats         � see main.py line 1997
# GET /audit-logs/entity/{...}  � see main.py line 2015
# GET /audit-logs/user/{email}  � see main.py line 2035
