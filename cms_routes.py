# CMS, Media Library, and Password Recovery Routes
# Phase 5: Advanced CMS Features

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import logging
import uuid
import hashlib
import jwt
from motor.motor_asyncio import AsyncIOMotorClient

# Import auth middleware
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth_middleware import get_current_user, get_db

# Create router
router = APIRouter(prefix="/api", tags=["CMS, Media & Auth"])

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'
PASSWORD_RESET_EXPIRATION_HOURS = 1

# CMS Password (separate from CRM login)
CMS_PASSWORD = os.getenv('CMS_PASSWORD')

# ==========================================
# CMS ACCESS PROTECTION
# ==========================================

class CmsPasswordVerify(BaseModel):
    password: str

@router.post("/cms/verify-password")
async def verify_cms_password(
    data: CmsPasswordVerify,
    user: Dict = Depends(get_current_user)
):
    """
    Verify the separate CMS password for accessing the editor.
    Only admin/technique roles can access this endpoint.
    
    The CMS_PASSWORD environment variable must be set on Render.
    """
    # Check user role
    if user.get('role') not in ['admin', 'technique', 'tech', 'developer']:
        raise HTTPException(
            status_code=403, 
            detail="Access denied - admin/technique role required"
        )
    
    # Check if CMS password is configured
    if not CMS_PASSWORD:
        logging.error("CMS_PASSWORD not configured in environment")
        raise HTTPException(
            status_code=503, 
            detail="CMS not configured"
        )
    
    # Verify password
    if data.password == CMS_PASSWORD:
        logging.info(f"CMS access granted to {user.get('email')}")
        return {"success": True, "message": "Access granted"}
    else:
        logging.warning(f"CMS access denied for {user.get('email')} - wrong password")
        raise HTTPException(
            status_code=401, 
            detail="Invalid password"
        )

# ==========================================
# CMS CONTENT ENDPOINTS
# ==========================================

class PageContentUpdate(BaseModel):
    page: str
    language: str
    section: str
    content: Dict[str, Any]
    version: Optional[int] = None

@router.get("/pages/{page}")
async def get_page_content(page: str, language: str = 'fr', user: Dict = Depends(get_current_user)):
    """
    Get content for a specific page and language.
    Returns the full page content object.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    content = await db.page_content.find_one(
        {"page": page, "language": language},
        {"_id": 0}
    )
    
    if not content:
        return {
            "page": page,
            "language": language,
            "content": {},
            "version": 0,
            "last_updated": None
        }
    
    return content

@router.post("/pages/update")
async def update_page_content(
    data: PageContentUpdate,
    user: Dict = Depends(get_current_user)
):
    """
    Update content for a specific page section.
    This endpoint is used by the WYSIWYG editor to save modifications.
    
    Request body:
    {
        "page": "home",
        "language": "fr",
        "section": "hero",
        "content": { "title": "...", "description": "..." },
        "version": 1  # Optional, for optimistic locking
    }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Check user permissions
    if user['role'] not in ['admin', 'editor']:
        raise HTTPException(status_code=403, detail="Insufficient permissions to edit content")
    
    # Get existing document for version check
    existing = await db.page_content.find_one(
        {"page": data.page, "language": data.language}
    )
    
    # Optimistic locking
    if existing and data.version is not None:
        if existing.get('version', 0) != data.version:
            raise HTTPException(
                status_code=409,
                detail="Content has been modified by another user. Please refresh and try again."
            )
    
    # Build update document
    now = datetime.now(timezone.utc)
    update_doc = {
        "page": data.page,
        "language": data.language,
        f"content.{data.section}": data.content,
        "updated_by": user['email'],
        "updated_at": now.isoformat(),
        "version": (existing.get('version', 0) + 1) if existing else 1
    }
    
    # Upsert the document
    await db.page_content.update_one(
        {"page": data.page, "language": data.language},
        {
            "$set": update_doc,
            "$setOnInsert": {
                "created_at": now.isoformat(),
                "created_by": user['email']
            }
        },
        upsert=True
    )
    
    logging.info(f"CMS: {user['email']} updated {data.page}/{data.language}/{data.section}")
    
    return {
        "success": True,
        "message": "Content saved successfully",
        "page": data.page,
        "section": data.section,
        "version": update_doc["version"],
        "updated_at": now.isoformat()
    }

@router.get("/pages/list")
async def list_pages(user: Dict = Depends(get_current_user)):
    """
    List all pages that have content in the CMS.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Get distinct pages
    pages = await db.page_content.distinct("page")
    
    # For each page, get the latest version for each language
    page_info = []
    for page in pages:
        languages = await db.page_content.distinct("language", {"page": page})
        page_info.append({
            "page": page,
            "languages": languages,
            "url": f"/{page}" if page != 'home' else "/"
        })
    
    return {"pages": page_info}

# ==========================================
# MEDIA LIBRARY ENDPOINTS
# ==========================================

MEDIA_UPLOAD_DIR = os.getenv('MEDIA_UPLOAD_DIR', '/tmp/igv-uploads')
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml']

@router.post("/admin/media/upload")
async def upload_media(
    file: UploadFile = File(...),
    user: Dict = Depends(get_current_user)
):
    """
    Upload an image to the media library.
    Returns the public URL of the uploaded file.
    
    Headers:
    - Authorization: Bearer <token>
    
    Body (multipart/form-data):
    - file: The image file to upload
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Check permissions
    if user['role'] not in ['admin', 'editor']:
        raise HTTPException(status_code=403, detail="Insufficient permissions to upload media")
    
    # Validate file type
    content_type = file.content_type
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_TYPES)}"
        )
    
    # Create upload directory if it doesn't exist
    os.makedirs(MEDIA_UPLOAD_DIR, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1] if file.filename else '.jpg'
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(MEDIA_UPLOAD_DIR, unique_filename)
    
    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")
    
    # Write file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # Generate public URL
    media_base_url = os.getenv('MEDIA_BASE_URL', f'/media/uploads')
    public_url = f"{media_base_url}/{unique_filename}"
    
    # Save to MongoDB
    media_doc = {
        "filename": unique_filename,
        "original_name": file.filename,
        "content_type": content_type,
        "size": len(content),
        "url": public_url,
        "uploaded_by": user['email'],
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "tags": [],
        "metadata": {}
    }
    
    await db.media_library.insert_one(media_doc)
    
    logging.info(f"Media: {user['email']} uploaded {unique_filename}")
    
    return {
        "success": True,
        "url": public_url,
        "filename": unique_filename,
        "original_name": file.filename,
        "size": len(content),
        "content_type": content_type
    }

@router.get("/admin/media")
async def list_media(
    page: int = 1,
    limit: int = 20,
    user: Dict = Depends(get_current_user)
):
    """
    List all media files in the library.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] not in ['admin', 'editor', 'viewer']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    skip = (page - 1) * limit
    
    # Get total count
    total = await db.media_library.count_documents({})
    
    # Get paginated results
    media = await db.media_library.find(
        {},
        {"_id": 0}
    ).sort("uploaded_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "media": media,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }

@router.delete("/admin/media/{filename}")
async def delete_media(
    filename: str,
    user: Dict = Depends(get_current_user)
):
    """
    Delete a media file from the library.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can delete media")
    
    # Find the file record
    media_doc = await db.media_library.find_one({"filename": filename})
    if not media_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from filesystem
    file_path = os.path.join(MEDIA_UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Delete from database
    await db.media_library.delete_one({"filename": filename})
    
    logging.info(f"Media: {user['email']} deleted {filename}")
    
    return {"success": True, "message": "File deleted successfully"}

# ==========================================
# PASSWORD RECOVERY ENDPOINTS
# ==========================================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ResetPasswordResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: EmailStr
    reset_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

@router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request a password reset link.
    Sends an email with a reset token to the user's email address.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Find user by email
    user = await db.users.find_one({"email": request.email})
    if not user:
        # Return success even if email not found (security best practice)
        return {
            "success": True,
            "message": "If an account exists, a password reset link has been sent."
        }
    
    # Generate reset token
    reset_token = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_EXPIRATION_HOURS)
    
    # Store reset token
    await db.password_resets.update_one(
        {"email": request.email},
        {
            "$set": {
                "token": reset_token,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "used": False
            }
        },
        upsert=True
    )
    
    # Build reset URL
    frontend_url = os.getenv('FRONTEND_URL', 'https://israelgrowthventure.com')
    reset_url = f"{frontend_url}/reset-password?token={reset_token}&email={request.email}"
    
    # TODO: Send email with reset URL
    # For now, log the reset URL (in production, send actual email)
    logging.info(f"Password reset URL for {request.email}: {reset_url}")
    
    # In production, uncomment:
    # await send_password_reset_email(request.email, reset_url)
    
    return {
        "success": True,
        "message": "If an account exists, a password reset link has been sent.",
        # Remove in production
        "debug_reset_url": reset_url if os.getenv('DEBUG') else None
    }

@router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using a valid reset token.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Find valid reset token
    reset_record = await db.password_resets.find_one({
        "email": request.email,
        "token": request.token,
        "used": False
    })
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check expiration
    expires_at = reset_record.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Hash new password
    new_password_hash = hashlib.sha256(request.new_password.encode()).hexdigest()
    
    # Update user password
    await db.users.update_one(
        {"email": request.email},
        {"$set": {"password_hash": new_password_hash}}
    )
    
    # Mark reset token as used
    await db.password_resets.update_one(
        {"email": request.email, "token": request.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    logging.info(f"Auth: Password reset completed for {request.email}")
    
    return {
        "success": True,
        "message": "Password has been reset successfully. You can now login with your new password."
    }

@router.get("/auth/verify-reset-token")
async def verify_reset_token(email: str, token: str):
    """
    Verify if a reset token is valid.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    reset_record = await db.password_resets.find_one({
        "email": email,
        "token": token,
        "used": False
    })
    
    if not reset_record:
        return {"valid": False, "message": "Invalid or expired token"}
    
    expires_at = reset_record.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    
    if expires_at < datetime.now(timezone.utc):
        return {"valid": False, "message": "Token has expired"}
    
    return {"valid": True, "expires_at": expires_at.isoformat()}

# ==========================================
# CMS SYNC ENDPOINTS
# ==========================================

@router.post("/cms/sync-i18n")
async def sync_i18n_content(
    language: str = 'fr',
    user: Dict = Depends(get_current_user)
):
    """
    Sync CMS content to i18n JSON files.
    Exports all CMS content for a language to a downloadable JSON format.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can sync i18n content")
    
    # Get all content for the language
    content_docs = await db.page_content.find(
        {"language": language},
        {"_id": 0, "page": 1, "content": 1}
    ).to_list(1000)
    
    # Build i18n structure
    i18n_data = {}
    for doc in content_docs:
        page = doc.get("page", "unknown")
        content = doc.get("content", {})
        
        # Merge all sections for this page
        if page not in i18n_data:
            i18n_data[page] = {}
        i18n_data[page].update(content)
    
    return {
        "language": language,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "content": i18n_data
    }

# ==========================================
# VERSION HISTORY
# ==========================================

@router.get("/pages/{page}/history")
async def get_page_history(
    page: str,
    language: str = 'fr',
    limit: int = 10,
    user: Dict = Depends(get_current_user)
):
    """
    Get version history for a page.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Get from audit logs or version history collection
    history = await db.cms_history.find(
        {"page": page, "language": language}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Convert ObjectId to string
    for doc in history:
        doc['_id'] = str(doc['_id'])
        if isinstance(doc.get('timestamp'), datetime):
            doc['timestamp'] = doc['timestamp'].isoformat()
    
    return {"history": history}

# ==========================================
# EXPORTS
# ==========================================

__all__ = ["router"]
