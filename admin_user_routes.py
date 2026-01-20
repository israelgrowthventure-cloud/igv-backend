"""
Admin User Routes - User Management
Secured routes for CRUD operations on users
Uses centralized auth_middleware for authentication and RBAC
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
import os
import logging
import bcrypt

# Import centralized auth middleware
from auth_middleware import (
    get_current_user,
    require_admin,
    log_audit_event,
    get_db
)

router = APIRouter(prefix="/api/admin")


# ==========================================
# PYDANTIC MODELS
# ==========================================

class UserCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    password: str
    role: str = "commercial"  # commercial, admin
    assigned_leads: List[str] = []


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    assigned_leads: Optional[List[str]] = None


# ==========================================
# USER CRUD ROUTES
# ==========================================

@router.get("/users")
async def get_all_users(user: Dict = Depends(require_admin)):
    """Get all users (Admin only - uses require_admin dependency)"""
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Get ONLY ACTIVE users from crm_users collection
        # Deleted users have is_active=False and should not appear in the list
        users = await current_db.crm_users.find({"is_active": {"$ne": False}}).sort("created_at", -1).to_list(None)
        
        result = []
        for u in users:
            # Never return password hash
            # Return both "_id" and "id" for frontend/backend compatibility
            user_id = u.get("id", str(u["_id"]))  # UUID id if exists, fallback to MongoDB _id
            user_data = {
                "_id": user_id,  # For frontend (uses user._id)
                "id": user_id,   # For API consistency
                "email": u["email"],
                "first_name": u.get("first_name", ""),
                "last_name": u.get("last_name", ""),
                "role": u.get("role", "commercial"),
                "is_active": u.get("is_active", True),
                "assigned_leads": u.get("assigned_leads", []),
                "created_at": u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else None,
                "last_login": u.get("last_login").isoformat() if isinstance(u.get("last_login"), datetime) else None
            }
            result.append(user_data)
        
        return {"users": result, "total": len(result)}
    
    except Exception as e:
        logging.error(f"Error fetching users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, user: Dict = Depends(require_admin)):
    """Create new user (Admin only - uses require_admin dependency)"""
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Check if user already exists
        existing = await current_db.crm_users.find_one({"email": user_data.email})
        if existing:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Hash password with bcrypt
        password_hash = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Create user document with UUID id (consistent with other users)
        import uuid
        user_doc = {
            "id": str(uuid.uuid4()),  # Generate UUID for user id
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "password_hash": password_hash,
            "role": user_data.role,
            "is_active": True,
            "is_verified": True,
            "assigned_leads": user_data.assigned_leads,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "created_by": user["email"]
        }
        
        result = await current_db.crm_users.insert_one(user_doc)
        user_id = user_doc["id"]  # Use UUID id instead of MongoDB _id
        
        logging.info(f"User created: {user_data.email} by {user['email']}")
        
        # Audit log using centralized function
        await log_audit_event(
            user=user,
            action="create_user",
            entity_type="user",
            entity_id=user_id,
            details={"email": user_data.email, "role": user_data.role}
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "user": {
                "id": user_id,
                "_id": user_id,
                "email": user_data.email,
                "first_name": user_data.first_name,
                "last_name": user_data.last_name,
                "role": user_data.role
            },
            "message": "User created successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/users/{user_id}")
async def update_user(user_id: str, update_data: UserUpdate, user: Dict = Depends(require_admin)):
    """Update user (Admin only - uses require_admin dependency)"""
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Users now use UUID "id" field instead of MongoDB "_id"
        # Check if user exists by UUID id (try both id field and _id for backward compatibility)
        existing_user = await current_db.crm_users.find_one({"id": user_id})
        if not existing_user:
            # Fallback to MongoDB _id for old users
            try:
                obj_id = ObjectId(user_id)
                existing_user = await current_db.crm_users.find_one({"_id": obj_id})
            except:
                pass
        
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Build update dictionary (only non-None values)
        update_dict = {}
        if update_data.first_name is not None:
            update_dict["first_name"] = update_data.first_name
        if update_data.last_name is not None:
            update_dict["last_name"] = update_data.last_name
        if update_data.role is not None:
            update_dict["role"] = update_data.role
        if update_data.is_active is not None:
            update_dict["is_active"] = update_data.is_active
        if update_data.assigned_leads is not None:
            update_dict["assigned_leads"] = update_data.assigned_leads
        
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        # Update user (use the same query that found the user)
        query = {"id": existing_user.get("id")} if "id" in existing_user else {"_id": existing_user["_id"]}
        await current_db.crm_users.update_one(
            query,
            {"$set": update_dict}
        )
        
        logging.info(f"User updated: {user_id} by {user['email']}")
        
        # Audit log using centralized function
        await log_audit_event(
            user=user,
            action="update_user",
            entity_type="user",
            entity_id=user_id,
            details=update_dict
        )
        
        return {
            "success": True,
            "message": "User updated successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user: Dict = Depends(require_admin)):
    """Soft delete user (Admin only - uses require_admin dependency)"""
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        logging.info(f"DELETE user attempt: user_id={user_id}")
        
        # Search user - try UUID id field first, then MongoDB _id
        existing_user = None
        
        # Try 1: Search by "id" field (new users with UUID)
        existing_user = await current_db.crm_users.find_one({"id": user_id})
        
        if not existing_user:
            # Try 2: Search by MongoDB _id (old users or if id is actually an ObjectId)
            try:
                obj_id = ObjectId(user_id)
                existing_user = await current_db.crm_users.find_one({"_id": obj_id})
            except:
                pass  # Not a valid ObjectId, skip
        
        if not existing_user:
            # Try 3: Search by email (fallback - in case GET returns something else)
            # This shouldn't be needed but we're being defensive
            logging.error(f"User not found with id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent self-deletion
        if user_id == user["id"] or (existing_user.get("id") == user["id"]):
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        # Soft delete (set is_active to False)
        query = {"id": existing_user.get("id")} if "id" in existing_user else {"_id": existing_user["_id"]}
        await current_db.crm_users.update_one(
            query,
            {"$set": {
                "is_active": False,
                "deleted_at": datetime.now(timezone.utc),
                "deleted_by": user["email"]
            }}
        )
        
        logging.info(f"User soft-deleted: {user_id} by {user['email']}")
        
        # Audit log using centralized function
        await log_audit_event(
            user=user,
            action="delete_user",
            entity_type="user",
            entity_id=user_id,
            details={"email": existing_user["email"]}
        )
        
        return {
            "success": True,
            "message": "User deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}")
async def get_user(user_id: str, user: Dict = Depends(require_admin)):
    """Get specific user details (Admin only - uses require_admin dependency)"""
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        # Validate ObjectId
        try:
            obj_id = ObjectId(user_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        
        # Get user
        target_user = await current_db.crm_users.find_one({"_id": obj_id})
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Remove sensitive data
        result = {
            "_id": str(target_user["_id"]),
            "email": target_user["email"],
            "name": target_user.get("name", ""),
            "role": target_user.get("role", "commercial"),
            "is_active": target_user.get("is_active", True),
            "assigned_leads": target_user.get("assigned_leads", []),
            "created_at": target_user.get("created_at").isoformat() if isinstance(target_user.get("created_at"), datetime) else None,
            "last_login": target_user.get("last_login").isoformat() if isinstance(target_user.get("last_login"), datetime) else None
        }
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/change-password")
async def change_password(
    data: Dict,
    user: Dict = Depends(get_current_user)
):
    """Change current user's password"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Both passwords required")
    
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    try:
        # Get user from DB
        obj_id = ObjectId(user["_id"]) if isinstance(user["_id"], str) else user["_id"]
        db_user = await current_db.crm_users.find_one({"_id": obj_id})
        
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), db_user["password"].encode('utf-8')):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Hash new password
        new_hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Update password
        await current_db.crm_users.update_one(
            {"_id": obj_id},
            {"$set": {"password": new_hashed, "updated_at": datetime.utcnow()}}
        )
        
        return {"message": "Password changed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error changing password: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
