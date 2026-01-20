# IGV Backend - FastAPI Server - Build 20260102-0845 - HOTFIX 3
from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import jwt
import hashlib
import hmac
import traceback

# Conditional email imports (don't crash if not available)
try:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_LIBS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Email libraries not available in server.py: {str(e)}")
    EMAIL_LIBS_AVAILABLE = False

# Import AI routes
from ai_routes import router as ai_router
from mini_analysis_routes import router as mini_analysis_router
from extended_routes import router as extended_router
# from crm_routes import router as crm_router  # DISABLED - duplicate with crm_complete_routes
from tracking_routes import router as tracking_router
from admin_routes import router as admin_router
from crm_complete_routes import router as crm_complete_router
from gdpr_routes import router as gdpr_router
from quota_queue_routes import router as quota_router
from admin_user_routes import router as admin_user_router
from cms_routes import router as cms_router  # Phase 5: CMS, Media & Auth

# New routers with error handling
INVOICE_ROUTER_ERROR = None
MONETICO_ROUTER_ERROR = None

try:
    from invoice_routes import router as invoice_router
    INVOICE_ROUTER_LOADED = True
    logging.info("✓ Invoice router loaded successfully")
except Exception as e:
    INVOICE_ROUTER_ERROR = f"{type(e).__name__}: {str(e)}"
    logging.error(f"✗ Failed to load invoice_routes: {INVOICE_ROUTER_ERROR}")
    INVOICE_ROUTER_LOADED = False
    invoice_router = None

try:
    from monetico_routes import router as monetico_router
    MONETICO_ROUTER_LOADED = True
    logging.info("✓ Monetico router loaded successfully")
except Exception as e:
    MONETICO_ROUTER_ERROR = f"{type(e).__name__}: {str(e)}"
    logging.error(f"✗ Failed to load monetico_routes: {MONETICO_ROUTER_ERROR}")
    MONETICO_ROUTER_LOADED = False
    monetico_router = None


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# JWT & Admin configuration (from environment only)
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
BOOTSTRAP_TOKEN = os.getenv('BOOTSTRAP_TOKEN')

# MongoDB connection with environment variable aliases (Render compatibility)
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

# Initialize MongoDB client (optional - will be None if not configured)
client = None
db = None
mongodb_status = "not_configured"

if mongo_url:
    try:
        # Configure MongoDB with timeout and connection pooling
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=10,
            minPoolSize=1
        )
        db = client[db_name]
        mongodb_status = "configured"
        logging.info(f"MongoDB configured for database: {db_name}")
    except Exception as e:
        logging.error(f"MongoDB connection error: {str(e)}")
        mongodb_status = "error"
else:
    logging.warning("MongoDB not configured (MONGODB_URI or MONGO_URL not set)")

# Create the main app without a prefix
app = FastAPI()

# Debug endpoint to check router status
@app.get("/debug/routers")
async def debug_routers():
    """Debug endpoint to check if routers are loaded"""
    import sys
    return {
        "ai_router_loaded": 'ai_routes' in sys.modules,
        "mini_analysis_router_loaded": 'mini_analysis_routes' in sys.modules,
        "invoice_router_loaded": INVOICE_ROUTER_LOADED,
        "invoice_router_error": INVOICE_ROUTER_ERROR,
        "monetico_router_loaded": MONETICO_ROUTER_LOADED,
        "monetico_router_error": MONETICO_ROUTER_ERROR,
        "gemini_api_key_set": bool(os.getenv('GEMINI_API_KEY')),
        "gemini_api_key_length": len(os.getenv('GEMINI_API_KEY', '')),
        "mongodb_uri_set": bool(mongo_url),
        "db_name": db_name,
        "mongodb_status": mongodb_status,
        "build_timestamp": "2025-12-29T17:20:00Z"
    }

# Ultra-light health check at root (no MongoDB dependency)
@app.get("/health")
async def root_health():
    """Ultra-fast health check - no database check"""
    return {"status": "ok", "service": "igv-backend", "version": "1.0.0"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "IGV Backend API", "status": "running"}

# CORS configuration - MUST be configured BEFORE routers
# Production domains explicitly allowed
cors_origins_env = os.getenv('CORS_ALLOWED_ORIGINS') or os.getenv('CORS_ORIGINS', '')

# Default production origins
DEFAULT_ORIGINS = [
    "https://israelgrowthventure.com",
    "https://www.israelgrowthventure.com",
    "http://localhost:3000",  # Local development
    "http://127.0.0.1:3000"   # Local development
]

# Merge environment origins with defaults (global variable for exception handlers)
if cors_origins_env and cors_origins_env != '*':
    ALLOWED_ORIGINS = list(set(DEFAULT_ORIGINS + cors_origins_env.split(',')))
else:
    ALLOWED_ORIGINS = DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global exception handler to ensure CORS headers on ALL responses (including errors)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Ensure CORS headers are present even on error responses"""
    origin = request.headers.get("origin", "")
    headers = {}
    
    # Add CORS headers if origin is allowed
    if origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler with CORS headers and detailed logging"""
    error_id = f"err_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    error_trace = traceback.format_exc()
    
    logging.error(f"[{error_id}] Unhandled exception: {str(exc)}")
    logging.error(f"[{error_id}] Type: {type(exc).__name__}")
    logging.error(f"[{error_id}] Traceback:\n{error_trace}")
    
    origin = request.headers.get("origin", "")
    headers = {}
    
    if origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "error_id": error_id,
            "error_type": type(exc).__name__
        },
        headers=headers
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers"""
    origin = request.headers.get("origin", "")
    headers = {}
    
    if origin in ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
        headers=headers
    )

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Debug endpoint to see all headers
@api_router.get("/debug/headers")
async def debug_headers(request: Request):
    """Debug endpoint to see all request headers and IP detection"""
    return {
        "headers": dict(request.headers),
        "client_host": request.client.host if request.client else None,
        "client_port": request.client.port if request.client else None,
        "x_forwarded_for": request.headers.get('X-Forwarded-For'),
        "x_real_ip": request.headers.get('X-Real-IP'),
        "cf_connecting_ip": request.headers.get('CF-Connecting-IP'),
        "true_client_ip": request.headers.get('True-Client-IP'),
    }


# Health check endpoint (REQUIRED for Render)
@api_router.get("/health")
async def health_check():
    """Health check endpoint with MongoDB status"""
    health_status = {
        "status": "ok",
        "mongodb": mongodb_status
    }
    
    if mongodb_status == "configured" and db is not None:
        try:
            # Test MongoDB connection with timeout
            import asyncio
            await asyncio.wait_for(db.command('ping'), timeout=3.0)
            health_status["mongodb"] = "connected"
            health_status["db"] = db_name
        except asyncio.TimeoutError:
            logging.error("MongoDB ping timeout")
            health_status["mongodb"] = "timeout"
        except Exception as e:
            logging.error(f"MongoDB ping failed: {str(e)}")
            health_status["mongodb"] = "error"
    
    return health_status


# Define Models
class ContactForm(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    message: str
    language: str = "fr"

class ContactResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    language: str = "fr"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CartItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pack_name: str
    pack_type: str  # "analyse", "succursales", "franchise"
    price: float
    currency: str
    region: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CartItemCreate(BaseModel):
    pack_name: str
    pack_type: str
    price: float
    currency: str
    region: str

class IPLocationResponse(BaseModel):
    region: str
    country: str
    currency: str

class CMSContent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    page: str  # 'home', 'about', 'packs', etc.
    language: str  # 'fr', 'en', 'he'
    content: Dict[str, Any]  # GrapesJS JSON content
    updated_by: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CMSContentCreate(BaseModel):
    page: str
    language: str
    content: Dict[str, Any]

class AdminUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    password_hash: str
    role: str = 'admin'  # 'admin', 'sales', 'viewer'
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class AdminUserCreate(BaseModel):
    email: EmailStr
    first_name: str = ""
    last_name: str = ""
    password: str
    role: str = 'viewer'  # Default to lowest privilege

class MoneticopaymentRequest(BaseModel):
    pack_type: str  # 'analyse'
    amount: float
    currency: str
    customer_email: EmailStr
    customer_name: str
    language: str = 'fr'

# Security
security = HTTPBearer()

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return hash_password(plain_password) == hashed_password

def create_jwt_token(email: str, role: str) -> str:
    """Create JWT token"""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    
    payload = {
        'email': email,
        'role': role,
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """Verify and decode JWT token"""
    if not JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    return verify_jwt_token(token)


# Helper function to send email via OVH SMTP (contact@israelgrowthventure.com)
async def send_email_gmail(to_email: str, subject: str, body: str, html_body: str = None):
    # OVH SMTP Configuration
    smtp_host = os.getenv('SMTP_HOST', 'ssl0.ovh.net')
    smtp_port = int(os.getenv('SMTP_PORT', '465'))
    smtp_user = os.getenv('SMTP_USER', 'contact@israelgrowthventure.com')
    smtp_password = os.getenv('SMTP_PASSWORD')
    smtp_from = os.getenv('SMTP_FROM', 'contact@israelgrowthventure.com')
    
    if not smtp_user or not smtp_password:
        raise HTTPException(status_code=500, detail="SMTP credentials not configured")
    
    message = MIMEMultipart('alternative')
    message['Subject'] = subject
    message['From'] = f"Israel Growth Venture <{smtp_from}>"
    message['Reply-To'] = smtp_from
    message['To'] = to_email
    
    part1 = MIMEText(body, 'plain')
    message.attach(part1)
    
    if html_body:
        part2 = MIMEText(html_body, 'html')
        message.attach(part2)
    
    try:
        # OVH requires SSL/TLS (port 465) instead of STARTTLS (port 587)
        await aiosmtplib.send(
            message,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            use_tls=True  # SSL/TLS direct for OVH
        )
        return True
    except Exception as e:
        logging.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


# API Routes
@api_router.get("/")
async def root():
    return {"message": "Israel Growth Venture API"}


@api_router.post("/contact", response_model=ContactResponse)
async def create_contact(contact: ContactForm):
    """Handle contact form submission"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    contact_dict = contact.model_dump()
    contact_obj = ContactResponse(**contact_dict)
    
    # Save to MongoDB
    doc = contact_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.contacts.insert_one(doc)
    
    # Send email notification
    email_subject = f"Nouveau contact IGV - {contact.name}"
    email_body = f"""
    Nouveau message de contact:
    
    Nom: {contact.name}
    Email: {contact.email}
    Société: {contact.company or 'Non spécifié'}
    Téléphone: {contact.phone or 'Non spécifié'}
    Langue: {contact.language}
    
    Message:
    {contact.message}
    """
    
    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <h2 style="color: #1e40af;">Nouveau message de contact</h2>
        <table style="border-collapse: collapse; width: 100%;">
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Nom:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{contact.name}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Email:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{contact.email}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Société:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{contact.company or 'Non spécifié'}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Téléphone:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{contact.phone or 'Non spécifié'}</td>
          </tr>
          <tr>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;"><strong>Langue:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{contact.language}</td>
          </tr>
        </table>
        <div style="margin-top: 20px; padding: 15px; background-color: #f3f4f6; border-left: 4px solid #1e40af;">
          <h3 style="margin-top: 0;">Message:</h3>
          <p style="white-space: pre-wrap;">{contact.message}</p>
        </div>
      </body>
    </html>
    """
    
    recipient_email = os.getenv('CONTACT_EMAIL', 'israel.growth.venture@gmail.com')
    await send_email_gmail(recipient_email, email_subject, email_body, html_body)
    
    return contact_obj


@api_router.get("/contacts", response_model=List[ContactResponse])
async def get_contacts():
    """Get all contacts (admin)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    contacts = await db.contacts.find({}, {"_id": 0}).to_list(1000)
    for contact in contacts:
        ts = contact.get('timestamp')
        if ts is None:
            contact['timestamp'] = datetime.now(timezone.utc)
            continue
        if isinstance(ts, str):
            try:
                contact['timestamp'] = datetime.fromisoformat(ts)
            except ValueError:
                contact['timestamp'] = datetime.now(timezone.utc)
        elif not isinstance(ts, datetime):
            contact['timestamp'] = datetime.now(timezone.utc)
    return contacts


@api_router.post("/cart", response_model=CartItem)
async def add_to_cart(item: CartItemCreate):
    """Add item to cart"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    cart_obj = CartItem(**item.model_dump())
    doc = cart_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.cart.insert_one(doc)
    return cart_obj


@api_router.get("/cart", response_model=List[CartItem])
async def get_cart():
    """Get cart items"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    items = await db.cart.find({}, {"_id": 0}).to_list(1000)
    for item in items:
        if isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
    return items


@api_router.get("/detect-location")
async def detect_location(request: Request):
    """Detect user location based on IP using ipapi.co with fallback to IP2Location"""
    try:
        # Get client IP from multiple possible headers (Render/CloudFlare/etc.)
        client_ip = None
        
        # Try different headers in order of preference
        if request.headers.get('CF-Connecting-IP'):
            client_ip = request.headers.get('CF-Connecting-IP')
        elif request.headers.get('True-Client-IP'):
            client_ip = request.headers.get('True-Client-IP')
        elif request.headers.get('X-Real-IP'):
            client_ip = request.headers.get('X-Real-IP')
        elif request.headers.get('X-Forwarded-For'):
            # X-Forwarded-For can have multiple IPs, take the LAST one (client's real IP)
            forwarded = request.headers.get('X-Forwarded-For')
            client_ip = forwarded.split(',')[-1].strip()
        elif request.client:
            client_ip = request.client.host
        
        logging.info(f"🌍 Geolocation request for IP: {client_ip}")
        logging.info(f"📋 Headers: X-Forwarded-For={request.headers.get('X-Forwarded-For')}, X-Real-IP={request.headers.get('X-Real-IP')}, CF-Connecting-IP={request.headers.get('CF-Connecting-IP')}")
        
        # Try ipapi.co first
        async with httpx.AsyncClient() as client:
            try:
                if client_ip:
                    response = await client.get(f'https://ipapi.co/{client_ip}/json/', timeout=5.0)
                else:
                    response = await client.get('https://ipapi.co/json/', timeout=5.0)
                data = response.json()
                
                country_code = data.get('country_code', 'FR')
                country_name = data.get('country_name', 'France')
                
                logging.info(f"📍 ipapi.co result: {country_code} - {country_name}")
            except Exception as e:
                logging.warning(f"ipapi.co failed: {e}, trying ip-api.com")
                # Fallback to ip-api.com
                if client_ip:
                    response = await client.get(f'http://ip-api.com/json/{client_ip}', timeout=5.0)
                else:
                    response = await client.get('http://ip-api.com/json/', timeout=5.0)
                data = response.json()
                
                country_code = data.get('countryCode', 'FR')
                country_name = data.get('country', 'France')
                
                logging.info(f"📍 ip-api.com result: {country_code} - {country_name}")
            
            # Determine region based on country
            if country_code in ['FR', 'BE', 'CH', 'LU', 'MC', 'DE', 'IT', 'ES', 'PT', 'NL', 'GB', 'IE']:
                region = 'europe'
                currency = '€'
            elif country_code in ['US', 'CA']:
                region = 'usa'
                currency = '$'
            elif country_code == 'IL':
                region = 'israel'
                currency = '₪'
            else:
                region = 'other'
                currency = '$'
            
            logging.info(f"✅ Final location: {region} - {country_name} ({currency})")
            
            return IPLocationResponse(
                region=region,
                country=country_name,
                currency=currency
            )
    except Exception as e:
        logging.error(f"❌ Error detecting location: {str(e)}")
        # Default to Europe if detection fails
        return IPLocationResponse(
            region='europe',
            country='France',
            currency='€'
        )


# ============================================================
# CMS Endpoints (Protected)
# ============================================================

@api_router.get("/cms/content")
async def get_cms_content(page: str, language: str = 'fr', user: Dict = Depends(get_current_user)):
    """Get CMS content for a specific page and language (protected)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    content = await db.cms_content.find_one(
        {"page": page, "language": language},
        {"_id": 0}
    )
    
    if not content:
        return {"page": page, "language": language, "content": {}}
    
    return content

@api_router.post("/cms/content")
async def save_cms_content(data: CMSContentCreate, user: Dict = Depends(get_current_user)):
    """Save CMS content (protected, admin/editor only)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] not in ['admin', 'editor']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    content_obj = CMSContent(
        page=data.page,
        language=data.language,
        content=data.content,
        updated_by=user['email']
    )
    
    # Upsert: update if exists, insert if not
    await db.cms_content.update_one(
        {"page": data.page, "language": data.language},
        {"$set": content_obj.model_dump()},
        upsert=True
    )
    
    return {"message": "Content saved successfully", "id": content_obj.id}


# ============================================================
# Admin/CRM Endpoints
# ============================================================

@api_router.post("/admin/bootstrap")
async def bootstrap_admin(token: str):
    """Bootstrap admin account (protected by BOOTSTRAP_TOKEN)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if not BOOTSTRAP_TOKEN:
        raise HTTPException(status_code=500, detail="BOOTSTRAP_TOKEN not configured")
    
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="ADMIN_EMAIL or ADMIN_PASSWORD not configured")
    
    if token != BOOTSTRAP_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")
    
    # Check if admin already exists
    existing_admin = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing_admin:
        # Update password hash if it exists (allows password reset)
        await db.users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"password_hash": hash_password(ADMIN_PASSWORD)}}
        )
        return {"message": "Admin password updated", "email": ADMIN_EMAIL}
    
    # Create admin user
    admin_user = AdminUser(
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role='admin'
    )
    
    await db.users.insert_one(admin_user.model_dump())
    
    return {"message": "Admin created successfully", "email": ADMIN_EMAIL}

@api_router.post("/admin/login")
async def admin_login(credentials: AdminLoginRequest):
    """Admin login - returns JWT token"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    user = await db.users.find_one({"email": credentials.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_jwt_token(user['email'], user['role'])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user['role']
    }

@api_router.get("/admin/verify")
async def verify_admin_token(user: Dict = Depends(get_current_user)):
    """Verify admin JWT token and return user info"""
    return {
        "email": user['email'],
        "role": user['role']
    }

@api_router.get("/admin/contacts")
async def get_all_contacts(user: Dict = Depends(get_current_user)):
    """Get all contacts (admin only)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] not in ['admin', 'editor', 'viewer']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    contacts = await db.contacts.find({}, {"_id": 0}).sort("timestamp", -1).to_list(1000)
    return contacts

@api_router.get("/admin/stats")
async def get_stats(user: Dict = Depends(get_current_user)):
    """Get dashboard statistics (admin/sales/viewer)"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    if user['role'] not in ['admin', 'sales', 'viewer']:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        total_contacts = await db.contacts.count_documents({})
        total_carts = await db.cart.count_documents({})
        total_leads = await db.leads.count_documents({})
        total_analyses = await db.mini_analyses.count_documents({})
        
        # Calculate conversion rate (leads that became analyses)
        conversion_rate = round((total_analyses / total_leads * 100) if total_leads > 0 else 0, 1)
        
        return {
            "total_contacts": total_contacts,
            "total_carts": total_carts,
            "total_leads": total_leads,
            "total_analyses": total_analyses,
            "conversion_rate": conversion_rate,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logging.error(f"Error getting stats: {str(e)}")
        return {
            "total_contacts": 0,
            "total_carts": 0,
            "total_leads": 0,
            "total_analyses": 0,
            "conversion_rate": 0,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


# REMOVED: POST /admin/users - now handled by admin_user_routes.py (returns proper user_id + user object)
# REMOVED: GET /admin/users - now handled by admin_user_routes.py (uses crm_users collection)
# Old endpoints used db.users collection, new ones use db.crm_users (correct for CRM)

# ============================================================
# Monetico Payment Endpoints
# ============================================================

def generate_monetico_mac(data: Dict[str, str], key: str) -> str:
    """Generate Monetico MAC signature"""
    # Concatenate values in specific order
    message = '*'.join([
        data.get('TPE', ''),
        data.get('date', ''),
        data.get('montant', ''),
        data.get('reference', ''),
        data.get('texte-libre', ''),
        data.get('version', '3.0'),
        data.get('lgue', 'FR'),
        data.get('societe', ''),
        data.get('mail', '')
    ])
    
    # Create HMAC-SHA1 signature
    mac = hmac.new(key.encode(), message.encode(), hashlib.sha1).hexdigest()
    return mac

@api_router.post("/monetico/init-payment")
async def init_monetico_payment(payment: MoneticopaymentRequest):
    """Initialize Monetico payment (Pack Analyse only)"""
    
    # Get Monetico config from environment
    monetico_tpe = os.getenv('MONETICO_TPE')
    monetico_key = os.getenv('MONETICO_KEY')
    monetico_company = os.getenv('MONETICO_COMPANY_CODE')
    monetico_mode = os.getenv('MONETICO_MODE', 'TEST')
    
    if not all([monetico_tpe, monetico_key, monetico_company]):
        raise HTTPException(status_code=500, detail="Monetico not configured")
    
    # Only Pack Analyse is payable via Monetico
    if payment.pack_type != 'analyse':
        raise HTTPException(status_code=400, detail="Only Pack Analyse is available for online payment")
    
    # Generate unique reference
    reference = f"IGV-{payment.pack_type.upper()}-{uuid.uuid4().hex[:8]}"
    
    # Prepare payment data
    payment_data = {
        'TPE': monetico_tpe,
        'date': datetime.now(timezone.utc).strftime('%d/%m/%Y:%H:%M:%S'),
        'montant': f"{payment.amount:.2f}{payment.currency}",
        'reference': reference,
        'texte-libre': f"Pack {payment.pack_type}",
        'version': '3.0',
        'lgue': payment.language.upper(),
        'societe': monetico_company,
        'mail': payment.customer_email
    }
    
    # Generate MAC
    mac = generate_monetico_mac(payment_data, monetico_key)
    payment_data['MAC'] = mac
    
    # Return payment form data
    return {
        "reference": reference,
        "payment_url": f"https://p.monetico-services.com/paiement.cgi" if monetico_mode == 'PRODUCTION' else "https://p.monetico-services.com/test/paiement.cgi",
        "form_data": payment_data
    }

@api_router.post("/monetico/callback")
async def monetico_callback(data: Dict[str, Any]):
    """Handle Monetico payment callback"""
    # Log callback for debugging
    logging.info(f"Monetico callback received: {data}")
    
    # TODO: Verify MAC, store payment result, send confirmation email, generate PDF invoice
    
    return {"version": "3.0", "cdr": "0"}  # Acknowledge receipt


# Include the routers in the main app
app.include_router(api_router)
app.include_router(ai_router)  # AI Insight generation
app.include_router(mini_analysis_router)  # Mini-Analysis with Gemini
app.include_router(extended_router)  # Extended features: PDF, Calendar, Contact Expert
# app.include_router(crm_router)  # DISABLED - duplicate with crm_complete_routes
app.include_router(crm_complete_router)  # CRM Complete (MVP) - ONLY CRM router now
app.include_router(admin_user_router)  # Admin User Management (/api/admin/users)
app.include_router(gdpr_router)  # GDPR Consent & Privacy
app.include_router(quota_router)  # Gemini Quota Queue
app.include_router(tracking_router)  # Tracking & Analytics
app.include_router(admin_router)  # Admin Dashboard & Stats

# Phase 5: CMS, Media Library & Password Recovery
try:
    app.include_router(cms_router)
    logging.info("✓ CMS/Media/Auth router registered")
except Exception as e:
    logging.error(f"✗ Failed to load cms_routes: {e}")

# Include new routers only if loaded successfully
if INVOICE_ROUTER_LOADED and invoice_router:
    app.include_router(invoice_router)  # Invoice & Billing
    logging.info("✓ Invoice router registered")
else:
    logging.warning("✗ Invoice router not registered (import failed)")

if MONETICO_ROUTER_LOADED and monetico_router:
    app.include_router(monetico_router)  # Monetico Payment Integration
    logging.info("✓ Monetico router registered")
else:
    logging.warning("✗ Monetico router not registered (import failed)")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_db_init():
    """Create MongoDB indexes for performance on startup"""
    if db is not None:
        try:
            # Leads indexes
            await db.leads.create_index("created_at", background=True)
            await db.leads.create_index("status", background=True)
            await db.leads.create_index("email", background=True)
            await db.leads.create_index("stage", background=True)
            # Contacts indexes
            await db.contacts.create_index("email", background=True)
            await db.contacts.create_index("name", background=True)
            await db.contacts.create_index("created_at", background=True)
            # Opportunities indexes  
            await db.opportunities.create_index("stage", background=True)
            await db.opportunities.create_index("contact_id", background=True)
            await db.opportunities.create_index("created_at", background=True)
            # Activities index
            await db.activities.create_index("lead_id", background=True)
            await db.activities.create_index("created_at", background=True)
            logging.info("✓ MongoDB indexes created/verified")
        except Exception as e:
            logging.warning(f"Index creation skipped: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    if client:
        client.close()
