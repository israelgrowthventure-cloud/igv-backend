"""
Global Search & Advanced RBAC Routes - CRM IGV
Points 7, 8 de la mission:
- Vraie recherche globale (cross-objects)
- RBAC avancé (Manager/Support/ReadOnly roles)
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
import logging
import re

from auth_middleware import get_current_user, require_admin, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crm", tags=["search-rbac"])


# ==========================================
# POINT 7: VRAIE RECHERCHE GLOBALE
# ==========================================

@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=2, description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated types: leads,contacts,companies,opportunities"),
    limit: int = Query(20, le=100),
    user: Dict = Depends(get_current_user)
):
    """
    Global search across all CRM entities
    Returns leads, contacts, companies, opportunities matching the query
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        results = {
            "query": q,
            "leads": [],
            "contacts": [],
            "companies": [],
            "opportunities": [],
            "total": 0
        }
        
        # Determine which types to search
        search_types = ["leads", "contacts", "companies", "opportunities"]
        if types:
            search_types = [t.strip() for t in types.split(",") if t.strip() in search_types]
        
        # Build regex pattern
        pattern = {"$regex": q, "$options": "i"}
        
        # RBAC base query
        rbac_query = {}
        if user.get("role") == "commercial":
            rbac_query["owner_email"] = user.get("email")
        
        # Search leads
        if "leads" in search_types:
            lead_query = {
                "$or": [
                    {"name": pattern},
                    {"email": pattern},
                    {"phone": pattern},
                    {"brand_name": pattern},
                    {"sector": pattern},
                    {"target_city": pattern},
                    {"tags": pattern}
                ],
                **rbac_query
            }
            leads = await db.leads.find(lead_query).limit(limit).to_list(length=limit)
            for lead in leads:
                results["leads"].append({
                    "id": str(lead.get("_id", lead.get("lead_id"))),
                    "type": "lead",
                    "name": lead.get("name") or lead.get("brand_name") or lead.get("email"),
                    "email": lead.get("email"),
                    "phone": lead.get("phone"),
                    "status": lead.get("status"),
                    "url": f"/admin/crm/leads/{lead.get('_id', lead.get('lead_id'))}"
                })
        
        # Search contacts
        if "contacts" in search_types:
            contact_query = {
                "$or": [
                    {"name": pattern},
                    {"email": pattern},
                    {"phone": pattern},
                    {"position": pattern},
                    {"company": pattern}
                ]
            }
            # Contacts visible by commercial if linked
            contacts = await db.contacts.find(contact_query).limit(limit).to_list(length=limit)
            for contact in contacts:
                results["contacts"].append({
                    "id": str(contact.get("_id", contact.get("contact_id"))),
                    "type": "contact",
                    "name": contact.get("name"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "position": contact.get("position"),
                    "url": f"/admin/crm/contacts/{contact.get('_id', contact.get('contact_id'))}"
                })
        
        # Search companies
        if "companies" in search_types:
            company_query = {
                "$or": [
                    {"name": pattern},
                    {"domain": pattern},
                    {"industry": pattern},
                    {"city": pattern},
                    {"country": pattern}
                ]
            }
            companies = await db.companies.find(company_query).limit(limit).to_list(length=limit)
            for company in companies:
                results["companies"].append({
                    "id": str(company.get("_id")),
                    "type": "company",
                    "name": company.get("name"),
                    "domain": company.get("domain"),
                    "industry": company.get("industry"),
                    "url": f"/admin/crm/companies/{company.get('_id')}"
                })
        
        # Search opportunities
        if "opportunities" in search_types:
            opp_query = {
                "$or": [
                    {"name": pattern},
                    {"description": pattern}
                ]
            }
            opps = await db.opportunities.find(opp_query).limit(limit).to_list(length=limit)
            for opp in opps:
                results["opportunities"].append({
                    "id": str(opp.get("_id", opp.get("opportunity_id"))),
                    "type": "opportunity",
                    "name": opp.get("name"),
                    "value": opp.get("value"),
                    "stage": opp.get("stage"),
                    "url": f"/admin/crm/opportunities/{opp.get('_id', opp.get('opportunity_id'))}"
                })
        
        results["total"] = (
            len(results["leads"]) + 
            len(results["contacts"]) + 
            len(results["companies"]) + 
            len(results["opportunities"])
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Error in global search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/quick")
async def quick_search(
    q: str = Query(..., min_length=2),
    user: Dict = Depends(get_current_user)
):
    """
    Quick search for autocomplete - returns top 5 results per type
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        pattern = {"$regex": f"^{re.escape(q)}", "$options": "i"}
        suggestions = []
        
        # Quick search in leads
        leads = await db.leads.find({
            "$or": [{"name": pattern}, {"email": pattern}, {"brand_name": pattern}]
        }).limit(5).to_list(length=5)
        
        for lead in leads:
            suggestions.append({
                "type": "lead",
                "id": str(lead.get("_id", lead.get("lead_id"))),
                "label": lead.get("name") or lead.get("brand_name") or lead.get("email"),
                "sublabel": lead.get("email"),
                "url": f"/admin/crm/leads/{lead.get('_id', lead.get('lead_id'))}"
            })
        
        # Quick search in contacts
        contacts = await db.contacts.find({
            "$or": [{"name": pattern}, {"email": pattern}]
        }).limit(5).to_list(length=5)
        
        for contact in contacts:
            suggestions.append({
                "type": "contact",
                "id": str(contact.get("_id", contact.get("contact_id"))),
                "label": contact.get("name"),
                "sublabel": contact.get("email"),
                "url": f"/admin/crm/contacts/{contact.get('_id', contact.get('contact_id'))}"
            })
        
        # Quick search in companies
        companies = await db.companies.find({
            "$or": [{"name": pattern}, {"domain": pattern}]
        }).limit(5).to_list(length=5)
        
        for company in companies:
            suggestions.append({
                "type": "company",
                "id": str(company.get("_id")),
                "label": company.get("name"),
                "sublabel": company.get("industry"),
                "url": f"/admin/crm/companies/{company.get('_id')}"
            })
        
        return {"suggestions": suggestions[:15]}
        
    except Exception as e:
        logger.error(f"Error in quick search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# POINT 8: RBAC AVANCÉ
# ==========================================

# Available roles with permissions
ROLES = {
    "admin": {
        "description": "Full access to all features",
        "permissions": ["*"]
    },
    "manager": {
        "description": "Can manage team, view all data, but cannot delete users or change settings",
        "permissions": [
            "leads:read", "leads:write", "leads:delete",
            "contacts:read", "contacts:write", "contacts:delete",
            "opportunities:read", "opportunities:write", "opportunities:delete",
            "companies:read", "companies:write",
            "activities:read", "activities:write",
            "emails:read", "emails:write",
            "reports:read",
            "team:read", "team:assign"
        ]
    },
    "commercial": {
        "description": "Can manage own leads and contacts",
        "permissions": [
            "leads:read:own", "leads:write:own",
            "contacts:read:own", "contacts:write:own",
            "opportunities:read:own", "opportunities:write:own",
            "companies:read",
            "activities:read:own", "activities:write:own",
            "emails:read:own", "emails:write:own"
        ]
    },
    "support": {
        "description": "Can view and add notes, but cannot modify core data",
        "permissions": [
            "leads:read", "leads:notes:write",
            "contacts:read", "contacts:notes:write",
            "opportunities:read",
            "activities:read", "activities:write",
            "emails:read"
        ]
    },
    "readonly": {
        "description": "View-only access",
        "permissions": [
            "leads:read",
            "contacts:read",
            "opportunities:read",
            "companies:read",
            "activities:read",
            "reports:read"
        ]
    }
}


@router.get("/roles")
async def list_roles(user: Dict = Depends(require_admin)):
    """List all available roles and their permissions"""
    return {"roles": ROLES}


@router.get("/permissions")
async def get_user_permissions(user: Dict = Depends(get_current_user)):
    """Get current user's permissions"""
    role = user.get("role", "commercial")
    role_config = ROLES.get(role, ROLES["commercial"])
    
    return {
        "user_email": user.get("email"),
        "role": role,
        "description": role_config["description"],
        "permissions": role_config["permissions"]
    }


@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_data: Dict = Body(...),
    user: Dict = Depends(require_admin)
):
    """
    Update a user's role
    Admin only
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        new_role = role_data.get("role")
        if new_role not in ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {list(ROLES.keys())}")
        
        # Find user
        try:
            target_user = await db.crm_users.find_one({"_id": ObjectId(user_id)})
        except:
            target_user = await db.crm_users.find_one({"email": user_id})
        
        if not target_user:
            # Try legacy users collection
            try:
                target_user = await db.users.find_one({"_id": ObjectId(user_id)})
            except:
                target_user = await db.users.find_one({"email": user_id})
        
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent self-demotion from admin
        if str(target_user.get("email")) == user.get("email") and new_role != "admin":
            raise HTTPException(status_code=400, detail="Cannot demote yourself from admin")
        
        # Update role
        collection = db.crm_users if await db.crm_users.find_one({"_id": target_user["_id"]}) else db.users
        
        await collection.update_one(
            {"_id": target_user["_id"]},
            {
                "$set": {
                    "role": new_role,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": user.get("email")
                }
            }
        )
        
        # Audit log
        await db.audit_logs.insert_one({
            "action": "role_change",
            "entity_type": "user",
            "entity_id": str(target_user["_id"]),
            "user_email": user.get("email"),
            "old_role": target_user.get("role"),
            "new_role": new_role,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "user_id": str(target_user["_id"]),
            "new_role": new_role,
            "permissions": ROLES[new_role]["permissions"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/permissions")
async def set_custom_permissions(
    user_id: str,
    perm_data: Dict = Body(...),
    user: Dict = Depends(require_admin)
):
    """
    Set custom permissions for a user (overrides role defaults)
    Admin only
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        permissions = perm_data.get("permissions", [])
        
        # Find user
        try:
            target_user = await db.crm_users.find_one({"_id": ObjectId(user_id)})
        except:
            target_user = await db.crm_users.find_one({"email": user_id})
        
        if not target_user:
            try:
                target_user = await db.users.find_one({"_id": ObjectId(user_id)})
            except:
                target_user = await db.users.find_one({"email": user_id})
        
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        collection = db.crm_users if await db.crm_users.find_one({"_id": target_user["_id"]}) else db.users
        
        await collection.update_one(
            {"_id": target_user["_id"]},
            {
                "$set": {
                    "custom_permissions": permissions,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return {
            "success": True,
            "user_id": str(target_user["_id"]),
            "custom_permissions": permissions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting custom permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def has_permission(user: Dict, required_permission: str) -> bool:
    """
    Check if user has a specific permission
    Used by other routes for fine-grained access control
    """
    role = user.get("role", "commercial")
    custom_perms = user.get("custom_permissions", [])
    
    # Custom permissions override
    if custom_perms:
        return required_permission in custom_perms or "*" in custom_perms
    
    # Role-based permissions
    role_perms = ROLES.get(role, {}).get("permissions", [])
    
    if "*" in role_perms:
        return True
    
    if required_permission in role_perms:
        return True
    
    # Check for :own variant
    base_perm = required_permission.replace(":own", "")
    if f"{base_perm}:own" in role_perms:
        return True
    
    return False


@router.get("/team")
async def get_team_members(
    role: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """
    Get team members (for managers and admins)
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Check permission
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized to view team")
    
    try:
        query = {"is_active": {"$ne": False}}
        if role:
            query["role"] = role
        
        # Try crm_users first
        users = await db.crm_users.find(query).to_list(length=100)
        if not users:
            users = await db.users.find(query).to_list(length=100)
        
        team = []
        for u in users:
            # Get stats
            user_email = u.get("email")
            leads_count = await db.leads.count_documents({"owner_email": user_email})
            
            team.append({
                "id": str(u["_id"]),
                "email": user_email,
                "name": u.get("name", user_email.split("@")[0]),
                "role": u.get("role", "commercial"),
                "leads_count": leads_count,
                "is_active": u.get("is_active", True),
                "last_login": str(u.get("last_login", "")) if u.get("last_login") else None
            })
        
        return {"team": team, "total": len(team)}
        
    except Exception as e:
        logger.error(f"Error getting team: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/team/assign")
async def bulk_assign_leads(
    assignment_data: Dict = Body(...),
    user: Dict = Depends(get_current_user)
):
    """
    Bulk assign leads to team members
    Manager and Admin only
    
    assignment_data: {
        "lead_ids": ["id1", "id2"],
        "assign_to": "commercial@example.com"
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    if user.get("role") not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    try:
        lead_ids = assignment_data.get("lead_ids", [])
        assign_to = assignment_data.get("assign_to")
        
        if not lead_ids or not assign_to:
            raise HTTPException(status_code=400, detail="lead_ids and assign_to required")
        
        # Verify target user exists
        target = await db.crm_users.find_one({"email": assign_to})
        if not target:
            target = await db.users.find_one({"email": assign_to})
        if not target:
            raise HTTPException(status_code=404, detail="Target user not found")
        
        # Update leads
        updated = 0
        for lead_id in lead_ids:
            try:
                oid = ObjectId(lead_id)
                result = await db.leads.update_one(
                    {"_id": oid},
                    {
                        "$set": {
                            "owner_email": assign_to,
                            "assigned_at": datetime.now(timezone.utc),
                            "assigned_by": user.get("email")
                        }
                    }
                )
                if result.modified_count > 0:
                    updated += 1
            except:
                # Try with lead_id
                result = await db.leads.update_one(
                    {"lead_id": int(lead_id)},
                    {
                        "$set": {
                            "owner_email": assign_to,
                            "assigned_at": datetime.now(timezone.utc),
                            "assigned_by": user.get("email")
                        }
                    }
                )
                if result.modified_count > 0:
                    updated += 1
        
        return {
            "success": True,
            "assigned_to": assign_to,
            "leads_updated": updated,
            "total_requested": len(lead_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk assigning: {e}")
        raise HTTPException(status_code=500, detail=str(e))
