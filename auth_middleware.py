"""
Auth Middleware - Centralized Authentication & RBAC
Provides JWT verification, role-based access control, and MongoDB filtering
"""

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
import os
import logging
import jwt
from functools import wraps

# Security
security = HTTPBearer()

# MongoDB
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

mongo_client = None
db = None

def get_db():
    """Get MongoDB database instance"""
    global mongo_client, db
    if db is None and mongo_url:
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client[db_name]
    return db

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'


# ==========================================
# CORE AUTH FUNCTIONS
# ==========================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Verify JWT token and return current user data.
    
    Returns:
        dict: {
            "id": str,
            "email": str,
            "name": str,
            "role": str (admin|commercial),
            "assigned_leads": list (for commercial users)
        }
    
    Raises:
        HTTPException 401: Invalid or expired token
        HTTPException 403: Inactive user
        HTTPException 500: Database not configured
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        current_db = get_db()
        if current_db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        
        email = payload.get("email")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Search in crm_users first (new collection), then fallback to users (legacy)
        user = await current_db.crm_users.find_one({"email": email})
        if not user:
            user = await current_db.users.find_one({"email": email})
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="User account is inactive")
        
        # Construct user object
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user.get("name", email.split("@")[0]),
            "role": user.get("role", "admin"),  # Default admin for legacy users
            "assigned_leads": user.get("assigned_leads", [])
        }
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logging.error(f"Auth error in get_current_user: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")


async def require_role(required_roles: List[str], user: Dict[str, Any]) -> None:
    """
    Verify user has one of the required roles.
    
    Args:
        required_roles: List of allowed roles (e.g., ["admin"])
        user: Current user from get_current_user dependency
    
    Raises:
        HTTPException 403: User doesn't have required role
    """
    if user["role"] not in required_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Required role: {', '.join(required_roles)}. Your role: {user['role']}"
        )


async def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependency that requires admin role.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: Dict = Depends(require_admin)):
            ...
    
    Returns:
        dict: Current user data
    
    Raises:
        HTTPException 403: User is not admin
    """
    await require_role(["admin"], user)
    return user


async def get_user_or_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependency that allows both admin and commercial users.
    Returns user data for filtering in route logic.
    
    Usage:
        @router.get("/leads")
        async def get_leads(user: Dict = Depends(get_user_or_admin)):
            filter = get_user_assigned_filter(user, "leads")
            leads = await db.leads.find(filter).to_list(100)
    """
    await require_role(["admin", "commercial"], user)
    return user


# ==========================================
# RBAC FILTERING HELPERS
# ==========================================

def get_user_assigned_filter(user: Dict[str, Any], entity_type: str = "leads") -> Dict[str, Any]:
    """
    Generate MongoDB filter based on user role and assigned entities.
    
    Business Rules:
    - BR002: Admin sees ALL entities (no filter)
    - BR003: Commercial sees ONLY assigned entities
    
    Args:
        user: Current user dict from get_current_user
        entity_type: Type of entity (leads, contacts, opportunities, activities)
    
    Returns:
        dict: MongoDB filter query
            - Admin: {} (empty = all records)
            - Commercial: {"assigned_to": user["email"]} or {"_id": {"$in": assigned_ids}}
    
    Examples:
        # Admin user
        get_user_assigned_filter(admin_user, "leads")
        # Returns: {}
        
        # Commercial user
        get_user_assigned_filter(commercial_user, "leads")
        # Returns: {"assigned_to": "commercial@example.com"}
    """
    
    # Admin sees everything
    if user["role"] == "admin":
        return {}
    
    # Commercial sees only assigned items
    if user["role"] == "commercial":
        # For leads/contacts/opportunities: filter by assigned_to field
        if entity_type in ["leads", "contacts", "opportunities"]:
            return {"assigned_to": user["email"]}
        
        # For activities: filter by user_id or assigned leads
        if entity_type == "activities":
            return {
                "$or": [
                    {"user_id": user["id"]},
                    {"lead_id": {"$in": user.get("assigned_leads", [])}}
                ]
            }
        
        # Default: filter by assigned_to
        return {"assigned_to": user["email"]}
    
    # Unknown role: deny all
    logging.warning(f"Unknown role {user['role']} for user {user['email']}")
    return {"_id": {"$exists": False}}  # Matches nothing


def get_user_write_permission(user: Dict[str, Any], entity: Dict[str, Any]) -> bool:
    """
    Check if user can modify/delete an entity.
    
    Business Rules:
    - BR004: Admin can modify/delete ALL entities
    - BR005: Commercial can ONLY modify/delete entities assigned to them
    
    Args:
        user: Current user dict
        entity: The entity document to check (must have assigned_to or user_id field)
    
    Returns:
        bool: True if user can write, False otherwise
    
    Examples:
        lead = {"_id": "...", "assigned_to": "john@example.com"}
        
        # Admin user
        get_user_write_permission(admin_user, lead)  # True
        
        # Commercial user assigned to this lead
        get_user_write_permission(commercial_user, lead)  # True
        
        # Commercial user NOT assigned to this lead
        get_user_write_permission(other_commercial, lead)  # False
    """
    
    # Admin can modify everything
    if user["role"] == "admin":
        return True
    
    # Commercial can only modify their assigned entities
    if user["role"] == "commercial":
        # Check assigned_to field
        if entity.get("assigned_to") == user["email"]:
            return True
        
        # Check user_id field (for activities)
        if entity.get("user_id") == user["id"]:
            return True
        
        # Not assigned to this user
        return False
    
    # Unknown role: deny
    return False


# ==========================================
# AUDIT LOGGING
# ==========================================

async def log_audit_event(
    user: Dict[str, Any],
    action: str,
    entity_type: str,
    entity_id: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log audit event to audit_logs collection.
    
    Args:
        user: Current user dict
        action: Action performed (create_lead, update_contact, delete_opportunity, etc.)
        entity_type: Type of entity (lead, contact, opportunity, user, etc.)
        entity_id: ID of the entity
        details: Optional additional details (changes, metadata)
    
    Example:
        await log_audit_event(
            user=current_user,
            action="update_lead",
            entity_type="lead",
            entity_id="60a7f8...",
            details={"status": "new -> qualified"}
        )
    """
    try:
        current_db = get_db()
        if current_db is None:
            logging.warning("Cannot log audit event: database not configured")
            return
        
        audit_doc = {
            "user_id": user["id"],
            "user_email": user["email"],
            "user_role": user["role"],
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc),
            "ip_address": None  # Can be added from request.client.host if needed
        }
        
        await current_db.audit_logs.insert_one(audit_doc)
        logging.info(f"Audit: {user['email']} {action} {entity_type} {entity_id}")
    
    except Exception as e:
        logging.error(f"Failed to log audit event: {str(e)}")
        # Don't raise exception - audit logging failure shouldn't block requests


# ==========================================
# DECORATOR FOR ROLE-BASED ROUTES (Optional)
# ==========================================

def require_roles(*roles: str):
    """
    Decorator for role-based route protection.
    
    Usage (NOT RECOMMENDED - prefer Depends):
        @router.get("/admin-only")
        @require_roles("admin")
        async def admin_route(user: Dict = Depends(get_current_user)):
            ...
    
    Note: In FastAPI, it's better to use Depends(require_admin) directly.
    This decorator is provided for compatibility but Depends pattern is preferred.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (assumes user is passed as dependency)
            user = kwargs.get("user")
            if not user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            await require_role(list(roles), user)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# ==========================================
# EXPORTS
# ==========================================

__all__ = [
    "get_current_user",
    "require_role",
    "require_admin",
    "get_user_or_admin",
    "get_user_assigned_filter",
    "get_user_write_permission",
    "log_audit_event",
    "security"
]
