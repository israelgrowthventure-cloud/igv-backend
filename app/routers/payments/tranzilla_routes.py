"""
Tranzilla Payment Routes — Israeli Payment Gateway Integration
Terminal: fxpigv148 | Supplier: 0070698
Production-ready: hosted payment page, webhook notification, payment tracking
"""

VERSION = "7.1-CHECKOUT-POST-NO-LANG"

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import logging
import jwt
import uuid
import html

router = APIRouter(prefix="/api/tranzilla")
security = HTTPBearer()

# ──────────────────────────────────────────
# MongoDB
# ──────────────────────────────────────────
_mongo_url = os.getenv('MONGODB_URI')
_db_name = os.getenv('DB_NAME', 'igv_production')
_mongo_client = None
_db = None


def get_db():
    global _mongo_client, _db
    if _db is None and _mongo_url:
        _mongo_client = AsyncIOMotorClient(
            _mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        _db = _mongo_client[_db_name]
    return _db


# ──────────────────────────────────────────
# JWT helpers
# ──────────────────────────────────────────
JWT_SECRET = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = 'HS256'


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ──────────────────────────────────────────
# TRANZILLA CONFIGURATION
# ──────────────────────────────────────────
TRANZILLA_TERMINAL = os.getenv('TRANZILLA_TERMINAL')
TRANZILLA_PW = os.getenv('TRANZILLA_PW')

SITE_URL = os.getenv('SITE_URL', 'https://israelgrowthventure.com')
BACKEND_URL = os.getenv('BACKEND_URL', 'https://igv-cms-backend.onrender.com')

TRANZILLA_SUCCESS_URL = os.getenv('TRANZILLA_SUCCESS_URL', f"{SITE_URL}/payment/success")
TRANZILLA_FAIL_URL = os.getenv('TRANZILLA_FAIL_URL', f"{SITE_URL}/payment/failure")
TRANZILLA_NOTIFY_URL = os.getenv('TRANZILLA_NOTIFY_URL', f"{BACKEND_URL}/api/tranzilla/notify")

TRANZILLA_CONFIGURED = bool(TRANZILLA_TERMINAL and TRANZILLA_PW)

if TRANZILLA_CONFIGURED:
    logging.info(f"✅ Tranzilla configured — terminal: {TRANZILLA_TERMINAL}")
else:
    logging.warning("⚠️ Tranzilla not fully configured (set TRANZILLA_TERMINAL + TRANZILLA_PW)")


# ──────────────────────────────────────────
# CURRENCY HELPERS
# ──────────────────────────────────────────
CURRENCY_MAP = {
    'ILS': 1,
    'USD': 2,
    'EUR': 978,
    'GBP': 826,
}


def currency_to_tranzilla(currency_code: str) -> int:
    return CURRENCY_MAP.get((currency_code or 'EUR').upper(), 978)


def tranzilla_to_currency(code: int) -> str:
    reverse = {v: k for k, v in CURRENCY_MAP.items()}
    return reverse.get(code, 'EUR')


# ──────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────
class InitPaymentRequest(BaseModel):
    pack_id: str
    pack_name: str
    amount: float
    currency: str = 'EUR'
    language: str = 'fr'
    customer_email: Optional[str] = None
    customer_name: Optional[str] = None
    pack_type: Optional[str] = None
    booking_start: Optional[str] = None
    booking_end: Optional[str] = None
    booking_name: Optional[str] = None
    booking_phone: Optional[str] = None


# ──────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────
@router.get("/config")
async def tranzilla_config():
    """Check if Tranzilla is configured (public endpoint)."""
    return {
        "configured": TRANZILLA_CONFIGURED,
        "terminal": TRANZILLA_TERMINAL if TRANZILLA_CONFIGURED else None,
        "provider": "tranzilla",
    }


@router.post("/init-payment")
async def init_payment(req: InitPaymentRequest):
    """
    Initialize a Tranzilla payment session.
    Stores payment record and returns only the internal reference.
    """
    if not TRANZILLA_CONFIGURED:
        raise HTTPException(
            status_code=500,
            detail="Tranzilla payment gateway not configured. Please contact support."
        )

    db = get_db()
    if db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Please try again later."
        )

    reference = f"IGV-{uuid.uuid4().hex[:10].upper()}"

    payment_doc = {
        "payment_id": reference,
        "payment_provider": "tranzilla",
        "pack_id": req.pack_id,
        "pack_name": req.pack_name,
        "amount": req.amount,
        "currency": req.currency.upper(),
        "language": req.language,
        "client_email": req.customer_email,
        "client_name": req.customer_name or "Client IGV",
        "status": "INITIATED",
        "tranzilla_terminal": TRANZILLA_TERMINAL,
        "tranzilla_transaction_id": None,
        "tranzilla_auth_nr": None,
        "tranzilla_response_code": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "booking_start": req.booking_start,
        "booking_end": req.booking_end,
        "booking_email": req.customer_email,
        "booking_name": req.booking_name,
        "booking_phone": req.booking_phone,
        "booking_confirmed": False,
        "booking_meet_link": None,
        "booking_event_id": None,
        "booking_error": None,
    }

    try:
        await db.payments.insert_one(payment_doc)
    except Exception as e:
        logging.error(f"Could not save payment record: {e}")
        raise HTTPException(
            status_code=500,
            detail="Could not initialize payment. Please try again."
        )

    logging.info(
        f"[Tranzilla] Payment initialized — ref: {reference} | "
        f"amount: {req.amount} {req.currency} | pack: {req.pack_id}"
    )

    return {
        "reference": reference,
        "provider": "tranzilla",
    }


@router.get("/checkout/{reference}", response_class=HTMLResponse)
async def checkout(reference: str):
    """
    Loads payment data from backend and returns an auto-submitting POST form to Tranzilla.
    TranzilaPW is sent in POST body only, never in URL.
    """
    if not TRANZILLA_CONFIGURED:
        raise HTTPException(
            status_code=500,
            detail="Tranzilla payment gateway not configured. Please contact support."
        )

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    payment_doc = await db.payments.find_one({"payment_id": reference})
    if not payment_doc:
        raise HTTPException(status_code=404, detail="Payment not found")

    amount = float(payment_doc.get("amount", 0))
    currency = str(currency_to_tranzilla(payment_doc.get("currency", "EUR")))
    customer_name = payment_doc.get("client_name") or "Client IGV"
    customer_email = payment_doc.get("client_email") or ""
    pack_name = (payment_doc.get("pack_name") or "Audit IGV")[:50]

    tranzilla_action = f"https://direct.tranzila.com/{TRANZILLA_TERMINAL}/iframenew.php"

    fields = {
        "supplier": TRANZILLA_TERMINAL,
        "TranzilaPW": TRANZILLA_PW,
        "sum": f"{amount:.2f}",
        "currency": currency,
        "cred_type": "1",
        "tranmode": "A",
        "contact": customer_name,
        "email": customer_email,
        "noorder": reference,
        "pdesc": pack_name,
        "success_url": TRANZILLA_SUCCESS_URL,
        "fail_url": TRANZILLA_FAIL_URL,
        "notify_url": TRANZILLA_NOTIFY_URL,
    }

    inputs_html = "\n".join(
        f'<input type="hidden" name="{html.escape(str(key), quote=True)}" value="{html.escape(str(value), quote=True)}">'
        for key, value in fields.items()
    )

    page_html = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Redirection vers le paiement sécurisé</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <form id="tranzilla-checkout-form" method="POST" action="{html.escape(tranzilla_action, quote=True)}">
    {inputs_html}
    <noscript>
      <p>Redirection vers le paiement sécurisé.</p>
      <button type="submit">Continuer</button>
    </noscript>
  </form>
  <script>
    document.getElementById('tranzilla-checkout-form').submit();
  </script>
</body>
</html>"""

    return HTMLResponse(content=page_html)


# ──────────────────────────────────────────
# BOOKING TRIGGER (called after PAID)
# ──────────────────────────────────────────
async def _trigger_booking_after_payment(db, noorder: str, payment_doc: dict):
    """
    Creates a Google Calendar event + sends confirmation email after successful payment.
    Stores meetLink and eventId in the payment record.
    Non-fatal: logs errors, never crashes the notify webhook.
    """
    from datetime import datetime as _dt

    try:
        from app.routers.booking_routes import _create_booking_event
    except ImportError:
        logging.error("[tranzilla] Cannot import _create_booking_event — booking module not available")
        return

    booking_start = payment_doc.get("booking_start")
    booking_end = payment_doc.get("booking_end")
    booking_email = payment_doc.get("booking_email")

    if not (booking_start and booking_end and booking_email):
        logging.info(f"[tranzilla] No booking data for ref {noorder} — skipping calendar creation")
        return

    try:
        tz = ZoneInfo("Asia/Jerusalem")
        start_dt = _dt.fromisoformat(booking_start)
        end_dt = _dt.fromisoformat(booking_end)

        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=tz)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=tz)

        result = await _create_booking_event(
            start_dt=start_dt,
            end_dt=end_dt,
            email=booking_email,
            name=payment_doc.get("booking_name"),
            phone=payment_doc.get("booking_phone"),
            topic="audit",
        )

        await db.payments.update_one(
            {"payment_id": noorder},
            {"$set": {
                "booking_confirmed": True,
                "booking_meet_link": result.get("meetLink"),
                "booking_event_id": result.get("eventId"),
                "booking_error": None,
                "updated_at": datetime.now(timezone.utc),
            }}
        )
        logging.info(f"[tranzilla] Booking created for ref {noorder} — meetLink: {result.get('meetLink')}")

    except Exception as exc:
        error_msg = str(exc)
        logging.error(f"[tranzilla] Booking creation failed for ref {noorder}: {error_msg}")
        try:
            await db.payments.update_one(
                {"payment_id": noorder},
                {"$set": {
                    "booking_confirmed": False,
                    "booking_error": error_msg,
                    "updated_at": datetime.now(timezone.utc),
                }}
            )
        except Exception:
            pass


@router.post("/notify")
async def tranzilla_notify(request: Request):
    """
    Webhook endpoint — Tranzilla notifies us of payment result.
    Accepts both GET params and POST form data.
    """
    db = get_db()

    try:
        form = await request.form()
        data = dict(form)
    except Exception:
        data = {}

    if not data:
        data = dict(request.query_params)

    response_code = data.get("Response", "")
    transaction_id = data.get("TransactionId", "")
    auth_nr = data.get("AuthNr", "")
    noorder = data.get("noorder", "")
    amount_str = data.get("sum", "0")
    currency_code = data.get("currency", "978")
    card_type = data.get("cardtype", "")
    last4 = data.get("last4num", "")

    if not noorder:
        logging.warning("Tranzilla notify: missing noorder reference")
        return {"status": "ignored", "reason": "missing_reference"}

    is_success = response_code == "000"
    status = "PAID" if is_success else "FAILED"

    logging.info(f"Tranzilla notify — ref: {noorder} | response: {response_code} | status: {status}")

    if db is not None:
        try:
            update_data = {
                "status": status,
                "tranzilla_response_code": response_code,
                "tranzilla_transaction_id": transaction_id,
                "tranzilla_auth_nr": auth_nr,
                "payment_method": card_type,
                "card_last4": last4,
                "updated_at": datetime.now(timezone.utc),
            }
            if is_success:
                update_data["paid_at"] = datetime.now(timezone.utc)
            else:
                update_data["failed_at"] = datetime.now(timezone.utc)

            await db.payments.update_one(
                {"payment_id": noorder},
                {"$set": update_data}
            )

            await db.timeline_events.insert_one({
                "entity_type": "payment",
                "entity_id": noorder,
                "event_type": "payment_confirmed" if is_success else "payment_failed",
                "data": {
                    "response_code": response_code,
                    "transaction_id": transaction_id,
                    "auth_nr": auth_nr,
                    "amount": amount_str,
                    "currency": tranzilla_to_currency(int(currency_code) if str(currency_code).isdigit() else 978),
                },
                "created_at": datetime.now(timezone.utc),
            })

            if is_success:
                payment_doc = await db.payments.find_one({"payment_id": noorder})
                if payment_doc:
                    await _trigger_booking_after_payment(db, noorder, payment_doc)

        except Exception as e:
            logging.error(f"Tranzilla notify DB error: {e}")

    return {"status": "ok", "reference": noorder, "payment_status": status}


@router.get("/payment/{reference}")
async def get_payment_status(
    reference: str,
    _admin=Depends(verify_admin_token)
):
    """Get payment status by reference (admin only)."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await db.payments.find_one({"payment_id": reference})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment not found")

    doc["_id"] = str(doc["_id"])
    return doc


@router.get("/payments")
async def list_payments(
    status: Optional[str] = None,
    limit: int = 50,
    _admin=Depends(verify_admin_token)
):
    """List all Tranzilla payments (admin only)."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    query: Dict[str, Any] = {"payment_provider": "tranzilla"}
    if status:
        query["status"] = status.upper()

    cursor = db.payments.find(query).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        doc["_id"] = str(doc["_id"])

    return {"payments": docs, "count": len(docs)}


@router.get("/booking/{reference}")
async def get_booking_status(reference: str):
    """
    Public endpoint — frontend polls after payment to get booking/meetLink status.
    Returns: { payment_status, booking_confirmed, meet_link, event_id, booking_start, booking_error }
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await db.payments.find_one({"payment_id": reference})
    if not doc:
        raise HTTPException(status_code=404, detail="Payment not found")

    return {
        "payment_status": doc.get("status"),
        "booking_confirmed": doc.get("booking_confirmed", False),
        "meet_link": doc.get("booking_meet_link"),
        "event_id": doc.get("booking_event_id"),
        "booking_start": doc.get("booking_start"),
        "booking_error": doc.get("booking_error"),
    }