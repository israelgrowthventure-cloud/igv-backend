"""
Canonical Handlers Export Module
================================
Ce module ré-exporte les handlers et modèles canoniques
pour éviter les circular imports dans api_bridge.py.

Usage dans api_bridge.py:
    from canonical_handlers import (
        AdminLoginRequest,
        admin_login,
        get_stats,
        get_dashboard_stats,
        get_crm_users,
        ...
    )
"""

from pydantic import BaseModel, EmailStr


# ============================================================
# PYDANTIC MODELS - Canonical definitions
# ============================================================

class AdminLoginRequest(BaseModel):
    """Login request model - canonical definition shared with server.py"""
    email: EmailStr
    password: str


# ============================================================
# LAZY HANDLER IMPORTS
# ============================================================
# Note: handlers are imported lazily to avoid circular imports
# when server.py imports api_bridge during app initialization.

_handlers_cache = {}


def _get_handler(module_name: str, handler_name: str):
    """Lazy import handler to avoid circular imports"""
    cache_key = f"{module_name}.{handler_name}"
    if cache_key not in _handlers_cache:
        import importlib
        module = importlib.import_module(module_name)
        _handlers_cache[cache_key] = getattr(module, handler_name)
    return _handlers_cache[cache_key]


# Auth handlers
async def admin_login(credentials: AdminLoginRequest):
    """Forward to server.admin_login"""
    handler = _get_handler("server", "admin_login")
    return await handler(credentials)


async def get_stats(user):
    """Forward to server.get_stats"""
    handler = _get_handler("server", "get_stats")
    return await handler(user)


# CRM Dashboard
async def get_dashboard_stats(user):
    """Forward to crm_complete_routes.get_dashboard_stats"""
    handler = _get_handler("crm_complete_routes", "get_dashboard_stats")
    return await handler(user)


async def get_crm_users(user):
    """Forward to crm_complete_routes.get_crm_users"""
    handler = _get_handler("crm_complete_routes", "get_crm_users")
    return await handler(user)


# Automation handlers
async def list_automation_rules(user):
    """Forward to automation_kpi_routes.list_automation_rules"""
    handler = _get_handler("automation_kpi_routes", "list_automation_rules")
    return await handler(user)


async def create_automation_rule(rule_data, user):
    """Forward to automation_kpi_routes.create_automation_rule"""
    handler = _get_handler("automation_kpi_routes", "create_automation_rule")
    return await handler(rule_data, user)


async def update_automation_rule(rule_id, rule_data, user):
    """Forward to automation_kpi_routes.update_automation_rule"""
    handler = _get_handler("automation_kpi_routes", "update_automation_rule")
    return await handler(rule_id, rule_data, user)


async def delete_automation_rule(rule_id, user):
    """Forward to automation_kpi_routes.delete_automation_rule"""
    handler = _get_handler("automation_kpi_routes", "delete_automation_rule")
    return await handler(rule_id, user)


async def execute_automation_rules(user):
    """Forward to automation_kpi_routes.execute_automation_rules"""
    handler = _get_handler("automation_kpi_routes", "execute_automation_rules")
    return await handler(user)


# Audit handlers
async def list_audit_logs(entity_type, entity_id, user_email, action, limit, skip, user):
    """Forward to mini_analysis_audit_routes.list_audit_logs"""
    handler = _get_handler("mini_analysis_audit_routes", "list_audit_logs")
    return await handler(entity_type, entity_id, user_email, action, limit, skip, user)


async def get_audit_stats(user):
    """Forward to mini_analysis_audit_routes.get_audit_stats"""
    handler = _get_handler("mini_analysis_audit_routes", "get_audit_stats")
    return await handler(user)


async def get_entity_audit_history(entity_type, entity_id, user):
    """Forward to mini_analysis_audit_routes.get_entity_audit_history"""
    handler = _get_handler("mini_analysis_audit_routes", "get_entity_audit_history")
    return await handler(entity_type, entity_id, user)


async def get_user_activity_log(user_email, start_date, limit, user):
    """Forward to mini_analysis_audit_routes.get_user_activity_log"""
    handler = _get_handler("mini_analysis_audit_routes", "get_user_activity_log")
    return await handler(user_email, start_date, limit, user)


# RBAC handlers
async def list_roles(user):
    """Forward to search_rbac_routes.list_roles"""
    handler = _get_handler("search_rbac_routes", "list_roles")
    return await handler(user)


async def get_user_permissions(user):
    """Forward to search_rbac_routes.get_user_permissions"""
    handler = _get_handler("search_rbac_routes", "get_user_permissions")
    return await handler(user)


async def update_user_role(user_id, role_data, user):
    """Forward to search_rbac_routes.update_user_role"""
    handler = _get_handler("search_rbac_routes", "update_user_role")
    return await handler(user_id, role_data, user)


# Quality handlers
async def detect_lead_duplicates(threshold, limit, user):
    """Forward to quality_routes.detect_lead_duplicates"""
    handler = _get_handler("quality_routes", "detect_lead_duplicates")
    return await handler(threshold, limit, user)


async def detect_contact_duplicates(threshold, limit, user):
    """Forward to quality_routes.detect_contact_duplicates"""
    handler = _get_handler("quality_routes", "detect_contact_duplicates")
    return await handler(threshold, limit, user)
