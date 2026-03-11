"""
Client Portal Routes - Zone Client API
Created: 28 Janvier 2026
Login, register, analyses, invoices pour clients
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os
import logging
import jwt
import bcrypt
import uuid

# Import centralized auth middleware
from auth_middleware import get_db

router = APIRouter(prefix="/api/client", tags=["client"])

# JWT Configuration
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'
CLIENT_TOKEN_EXPIRATION_HOURS = 72  # Clients have longer sessions


# ==========================================
# PYDANTIC MODELS
# ==========================================

class ClientRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str
    last_name: str
    company: Optional[str] = None
    phone: Optional[str] = None


class ClientLogin(BaseModel):
    email: EmailStr
    password: str


class ClientProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def create_client_token(email: str, client_id: str) -> str:
    """Create JWT token for client"""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    
    payload = {
        'email': email,
        'client_id': client_id,
        'type': 'client',
        'exp': datetime.now(timezone.utc) + timedelta(hours=CLIENT_TOKEN_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_client_token(token: str) -> Dict[str, Any]:
    """Verify and decode client JWT token"""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'client':
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_client(authorization: str = None) -> Dict[str, Any]:
    """Dependency to get current authenticated client"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    try:
        token = authorization.replace("Bearer ", "")
        return verify_client_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON response"""
    if doc.get("_id"):
        doc["id"] = str(doc.pop("_id"))
    for key in ["created_at", "updated_at", "completed_at", "paid_at"]:
        if doc.get(key) and isinstance(doc[key], datetime):
            doc[key] = doc[key].isoformat()
    # Remove sensitive fields
    doc.pop("password_hash", None)
    doc.pop("password", None)
    return doc


# ==========================================
# HEALTH CHECK
# ==========================================

@router.get("/health")
async def client_health():
    """Health check for client portal API"""
    return {"status": "ok", "service": "client-portal", "version": "1.0.0"}


# ==========================================
# AUTHENTICATION ENDPOINTS
# ==========================================

@router.post("/register")
async def client_register(data: ClientRegister):
    """Register a new client account"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Check if email already exists
    existing = await db.clients.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create client document
    client_doc = {
        "id": str(uuid.uuid4()),
        "email": data.email,
        "password_hash": hash_password(data.password),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "company": data.company,
        "phone": data.phone,
        "is_active": True,
        "is_verified": False,  # Email verification pending
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.clients.insert_one(client_doc)
    
    # Generate token
    token = create_client_token(data.email, client_doc["id"])
    
    return {
        "message": "Registration successful",
        "access_token": token,
        "token_type": "bearer",
        "client": {
            "id": client_doc["id"],
            "email": client_doc["email"],
            "first_name": client_doc["first_name"],
            "last_name": client_doc["last_name"]
        }
    }


@router.post("/login")
async def client_login(credentials: ClientLogin):
    """Client login - returns JWT token"""
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    client = await db.clients.find_one({"email": credentials.email})
    
    if not client:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not client.get("is_active", True):
        raise HTTPException(status_code=401, detail="Account is inactive")
    
    password_hash = client.get("password_hash") or client.get("password")
    if not password_hash or not verify_password(credentials.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Update last login
    await db.clients.update_one(
        {"email": credentials.email},
        {"$set": {"last_login": datetime.now(timezone.utc)}}
    )
    
    token = create_client_token(credentials.email, client.get("id", str(client["_id"])))
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "client": {
            "id": client.get("id", str(client["_id"])),
            "email": client["email"],
            "first_name": client.get("first_name", ""),
            "last_name": client.get("last_name", "")
        }
    }


@router.get("/profile")
async def get_client_profile(authorization: str = None):
    """Get current client's profile"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    client = await db.clients.find_one({"email": client_data["email"]})
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return serialize_doc(client)


@router.put("/profile")
async def update_client_profile(update: ClientProfileUpdate, authorization: str = None):
    """Update client profile"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    update_doc = {k: v for k, v in update.model_dump().items() if v is not None}
    update_doc["updated_at"] = datetime.now(timezone.utc)
    
    await db.clients.update_one(
        {"email": client_data["email"]},
        {"$set": update_doc}
    )
    
    client = await db.clients.find_one({"email": client_data["email"]})
    return serialize_doc(client)


# ==========================================
# CLIENT ANALYSES
# ==========================================

@router.get("/analyses")
async def get_client_analyses(authorization: str = None):
    """Get all mini-analyses for the current client"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Find analyses by client email
    analyses = await db.mini_analyses.find({
        "email": client_data["email"]
    }).sort("created_at", -1).to_list(100)
    
    return {
        "analyses": [serialize_doc(a) for a in analyses],
        "total": len(analyses)
    }


@router.get("/analyses/{analysis_id}")
async def get_client_analysis(analysis_id: str, authorization: str = None):
    """Get a specific analysis for the current client"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        analysis = await db.mini_analyses.find_one({
            "_id": ObjectId(analysis_id),
            "email": client_data["email"]
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return serialize_doc(analysis)


# ==========================================
# CLIENT INVOICES
# ==========================================

@router.get("/invoices")
async def get_client_invoices(authorization: str = None):
    """Get all invoices for the current client"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    invoices = await db.invoices.find({
        "client_email": client_data["email"]
    }).sort("created_at", -1).to_list(100)
    
    return {
        "invoices": [serialize_doc(i) for i in invoices],
        "total": len(invoices)
    }


@router.get("/invoices/{invoice_id}")
async def get_client_invoice(invoice_id: str, authorization: str = None):
    """Get a specific invoice for the current client"""
    client_data = await get_current_client(authorization)
    
    db = await get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        invoice = await db.invoices.find_one({
            "_id": ObjectId(invoice_id),
            "client_email": client_data["email"]
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return serialize_doc(invoice)
