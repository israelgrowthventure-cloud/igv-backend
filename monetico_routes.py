"""
Monetico P# 0) Vérifie que tu es bien à la racine du repo
pwd

# 1) Liste ce qu'il y a dans audit_out
Get-ChildItem .\audit_out -Force | Select Name,Length,LastWriteTime | Format-Table -Auto

# 2) Cherche le fichier (peu importe où il est)
Get-ChildItem . -Recurse -Force -File -Filter "RAPPORT_REPARATION_CRM_LIVE.md" | Select FullName,LastWriteTime

# 3) Cherche tout ce qui ressemble au nom (au cas où il a ajouté une date)
Get-ChildItem . -Recurse -Force -File | Where-Object { $_.Name -match "RAPPORT_.*REPARATION|REPARATION_.*CRM|RAPPORT_.*CRM.*LIVE" } |
  Select FullName,LastWriteTime | Sort-Object LastWriteTime -Descending | Select -First 20

# 4) Trouve dans le code où le script écrit le rapport (chemin exact)
Select-String -Path .\audit_out\*.py -Pattern "RAPPORT_REPARATION|REPARATION_CRM|write_text|open\(" -List

# 5) Montre les fichiers markdown récents (souvent il a écrit à la racine)
Get-ChildItem . -Force -File -Filter "*.md" | Sort-Object LastWriteTime -Descending | Select -First 15 FullName,LastWriteTime
yment Routes - CIC/CM Payment Integration
Production-ready with signature verification, webhooks, payment tracking
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import os
import logging
import jwt
import hashlib
import hmac
from bson import ObjectId

from models.invoice_models import Payment, PaymentStatus

router = APIRouter(prefix="/api/monetico")
security = HTTPBearer()

# MongoDB
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

mongo_client = None
db = None

def get_db():
    global mongo_client, db
    if db is None and mongo_url:
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client[db_name]
    return db

# JWT
JWT_SECRET = os.getenv('JWT_SECRET')
JWT_ALGORITHM = 'HS256'

# ==========================================
# MONETICO CONFIGURATION
# ==========================================

# These should be set in environment variables (Render)
MONETICO_TPE = os.getenv('MONETICO_TPE')  # TPE number from CIC
MONETICO_KEY = os.getenv('MONETICO_KEY')  # Security key from CIC
MONETICO_VERSION = os.getenv('MONETICO_VERSION', '3.0')
MONETICO_COMPANY_CODE = os.getenv('MONETICO_COMPANY_CODE', 'israelgrowthventure')
MONETICO_ENDPOINT = os.getenv('MONETICO_ENDPOINT', 'https://p.monetico-services.com/paiement.cgi')  # Production

# Return and notification URLs (should be set in env)
MONETICO_RETURN_URL = os.getenv('MONETICO_RETURN_URL', 'https://israelgrowthventure.com/payment/return')
MONETICO_NOTIFY_URL = os.getenv('MONETICO_NOTIFY_URL', 'https://igv-backend.onrender.com/api/monetico/notify')

# Check if Monetico is configured
MONETICO_CONFIGURED = bool(MONETICO_TPE and MONETICO_KEY)

if not MONETICO_CONFIGURED:
    logging.warning("⚠️ Monetico not configured - payment endpoints will return configuration error")
else:
    logging.info(f"✅ Monetico configured - TPE: {MONETICO_TPE}")


# ==========================================
# MONETICO SIGNATURE UTILITIES
# ==========================================

def compute_monetico_mac(data: Dict[str, Any]) -> str:
    """
    Compute Monetico MAC (HMAC-SHA1) for request authentication
    Format: MAC = HMAC-SHA1-HEX(key, data_string)
    """
    if not MONETICO_KEY:
        raise HTTPException(status_code=500, detail="Monetico key not configured")
    
    # Build data string according to Monetico spec
    # Order is critical: TPE*date*montant*reference*texte-libre*version*lgue*societe*mail
    data_string = "*".join([
        data.get("TPE", MONETICO_TPE or ""),
        data.get("date", ""),
        data.get("montant", ""),
        data.get("reference", ""),
        data.get("texte-libre", ""),
        MONETICO_VERSION,
        data.get("lgue", "FR"),
        MONETICO_COMPANY_CODE,
        data.get("mail", "")
    ])
    
    # Compute HMAC-SHA1
    mac = hmac.new(
        MONETICO_KEY.encode('utf-8'),
        data_string.encode('utf-8'),
        hashlib.sha1
    ).hexdigest().upper()
    
    return mac


def verify_monetico_mac(data: Dict[str, Any], received_mac: str) -> bool:
    """Verify MAC received from Monetico"""
    computed_mac = compute_monetico_mac(data)
    return computed_mac == received_mac.upper()


# ==========================================
# AUTH
# ==========================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT and return current user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        current_db = get_db()
        if current_db is None:
            raise HTTPException(status_code=500, detail="Database not configured")
        
        user = await current_db.crm_users.find_one({"email": payload.get("email")})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user.get("name", ""),
            "role": user.get("role", "viewer")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==========================================
# PYDANTIC MODELS
# ==========================================

class PaymentInitRequest(BaseModel):
    """Request to initiate a payment"""
    pack_id: str
    pack_name: str
    amount: float
    currency: str = "EUR"
    language: str = "fr"
    email: Optional[EmailStr] = None
    customer_name: Optional[str] = None


class MoneticopaymentWebhookData(BaseModel):
    """Webhook data from Monetico"""
    reference: str
    montant: str
    code_retour: str
    cvx: Optional[str] = None
    vld: Optional[str] = None
    brand: Optional[str] = None
    numauto: Optional[str] = None
    motifrefus: Optional[str] = None
    MAC: str
    description: str
    client_email: EmailStr
    client_name: str
    invoice_id: Optional[str] = None
    contact_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    language: str = "fr"


# ==========================================
# ROUTES
# ==========================================

@router.get("/config")
async def get_monetico_config():
    """Get Monetico configuration status (public endpoint for frontend)"""
    return {
        "configured": MONETICO_CONFIGURED,
        "tpe": MONETICO_TPE if MONETICO_CONFIGURED else None,
        "endpoint": MONETICO_ENDPOINT if MONETICO_CONFIGURED else None,
        "version": MONETICO_VERSION,
        "message": "Monetico ready" if MONETICO_CONFIGURED else "Monetico not configured - set MONETICO_TPE and MONETICO_KEY environment variables"
    }


@router.post("/init-payment")
async def init_payment_public(payment_request: PaymentInitRequest):
    """
    Public endpoint to initiate a Monetico payment (for pack purchases)
    No authentication required
    """
    if not MONETICO_CONFIGURED:
        raise HTTPException(
            status_code=500,
            detail="Le paiement Monetico n'est pas encore configuré. Contactez-nous directement à israel.growth.venture@gmail.com"
        )
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Generate payment reference
    payment_reference = f"{payment_request.pack_id.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    # Create payment record
    payment_data = {
        "payment_id": payment_reference,
        "payment_provider": "monetico",
        "amount": payment_request.amount,
        "currency": payment_request.currency,
        "status": PaymentStatus.INITIATED,
        "monetico_reference": payment_reference,
        "client_email": payment_request.email or "contact@israelgrowthventure.com",
        "client_name": payment_request.customer_name or "Client IGV",
        "return_url": MONETICO_RETURN_URL,
        "notify_url": MONETICO_NOTIFY_URL,
        "initiated_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "metadata": {
            "pack_id": payment_request.pack_id,
            "pack_name": payment_request.pack_name,
            "language": payment_request.language
        }
    }
    
    result = await current_db.payments.insert_one(payment_data)
    payment_data["_id"] = str(result.inserted_id)
    
    # Build Monetico form data
    # Date format: dd/MM/yyyy:HH:mm:ss
    payment_date = datetime.now(timezone.utc).strftime("%d/%m/%Y:%H:%M:%S")
    
    # Amount format: 123.45EUR
    montant = f"{payment_request.amount:.2f}{payment_request.currency}"
    
    # Build form data
    form_data = {
        "TPE": MONETICO_TPE,
        "date": payment_date,
        "montant": montant,
        "reference": payment_reference,
        "texte-libre": f"{payment_request.pack_name}",
        "mail": payment_request.email or "contact@israelgrowthventure.com",
        "lgue": payment_request.language.upper() if payment_request.language else "FR",
        "societe": MONETICO_COMPANY_CODE,
        "url_retour": MONETICO_RETURN_URL,
        "url_retour_ok": f"{MONETICO_RETURN_URL}?status=success&ref={payment_reference}",
        "url_retour_err": f"{MONETICO_RETURN_URL}?status=error&ref={payment_reference}"
    }
    
    # Compute MAC
    mac = compute_monetico_mac(form_data)
    form_data["MAC"] = mac
    form_data["version"] = MONETICO_VERSION
    
    logging.info(f"Payment initiated: {payment_reference} - {payment_request.pack_name} - {montant}")
    
    return {
        "payment_id": payment_reference,
        "form_action": MONETICO_ENDPOINT,
        "form_data": form_data,
        "payment_url": None  # Client will submit form via POST
    }


@router.post("/init")
async def init_payment(
    payment_request: PaymentInitRequest,
    user: Dict = Depends(get_current_user)
):
    """
    Initiate a Monetico payment (admin authenticated)
    Returns form data to redirect user to Monetico payment page
    """
    if not MONETICO_CONFIGURED:
        raise HTTPException(
            status_code=503,
            detail="Monetico payment not configured. Please set MONETICO_TPE and MONETICO_KEY environment variables."
        )
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Use the public endpoint logic
    return await init_payment_public(payment_request)
    
    # Timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "payment",
        "entity_id": str(result.inserted_id),
        "event_type": "payment_initiated",
        "description": f"Payment initiated: {payment_request.reference} - {payment_request.amount} {payment_request.currency}",
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    logging.info(f"Payment initiated: {payment_id} - {payment_request.amount} {payment_request.currency}")
    
    return {
        "success": True,
        "payment_id": payment_id,
        "monetico_endpoint": MONETICO_ENDPOINT,
        "form_data": form_data
    }


@router.post("/notify")
async def monetico_notify(request: Request):
    """
    Monetico IPN (Instant Payment Notification) endpoint
    Called by Monetico server after payment
    CRITICAL: Must verify MAC signature
    """
    if not MONETICO_CONFIGURED:
        logging.error("Monetico notify called but Monetico not configured")
        return {"status": "error", "message": "Monetico not configured"}
    
    # Get form data
    form_data = await request.form()
    data = dict(form_data)
    
    logging.info(f"Monetico notification received: {data.get('reference')}")
    
    # Verify MAC
    received_mac = data.get("MAC")
    if not received_mac:
        logging.error("Monetico notification: MAC missing")
        return {"status": "error", "message": "MAC missing"}
    
    # Verify signature
    try:
        is_valid = verify_monetico_mac(data, received_mac)
        if not is_valid:
            logging.error(f"Monetico notification: Invalid MAC for reference {data.get('reference')}")
            return {"status": "error", "message": "Invalid MAC"}
    except Exception as e:
        logging.error(f"Monetico MAC verification error: {str(e)}")
        return {"status": "error", "message": "MAC verification failed"}
    
    # Extract payment info
    reference = data.get("reference")
    code_retour = data.get("code-retour")  # "payetest" (test) or "paye" (prod) = success
    montant = data.get("montant")
    
    # Determine payment status
    if code_retour in ["paye", "payetest"]:
        payment_status = PaymentStatus.PAID
    else:
        payment_status = PaymentStatus.FAILED
    
    # Find payment in DB
    current_db = get_db()
    if current_db is None:
        logging.error("Database not configured")
        return {"status": "error", "message": "Database error"}
    
    payment = await current_db.payments.find_one({"monetico_reference": reference})
    
    if not payment:
        logging.warning(f"Payment not found for reference: {reference}")
        # Still return success to Monetico to avoid retries
        return {"status": "ok", "message": "Payment not found but acknowledged"}
    
    # Check idempotence (prevent double processing)
    if payment["status"] == PaymentStatus.PAID:
        logging.info(f"Payment already processed: {reference}")
        return {"status": "ok", "message": "Already processed"}
    
    # Update payment
    update_data = {
        "status": payment_status,
        "provider_transaction_id": data.get("numauto"),
        "payment_method": data.get("modepaiement"),
        "card_last4": data.get("last4"),
        "monetico_context": data,
        "updated_at": datetime.now(timezone.utc)
    }
    
    if payment_status == PaymentStatus.PAID:
        update_data["paid_at"] = datetime.now(timezone.utc)
    else:
        update_data["failed_at"] = datetime.now(timezone.utc)
        update_data["error_code"] = code_retour
        update_data["error_message"] = data.get("motifrefus", "Payment failed")
    
    await current_db.payments.update_one(
        {"_id": payment["_id"]},
        {"$set": update_data}
    )
    
    # Update related invoice if exists
    if payment.get("invoice_id"):
        try:
            invoice_id = ObjectId(payment["invoice_id"])
            if payment_status == PaymentStatus.PAID:
                await current_db.invoices.update_one(
                    {"_id": invoice_id},
                    {
                        "$set": {
                            "status": "PAID",
                            "paid_amount": payment["amount"],
                            "payment_date": datetime.now(timezone.utc),
                            "payment_method": "monetico",
                            "payment_id": str(payment["_id"]),
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                
                # Timeline event
                await current_db.timeline_events.insert_one({
                    "entity_type": "invoice",
                    "entity_id": payment["invoice_id"],
                    "event_type": "payment_received",
                    "description": f"Payment received via Monetico: {montant}",
                    "created_at": datetime.now(timezone.utc)
                })
        except Exception as e:
            logging.error(f"Error updating invoice: {str(e)}")
    
    # Timeline event for payment
    await current_db.timeline_events.insert_one({
        "entity_type": "payment",
        "entity_id": str(payment["_id"]),
        "event_type": "payment_confirmed" if payment_status == PaymentStatus.PAID else "payment_failed",
        "description": f"Monetico payment {'succeeded' if payment_status == PaymentStatus.PAID else 'failed'}: {reference}",
        "created_at": datetime.now(timezone.utc)
    })
    
    logging.info(f"Payment {reference} processed: {payment_status}")
    
    # CRITICAL: Return proper response for Monetico
    # Monetico expects specific response format
    response = f"version=2\ncdr=0"  # cdr=0 means ok
    return response


@router.get("/payment/{payment_id}")
async def get_payment_status(
    payment_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get payment status"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    payment = await current_db.payments.find_one({"payment_id": payment_id})
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment["_id"] = str(payment["_id"])
    
    return payment


@router.get("/payments")
async def list_payments(
    user: Dict = Depends(get_current_user),
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List payments"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if status:
        query["status"] = status
    
    payments = await current_db.payments.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
    
    for payment in payments:
        payment["_id"] = str(payment["_id"])
    
    total = await current_db.payments.count_documents(query)
    
    return {
        "payments": payments,
        "total": total,
        "skip": skip,
        "limit": limit
    }
