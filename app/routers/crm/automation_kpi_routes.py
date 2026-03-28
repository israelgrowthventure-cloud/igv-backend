"""
Automation & KPI Routes - CRM IGV
Points 3, 4, 5, 6 de la mission:
- Règles métier automatiques
- Prochaine action obligatoire
- Suivi délais de réponse (KPI)
- Sources qui convertissent le mieux
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import logging

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["automation-kpi"])


# ==========================================
# POINT 3: RÈGLES MÉTIER AUTOMATIQUES
# ==========================================

@router.get("/rules")
async def list_automation_rules(user: Dict = Depends(require_admin)):
    """List all automation rules"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        rules = await db.automation_rules.find({}).to_list(length=100)
        for rule in rules:
            rule['_id'] = str(rule['_id'])
        return {"rules": rules, "total": len(rules)}
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
async def create_automation_rule(
    rule_data: Dict = Body(...),
    user: Dict = Depends(require_admin)
):
    """
    Create an automation rule
    
    Example rule_data:
    {
        "name": "Relance après 3 jours",
        "trigger": "lead_no_activity",
        "condition": {"days_inactive": 3},
        "action": {"type": "create_task", "template": "follow_up"},
        "is_active": true
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        rule = {
            "name": rule_data.get("name", "Unnamed Rule"),
            "description": rule_data.get("description", ""),
            "trigger": rule_data.get("trigger"),  # lead_created, lead_no_activity, stage_changed, etc.
            "condition": rule_data.get("condition", {}),
            "action": rule_data.get("action", {}),
            "is_active": rule_data.get("is_active", True),
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "execution_count": 0,
            "last_executed": None
        }
        
        result = await db.automation_rules.insert_one(rule)
        rule['_id'] = str(result.inserted_id)
        
        return {"success": True, "rule": rule}
        
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rules/{rule_id}")
async def update_automation_rule(
    rule_id: str,
    rule_data: Dict = Body(...),
    user: Dict = Depends(require_admin)
):
    """Update an automation rule"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        update = {
            "name": rule_data.get("name"),
            "description": rule_data.get("description"),
            "trigger": rule_data.get("trigger"),
            "condition": rule_data.get("condition"),
            "action": rule_data.get("action"),
            "is_active": rule_data.get("is_active"),
            "updated_at": datetime.now(timezone.utc),
            "updated_by": user.get("email")
        }
        # Remove None values
        update = {k: v for k, v in update.items() if v is not None}
        
        result = await db.automation_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {"$set": update}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {"success": True, "updated": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: str,
    user: Dict = Depends(require_admin)
):
    """Delete an automation rule"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await db.automation_rules.delete_one({"_id": ObjectId(rule_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"success": True, "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules/execute")
async def execute_automation_rules(user: Dict = Depends(require_admin)):
    """
    Manually execute all active automation rules
    In production, this would be called by a scheduled task
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        active_rules = await db.automation_rules.find({"is_active": True}).to_list(length=100)
        
        results = []
        for rule in active_rules:
            executed = 0
            trigger = rule.get("trigger")
            condition = rule.get("condition", {})
            action = rule.get("action", {})
            
            # Handle different triggers
            if trigger == "lead_no_activity":
                days = condition.get("days_inactive", 3)
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                
                # Find leads without recent activity
                inactive_leads = await db.leads.find({
                    "status": {"$nin": ["converted", "lost", "merged"]},
                    "$or": [
                        {"last_activity_at": {"$lt": cutoff}},
                        {"last_activity_at": {"$exists": False}}
                    ]
                }).to_list(length=100)
                
                for lead in inactive_leads:
                    if action.get("type") == "create_task":
                        await db.tasks.insert_one({
                            "title": f"Relance: {lead.get('name', lead.get('email'))}",
                            "description": action.get("template", "Follow up needed"),
                            "lead_id": str(lead["_id"]),
                            "due_date": datetime.now(timezone.utc) + timedelta(days=1),
                            "priority": "high",
                            "status": "pending",
                            "created_by": "automation",
                            "created_at": datetime.now(timezone.utc),
                            "rule_id": str(rule["_id"])
                        })
                        executed += 1
            
            elif trigger == "lead_high_priority_no_action":
                # High priority leads without next_action
                leads = await db.leads.find({
                    "priority": "high",
                    "status": {"$nin": ["converted", "lost"]},
                    "$or": [
                        {"next_action": {"$exists": False}},
                        {"next_action": None},
                        {"next_action.date": {"$lt": datetime.now(timezone.utc)}}
                    ]
                }).to_list(length=50)
                
                for lead in leads:
                    if action.get("type") == "notify":
                        await db.notifications.insert_one({
                            "type": "warning",
                            "message": f"Lead haute priorité sans action planifiée: {lead.get('name')}",
                            "lead_id": str(lead["_id"]),
                            "user_email": lead.get("owner_email"),
                            "created_at": datetime.now(timezone.utc),
                            "read": False
                        })
                        executed += 1
            
            # Update rule execution stats
            await db.automation_rules.update_one(
                {"_id": rule["_id"]},
                {
                    "$set": {"last_executed": datetime.now(timezone.utc)},
                    "$inc": {"execution_count": executed}
                }
            )
            
            results.append({
                "rule_id": str(rule["_id"]),
                "name": rule.get("name"),
                "executed": executed
            })
        
        return {
            "success": True,
            "rules_processed": len(active_rules),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error executing rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# NOTE: Routes below were removed — active versions registered first in crm/main.py:
# PUT /leads/{lead_id}/next-action — see main.py line 1609
# GET /kpi/response-times         — see main.py line 1715
# GET /kpi/conversion-times       — see main.py line 1792
# GET /kpi/source-performance     — see main.py line 1815
# GET /kpi/funnel                 — see main.py line 1846
