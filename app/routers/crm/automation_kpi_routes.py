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


# ==========================================
# POINT 4: PROCHAINE ACTION OBLIGATOIRE
# ==========================================

@router.get("/leads/missing-next-action")
async def get_leads_missing_next_action(
    priority: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: Dict = Depends(get_current_user)
):
    """Get leads without a next action planned"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        query = {
            "status": {"$nin": ["converted", "lost", "merged"]},
            "$or": [
                {"next_action": {"$exists": False}},
                {"next_action": None},
                {"next_action.date": None}
            ]
        }
        
        if priority:
            query["priority"] = priority
        
        # RBAC filtering
        if user.get("role") == "commercial":
            query["owner_email"] = user.get("email")
        
        leads = await db.leads.find(query).sort("created_at", -1).to_list(length=limit)
        
        for lead in leads:
            lead['_id'] = str(lead['_id'])
            if 'lead_id' not in lead:
                lead['lead_id'] = lead['_id']
        
        return {
            "leads": leads,
            "total": len(leads),
            "message": "Ces leads n'ont pas de prochaine action planifiée"
        }
        
    except Exception as e:
        logger.error(f"Error getting leads without next action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/leads/{lead_id}/next-action")
async def set_lead_next_action(
    lead_id: str,
    action_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """
    Set next action for a lead
    
    action_data: {
        "type": "call|email|meeting|demo|follow_up",
        "date": "2026-01-25T10:00:00Z",
        "description": "Appeler pour suivi",
        "reminder": true
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Find lead
        try:
            lead = await db.leads.find_one({"_id": ObjectId(lead_id)})
        except:
            lead = await db.leads.find_one({"lead_id": int(lead_id)})
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        # RBAC check
        if user.get("role") == "commercial" and lead.get("owner_email") != user.get("email"):
            raise HTTPException(status_code=403, detail="Not authorized")
        
        next_action = {
            "type": action_data.get("type", "follow_up"),
            "date": action_data.get("date"),
            "description": action_data.get("description", ""),
            "reminder": action_data.get("reminder", True),
            "created_by": user.get("email"),
            "created_at": datetime.now(timezone.utc)
        }
        
        # Parse date if string
        if isinstance(next_action["date"], str):
            next_action["date"] = datetime.fromisoformat(next_action["date"].replace("Z", "+00:00"))
        
        await db.leads.update_one(
            {"_id": lead["_id"]},
            {
                "$set": {
                    "next_action": next_action,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Create task if reminder is set
        if action_data.get("reminder"):
            await db.tasks.insert_one({
                "title": f"{next_action['type'].title()}: {lead.get('name', lead.get('email'))}",
                "description": next_action["description"],
                "lead_id": str(lead["_id"]),
                "due_date": next_action["date"],
                "priority": lead.get("priority", "medium"),
                "status": "pending",
                "assigned_to": user.get("email"),
                "created_by": user.get("email"),
                "created_at": datetime.now(timezone.utc)
            })
        
        return {"success": True, "next_action": next_action}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting next action: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leads/overdue-actions")
async def get_overdue_actions(
    limit: int = Query(50, le=200),
    user: Dict = Depends(get_current_user)
):
    """Get leads with overdue next actions"""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        now = datetime.now(timezone.utc)
        
        query = {
            "status": {"$nin": ["converted", "lost", "merged"]},
            "next_action.date": {"$lt": now}
        }
        
        if user.get("role") == "commercial":
            query["owner_email"] = user.get("email")
        
        leads = await db.leads.find(query).sort("next_action.date", 1).to_list(length=limit)
        
        for lead in leads:
            lead['_id'] = str(lead['_id'])
            # Calculate days overdue
            if lead.get("next_action", {}).get("date"):
                action_date = lead["next_action"]["date"]
                if isinstance(action_date, datetime):
                    lead["days_overdue"] = (now - action_date).days
        
        return {
            "leads": leads,
            "total": len(leads)
        }
        
    except Exception as e:
        logger.error(f"Error getting overdue actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# POINT 5: SUIVI DÉLAIS DE RÉPONSE (KPI)
# ==========================================

@router.get("/kpi/response-times")
async def get_response_time_kpis(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """
    Get response time KPIs
    - First response time (time to first activity after lead creation)
    - Average response time
    - By user (for admin)
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Calculate date range
        now = datetime.now(timezone.utc)
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Get leads created in period
        query = {"created_at": {"$gte": start_date}}
        if user.get("role") == "commercial":
            query["owner_email"] = user.get("email")
        
        leads = await db.leads.find(query).to_list(length=1000)
        
        response_times = []
        by_user = {}
        
        for lead in leads:
            lead_id = str(lead.get("_id", lead.get("lead_id")))
            created_at = lead.get("created_at")
            owner = lead.get("owner_email", "unassigned")
            
            if not created_at:
                continue
            
            # Find first activity for this lead
            first_activity = await db.activities.find_one(
                {"lead_id": lead_id},
                sort=[("created_at", 1)]
            )
            
            if first_activity and first_activity.get("created_at"):
                response_time = (first_activity["created_at"] - created_at).total_seconds() / 3600  # hours
                response_times.append(response_time)
                
                if owner not in by_user:
                    by_user[owner] = []
                by_user[owner].append(response_time)
        
        # Calculate averages
        avg_response = sum(response_times) / len(response_times) if response_times else 0
        
        user_stats = []
        for email, times in by_user.items():
            user_stats.append({
                "user_email": email,
                "avg_response_hours": round(sum(times) / len(times), 1) if times else 0,
                "total_leads": len(times),
                "fastest_hours": round(min(times), 1) if times else 0,
                "slowest_hours": round(max(times), 1) if times else 0
            })
        
        # Sort by average (best first)
        user_stats.sort(key=lambda x: x["avg_response_hours"])
        
        return {
            "period": period,
            "total_leads_analyzed": len(leads),
            "leads_with_response": len(response_times),
            "avg_first_response_hours": round(avg_response, 1),
            "by_user": user_stats if user.get("role") == "admin" else None,
            "benchmark": {
                "excellent": "< 1h",
                "good": "1-4h",
                "acceptable": "4-24h",
                "poor": "> 24h"
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating response time KPIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/conversion-times")
async def get_conversion_time_kpis(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    user: Dict = Depends(require_admin)
):
    """
    Get lead-to-contact conversion time KPIs
    Admin only
    """
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
        
        # Get converted leads
        converted_leads = await db.leads.find({
            "status": "converted",
            "converted_at": {"$gte": start_date}
        }).to_list(length=500)
        
        conversion_times = []
        by_source = {}
        
        for lead in converted_leads:
            created_at = lead.get("created_at")
            converted_at = lead.get("converted_at")
            source = lead.get("source", "unknown")
            
            if created_at and converted_at:
                days = (converted_at - created_at).days
                conversion_times.append(days)
                
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(days)
        
        avg_conversion = sum(conversion_times) / len(conversion_times) if conversion_times else 0
        
        source_stats = []
        for source, times in by_source.items():
            source_stats.append({
                "source": source,
                "avg_days": round(sum(times) / len(times), 1) if times else 0,
                "conversions": len(times)
            })
        
        source_stats.sort(key=lambda x: x["avg_days"])
        
        return {
            "period": period,
            "total_conversions": len(converted_leads),
            "avg_conversion_days": round(avg_conversion, 1),
            "fastest_conversion_days": min(conversion_times) if conversion_times else 0,
            "slowest_conversion_days": max(conversion_times) if conversion_times else 0,
            "by_source": source_stats
        }
        
    except Exception as e:
        logger.error(f"Error calculating conversion KPIs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# POINT 6: SOURCES QUI CONVERTISSENT LE MIEUX
# ==========================================

@router.get("/kpi/source-performance")
async def get_source_performance(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """
    Get source performance metrics (funnel analysis)
    Shows which sources convert best
    """
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
        
        # Get all leads in period
        leads = await db.leads.find({
            "created_at": {"$gte": start_date}
        }).to_list(length=2000)
        
        # Aggregate by source
        sources = {}
        for lead in leads:
            source = lead.get("source") or lead.get("utm_source") or "direct"
            
            if source not in sources:
                sources[source] = {
                    "total": 0,
                    "contacted": 0,
                    "qualified": 0,
                    "converted": 0,
                    "lost": 0,
                    "opportunities": 0,
                    "revenue": 0
                }
            
            sources[source]["total"] += 1
            status = lead.get("status", "new")
            stage = lead.get("stage", "")
            
            if status in ["contacted", "qualified", "negotiation", "converted"]:
                sources[source]["contacted"] += 1
            if status in ["qualified", "negotiation", "converted"]:
                sources[source]["qualified"] += 1
            if status == "converted":
                sources[source]["converted"] += 1
            if status == "lost":
                sources[source]["lost"] += 1
        
        # Get opportunities for each source
        for source_name in sources:
            # Find contacts from this source
            contacts_from_source = await db.contacts.find({
                "source": source_name
            }).to_list(length=500)
            
            contact_ids = [str(c.get("_id", c.get("contact_id"))) for c in contacts_from_source]
            
            if contact_ids:
                # Get opportunities for these contacts
                opps = await db.opportunities.find({
                    "contact_id": {"$in": contact_ids}
                }).to_list(length=200)
                
                sources[source_name]["opportunities"] = len(opps)
                sources[source_name]["revenue"] = sum(o.get("value", 0) or 0 for o in opps)
        
        # Calculate conversion rates
        result = []
        for source_name, data in sources.items():
            total = data["total"]
            result.append({
                "source": source_name,
                "total_leads": total,
                "contacted": data["contacted"],
                "qualified": data["qualified"],
                "converted": data["converted"],
                "lost": data["lost"],
                "opportunities": data["opportunities"],
                "revenue": data["revenue"],
                "contact_rate": round((data["contacted"] / total) * 100, 1) if total > 0 else 0,
                "qualification_rate": round((data["qualified"] / total) * 100, 1) if total > 0 else 0,
                "conversion_rate": round((data["converted"] / total) * 100, 1) if total > 0 else 0,
                "avg_revenue_per_lead": round(data["revenue"] / total, 2) if total > 0 else 0
            })
        
        # Sort by conversion rate
        result.sort(key=lambda x: x["conversion_rate"], reverse=True)
        
        # Calculate totals
        totals = {
            "total_leads": sum(s["total_leads"] for s in result),
            "total_converted": sum(s["converted"] for s in result),
            "total_revenue": sum(s["revenue"] for s in result),
            "best_source": result[0]["source"] if result else None,
            "best_conversion_rate": result[0]["conversion_rate"] if result else 0
        }
        
        return {
            "period": period,
            "sources": result,
            "totals": totals
        }
        
    except Exception as e:
        logger.error(f"Error calculating source performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpi/funnel")
async def get_sales_funnel(
    period: str = Query("month", regex="^(week|month|quarter|year)$"),
    user: Dict = Depends(get_current_user)
):
    """
    Get sales funnel visualization data
    """
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
        
        # Count at each stage
        stages = [
            ("new_leads", {"created_at": {"$gte": start_date}}),
            ("contacted", {"created_at": {"$gte": start_date}, "status": {"$in": ["contacted", "qualified", "negotiation", "converted"]}}),
            ("qualified", {"created_at": {"$gte": start_date}, "status": {"$in": ["qualified", "negotiation", "converted"]}}),
            ("converted", {"created_at": {"$gte": start_date}, "status": "converted"})
        ]
        
        funnel = []
        prev_count = None
        
        for stage_name, query in stages:
            count = await db.leads.count_documents(query)
            drop_rate = 0
            if prev_count is not None and prev_count > 0:
                drop_rate = round(((prev_count - count) / prev_count) * 100, 1)
            
            funnel.append({
                "stage": stage_name,
                "count": count,
                "drop_rate": drop_rate
            })
            prev_count = count
        
        # Opportunities funnel
        opp_stages = [
            ("qualification", "qualification"),
            ("proposal", "proposal"),
            ("negotiation", "negotiation"),
            ("closed_won", "closed_won")
        ]
        
        opp_funnel = []
        for stage_name, stage_value in opp_stages:
            count = await db.opportunities.count_documents({
                "created_at": {"$gte": start_date},
                "stage": stage_value
            })
            opp_funnel.append({
                "stage": stage_name,
                "count": count
            })
        
        return {
            "period": period,
            "lead_funnel": funnel,
            "opportunity_funnel": opp_funnel
        }
        
    except Exception as e:
        logger.error(f"Error calculating funnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))
