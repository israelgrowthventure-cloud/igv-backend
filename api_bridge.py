"""
API Bridge Module - IGV Backend
================================
STRICT ALIAS LAYER - Aucune logique métier ici.

PRINCIPES STRICTS:
1. Ce module contient UNIQUEMENT des forwards vers les handlers canoniques
2. INTERDIT: Dupliquer une route canonique avec include_in_schema=False
3. INTERDIT: Contenir du code MongoDB/logique métier
4. Les aliases doivent appeler les VRAIES fonctions canoniques existantes
5. Re-raise HTTPException tel quel, ne jamais transformer en 500
6. INTERDIT: Exposer str(e) au client - logs détaillés server-side uniquement
7. Chaque erreur retourne un error_id unique pour traçabilité

Date: 26 Janvier 2026
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Dict, Optional
from datetime import datetime, timezone
import logging
import uuid

from auth_middleware import get_current_user, require_admin

# Import canonical handlers and models (no circular import)
from canonical_handlers import (
    AdminLoginRequest,
    admin_login,
    get_stats,
    get_dashboard_stats,
    get_crm_users,
    list_automation_rules,
    create_automation_rule,
    update_automation_rule,
    delete_automation_rule,
    execute_automation_rules,
    list_audit_logs,
    get_audit_stats,
    get_entity_audit_history,
    get_user_activity_log,
    list_roles,
    get_user_permissions,
    update_user_role,
    detect_lead_duplicates,
    detect_contact_duplicates,
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

# Documentation only - actual aliases are implemented below
ROUTE_ALIASES = {
    # Auth aliases
    "/api/login": "/api/admin/login",
    "/api/auth/login": "/api/admin/login",
    
    # Stats aliases
    "/api/stats": "/api/admin/stats",
    "/api/crm/stats": "/api/crm/dashboard/stats",
    
    # CRM module aliases
    "/api/crm/automation": "/api/crm/rules",
    "/api/crm/automation/rules": "/api/crm/rules",
    "/api/crm/audit": "/api/crm/audit-logs",
}


def log_legacy_route(original_path: str, canonical_path: str, method: str = "GET"):
    """Log when a legacy route is used"""
    logger.warning(
        f"LEGACY_ROUTE_USED: {method} {original_path} -> {canonical_path} "
        f"[timestamp={datetime.now(timezone.utc).isoformat()}]"
    )


def generate_error_id() -> str:
    """Generate unique error ID for traceability"""
    return str(uuid.uuid4())[:8]


def log_and_raise_error(context: str, exc: Exception) -> None:
    """Log exception with traceback and raise HTTPException with error_id"""
    error_id = generate_error_id()
    logger.exception(f"[{error_id}] {context}: {type(exc).__name__}")
    raise HTTPException(
        status_code=500,
        detail=f"Internal error. Reference: {error_id}"
    )


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(tags=["api-bridge"])


# ============================================================
# AUTH ALIASES - Forward to canonical handlers
# ============================================================

@router.post("/api/login")
async def legacy_login(request: Request):
    """
    Legacy alias: /api/login -> /api/admin/login
    Forwards to canonical handler via canonical_handlers module
    """
    log_legacy_route("/api/login", "/api/admin/login", "POST")
    
    try:
        body = await request.json()
        credentials = AdminLoginRequest(**body)
        return await admin_login(credentials)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy login", e)


@router.post("/api/auth/login")
async def legacy_auth_login(request: Request):
    """
    Legacy alias: /api/auth/login -> /api/admin/login
    """
    log_legacy_route("/api/auth/login", "/api/admin/login", "POST")
    
    try:
        body = await request.json()
        credentials = AdminLoginRequest(**body)
        return await admin_login(credentials)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy auth login", e)


# ============================================================
# STATS ALIASES - Forward to canonical handlers
# ============================================================

@router.get("/api/stats")
async def legacy_stats(user: Dict = Depends(get_current_user)):
    """
    Legacy alias: /api/stats -> /api/admin/stats
    Forwards to canonical handler via canonical_handlers module
    """
    log_legacy_route("/api/stats", "/api/admin/stats", "GET")
    
    try:
        return await get_stats(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy stats", e)


@router.get("/api/crm/stats")
async def legacy_crm_stats(user: Dict = Depends(get_current_user)):
    """
    Legacy alias: /api/crm/stats -> /api/crm/dashboard/stats
    Forwards to canonical handler via canonical_handlers module
    """
    log_legacy_route("/api/crm/stats", "/api/crm/dashboard/stats", "GET")
    
    try:
        return await get_dashboard_stats(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy CRM stats", e)


# ============================================================
# CRM AUTOMATION ALIASES (automation -> rules)
# ============================================================

@router.get("/api/crm/automation")
async def legacy_automation_list(user: Dict = Depends(require_admin)):
    """
    Legacy alias: /api/crm/automation -> /api/crm/rules
    """
    log_legacy_route("/api/crm/automation", "/api/crm/rules", "GET")
    
    try:
        return await list_automation_rules(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation list", e)


@router.get("/api/crm/automation/rules")
async def legacy_automation_rules_list(user: Dict = Depends(require_admin)):
    """
    Legacy alias: /api/crm/automation/rules -> /api/crm/rules
    """
    log_legacy_route("/api/crm/automation/rules", "/api/crm/rules", "GET")
    
    try:
        return await list_automation_rules(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation rules list", e)


@router.post("/api/crm/automation/rules")
async def legacy_automation_rules_create(
    request: Request,
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: POST /api/crm/automation/rules -> POST /api/crm/rules
    """
    log_legacy_route("/api/crm/automation/rules", "/api/crm/rules", "POST")
    
    try:
        body = await request.json()
        return await create_automation_rule(body, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation rule create", e)


@router.put("/api/crm/automation/rules/{rule_id}")
async def legacy_automation_rules_update(
    rule_id: str,
    request: Request,
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: PUT /api/crm/automation/rules/{id} -> PUT /api/crm/rules/{id}
    """
    log_legacy_route(f"/api/crm/automation/rules/{rule_id}", f"/api/crm/rules/{rule_id}", "PUT")
    
    try:
        body = await request.json()
        return await update_automation_rule(rule_id, body, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation rule update", e)


@router.delete("/api/crm/automation/rules/{rule_id}")
async def legacy_automation_rules_delete(
    rule_id: str,
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: DELETE /api/crm/automation/rules/{id} -> DELETE /api/crm/rules/{id}
    """
    log_legacy_route(f"/api/crm/automation/rules/{rule_id}", f"/api/crm/rules/{rule_id}", "DELETE")
    
    try:
        return await delete_automation_rule(rule_id, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation rule delete", e)


@router.post("/api/crm/automation/execute")
async def legacy_automation_execute(user: Dict = Depends(require_admin)):
    """
    Legacy alias: POST /api/crm/automation/execute -> POST /api/crm/rules/execute
    """
    log_legacy_route("/api/crm/automation/execute", "/api/crm/rules/execute", "POST")
    
    try:
        return await execute_automation_rules(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy automation execute", e)


# ============================================================
# CRM AUDIT ALIASES (audit -> audit-logs)
# ============================================================

@router.get("/api/crm/audit")
async def legacy_audit_list(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    skip: int = Query(0),
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: /api/crm/audit -> /api/crm/audit-logs
    """
    log_legacy_route("/api/crm/audit", "/api/crm/audit-logs", "GET")
    
    try:
        return await list_audit_logs(entity_type, entity_id, user_email, action, limit, skip, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy audit list", e)


@router.get("/api/crm/audit/stats")
async def legacy_audit_stats(user: Dict = Depends(require_admin)):
    """
    Legacy alias: /api/crm/audit/stats -> /api/crm/audit-logs/stats
    """
    log_legacy_route("/api/crm/audit/stats", "/api/crm/audit-logs/stats", "GET")
    
    try:
        return await get_audit_stats(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy audit stats", e)


@router.get("/api/crm/audit/entity/{entity_type}/{entity_id}")
async def legacy_audit_entity(
    entity_type: str,
    entity_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Legacy alias: /api/crm/audit/entity/{type}/{id} -> /api/crm/audit-logs/entity/{type}/{id}
    """
    log_legacy_route(
        f"/api/crm/audit/entity/{entity_type}/{entity_id}",
        f"/api/crm/audit-logs/entity/{entity_type}/{entity_id}",
        "GET"
    )
    
    try:
        return await get_entity_audit_history(entity_type, entity_id, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy audit entity", e)


@router.get("/api/crm/audit/user/{user_email}")
async def legacy_audit_user(
    user_email: str,
    limit: int = Query(100),
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: /api/crm/audit/user/{email} -> /api/crm/audit-logs/user/{email}
    """
    log_legacy_route(
        f"/api/crm/audit/user/{user_email}",
        f"/api/crm/audit-logs/user/{user_email}",
        "GET"
    )
    
    try:
        return await get_user_activity_log(user_email, None, limit, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy audit user", e)


# ============================================================
# RBAC ALIASES
# ============================================================

@router.get("/api/crm/roles")
async def legacy_roles_list(user: Dict = Depends(require_admin)):
    """
    Legacy alias: /api/crm/roles -> /api/crm/rbac/roles
    """
    log_legacy_route("/api/crm/roles", "/api/crm/rbac/roles", "GET")
    
    try:
        return await list_roles(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy roles list", e)


@router.get("/api/crm/permissions")
async def legacy_permissions(user: Dict = Depends(get_current_user)):
    """
    Legacy alias: /api/crm/permissions -> /api/crm/rbac/permissions
    """
    log_legacy_route("/api/crm/permissions", "/api/crm/rbac/permissions", "GET")
    
    try:
        return await get_user_permissions(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy permissions", e)


@router.put("/api/crm/users/{user_id}/role")
async def legacy_update_user_role(
    user_id: str,
    request: Request,
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: PUT /api/crm/users/{id}/role -> PUT /api/crm/rbac/users/{id}/role
    """
    log_legacy_route(f"/api/crm/users/{user_id}/role", f"/api/crm/rbac/users/{user_id}/role", "PUT")
    
    try:
        body = await request.json()
        return await update_user_role(user_id, body, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy update user role", e)


# ============================================================
# QUALITY ALIASES
# ============================================================

@router.get("/api/crm/duplicates/leads")
async def legacy_duplicates_leads(
    threshold: float = Query(0.8, ge=0.5, le=1.0),
    limit: int = Query(100, le=500),
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: /api/crm/duplicates/leads -> /api/crm/quality/duplicates/leads
    """
    log_legacy_route("/api/crm/duplicates/leads", "/api/crm/quality/duplicates/leads", "GET")
    
    try:
        return await detect_lead_duplicates(threshold, limit, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy duplicates leads", e)


@router.get("/api/crm/duplicates/contacts")
async def legacy_duplicates_contacts(
    threshold: float = Query(0.8, ge=0.5, le=1.0),
    limit: int = Query(100, le=500),
    user: Dict = Depends(require_admin)
):
    """
    Legacy alias: /api/crm/duplicates/contacts -> /api/crm/quality/duplicates/contacts
    """
    log_legacy_route("/api/crm/duplicates/contacts", "/api/crm/quality/duplicates/contacts", "GET")
    
    try:
        return await detect_contact_duplicates(threshold, limit, user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy duplicates contacts", e)


# ============================================================
# TEAM/USERS ALIASES - Forward to canonical handlers
# ============================================================

@router.get("/api/crm/team")
async def legacy_team_list(user: Dict = Depends(get_current_user)):
    """
    Legacy alias: /api/crm/team -> /api/crm/settings/users
    """
    log_legacy_route("/api/crm/team", "/api/crm/settings/users", "GET")
    
    try:
        return await get_crm_users(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy team list", e)


@router.get("/api/crm/users")
async def legacy_crm_users(user: Dict = Depends(get_current_user)):
    """
    Legacy alias: /api/crm/users -> /api/crm/settings/users
    """
    log_legacy_route("/api/crm/users", "/api/crm/settings/users", "GET")
    
    try:
        return await get_crm_users(user)
    except HTTPException:
        raise
    except Exception as e:
        log_and_raise_error("Legacy CRM users", e)


logger.info("✓ API Bridge module loaded - Legacy routes enabled with logging")
