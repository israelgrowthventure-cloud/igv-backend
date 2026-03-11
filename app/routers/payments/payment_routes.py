"""
Payment Routes - Payoneer Integration (no API / no webhook)
Manual workflow: init session → client pays via Payoneer link → admin confirms
Collection: payment_sessions
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import os
import logging
import uuid
import base64
import jwt

try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        import pytz
        class ZoneInfo:
            def __new__(cls, key):
                return pytz.timezone(key)

# PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from io import BytesIO
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("reportlab not available — PDF generation disabled in payment_routes")

router = APIRouter(prefix="/api")
security = HTTPBearer()

# ─── Config ─────────────────────────────────────────────────────────────────
mongo_url = os.getenv("MONGODB_URI") or os.getenv("MONGO_URL")
db_name   = os.getenv("DB_NAME", "igv_production")
JWT_SECRET    = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

PUBLIC_BASE_URL  = os.getenv("PUBLIC_BASE_URL",  "https://israelgrowthventure.com")
BACKEND_BASE_URL = os.getenv("BACKEND_URL",       "https://igv-cms-backend.onrender.com")
PAYONEER_LINK_EUR = os.getenv("PAYONEER_PAYMENT_LINK_EUR", "")
PAYONEER_LINK_USD = os.getenv("PAYONEER_PAYMENT_LINK_USD", "")
DEFAULT_CURRENCY  = os.getenv("PAYMENTS_DEFAULT_CURRENCY", "EUR")

TZ_JERUSALEM = ZoneInfo("Asia/Jerusalem")

COMPANY_NAME    = "Israel Growth Venture"
COMPANY_EMAIL   = "contact@israelgrowthventure.com"
COMPANY_WEBSITE = "israelgrowthventure.com"
COMPANY_ADDRESS = "Tel Aviv, Israel"

# ─── DB ─────────────────────────────────────────────────────────────────────
_mongo_client = None
_db = None

def get_db():
    global _mongo_client, _db
    if _db is None and mongo_url:
        _mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )
        _db = _mongo_client[db_name]
    return _db


# ─── Auth (admin only) ───────────────────────────────────────────────────────
async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        if payload.get("role") not in ("admin", "superadmin"):
            raise HTTPException(status_code=403, detail="Admin access required")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Helpers ────────────────────────────────────────────────────────────────
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_il() -> datetime:
    return datetime.now(TZ_JERUSALEM)


def _generate_invoice_number() -> str:
    n = _now_il()
    return f"IGV-{n.year}{n.month:02d}-{uuid.uuid4().hex[:6].upper()}"


def _dt_iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


# ─── PDF: Proforma ───────────────────────────────────────────────────────────
def _generate_proforma_pdf(session: dict) -> bytes:
    if not PDF_AVAILABLE:
        raise RuntimeError("reportlab not installed")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()

    s_header = ParagraphStyle(
        "PHeader", parent=styles["Normal"],
        fontSize=22, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#00318D"), alignment=TA_CENTER,
    )
    s_proforma = ParagraphStyle(
        "SProforma", parent=styles["Normal"],
        fontSize=12, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#CC5500"), alignment=TA_CENTER,
    )
    s_title2 = ParagraphStyle(
        "ST2", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#00318D"),
    )
    s_small = ParagraphStyle(
        "SSmall", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#6b7280"),
    )
    s_footer = ParagraphStyle(
        "SFoot", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER,
    )
    N = styles["Normal"]

    created = session.get("created_at", _now_utc())
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    created_il = created.astimezone(TZ_JERUSALEM)

    amount   = session.get("amount", 900)
    currency = session.get("currency", "EUR")
    sym      = "€" if currency == "EUR" else "$"
    desc     = session.get("description", "Audit Stratégique Israel Growth Venture (60 min)")
    sid      = session.get("session_id", "N/A")

    story = []
    story.append(Paragraph(COMPANY_NAME, s_header))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("FACTURE PROFORMA — PAIEMENT EN ATTENTE", s_proforma))
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(
        "Ce document ne constitue pas une facture définitive. "
        "Il sera remplacé par la facture officielle après confirmation du paiement.",
        s_small,
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#00318D")))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(f"Référence dossier : <b>{sid[:18].upper()}</b>", N))
    story.append(Paragraph(
        f"Date d'émission : {created_il.strftime('%d/%m/%Y %H:%M')} (heure Israël)", N,
    ))
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph("CLIENT", s_title2))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(f"Email : {session.get('email', '')}", N))
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph("PRESTATION", s_title2))
    story.append(Spacer(1, 0.15 * cm))

    tdata = [
        ["Description", "Montant"],
        [desc, f"{amount} {sym}"],
        ["", ""],
        ["TOTAL", f"{amount} {sym}"],
    ]
    tbl = Table(tdata, colWidths=[12 * cm, 4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#00318D")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",        (1, 0), (1, -1), "RIGHT"),
        ("ALIGN",        (0, 3), (0,  3), "RIGHT"),
        ("FONTNAME",     (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 3), (-1, 3), 12),
        ("BACKGROUND",   (0, 3), (-1, 3), colors.HexColor("#eff6ff")),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, 2), [colors.white, colors.HexColor("#f9fafb")]),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "TVA : non applicable — exonération art. 259-1 CGI / prestations B2B internationales.",
        s_small,
    ))
    story.append(Spacer(1, 0.8 * cm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d1d5db")))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("INSTRUCTIONS DE PAIEMENT", s_title2))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Le règlement s'effectue via Payoneer en suivant le lien de paiement fourni sur notre site.",
        N,
    ))
    story.append(Paragraph(
        "La facture définitive vous sera envoyée par email après confirmation par notre équipe (délai : 48h ouvrées max).",
        N,
    ))
    story.append(Spacer(1, 1 * cm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"{COMPANY_NAME} — {COMPANY_EMAIL} — {COMPANY_WEBSITE}",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()


# ─── PDF: Final Invoice ──────────────────────────────────────────────────────
def _generate_invoice_pdf(session: dict) -> bytes:
    if not PDF_AVAILABLE:
        raise RuntimeError("reportlab not installed")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()

    s_header = ParagraphStyle(
        "IHeader", parent=styles["Normal"],
        fontSize=22, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#00318D"), alignment=TA_CENTER,
    )
    s_inv_title = ParagraphStyle(
        "ITitle", parent=styles["Normal"],
        fontSize=16, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111827"), alignment=TA_CENTER,
    )
    s_title2 = ParagraphStyle(
        "IT2", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#00318D"),
    )
    s_small = ParagraphStyle(
        "ISmall", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#6b7280"),
    )
    s_footer = ParagraphStyle(
        "IFoot", parent=styles["Normal"],
        fontSize=8, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER,
    )
    N = styles["Normal"]

    paid_at = session.get("paid_at", _now_utc())
    if isinstance(paid_at, str):
        paid_at = datetime.fromisoformat(paid_at)
    paid_il = paid_at.astimezone(TZ_JERUSALEM)

    invoice_number = session.get("invoice_number", _generate_invoice_number())
    amount   = session.get("amount", 900)
    currency = session.get("currency", "EUR")
    sym      = "€" if currency == "EUR" else "$"
    desc     = session.get("description", "Audit Stratégique Israel Growth Venture (60 min)")

    story = []
    story.append(Paragraph(COMPANY_NAME, s_header))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("FACTURE", s_inv_title))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#00318D")))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(f"N° de facture : <b>{invoice_number}</b>", N))
    story.append(Paragraph(
        f"Date de facturation : {paid_il.strftime('%d/%m/%Y')} (heure Israël)", N,
    ))
    story.append(Spacer(1, 0.8 * cm))

    story.append(Paragraph("VENDEUR", s_title2))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(f"<b>{COMPANY_NAME}</b>", N))
    story.append(Paragraph(COMPANY_ADDRESS, N))
    story.append(Paragraph(f"Email : {COMPANY_EMAIL}", N))
    story.append(Paragraph(f"Site : {COMPANY_WEBSITE}", N))
    story.append(Spacer(1, 0.7 * cm))

    story.append(Paragraph("ACHETEUR", s_title2))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(f"Email : {session.get('email', '')}", N))
    story.append(Spacer(1, 0.8 * cm))

    tdata = [
        ["Description", "Montant"],
        [desc, f"{amount} {sym}"],
        ["", ""],
        ["TOTAL", f"{amount} {sym}"],
    ]
    tbl = Table(tdata, colWidths=[12 * cm, 4 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#00318D")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",        (1, 0), (1, -1), "RIGHT"),
        ("ALIGN",        (0, 3), (0,  3), "RIGHT"),
        ("FONTNAME",     (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 3), (-1, 3), 12),
        ("BACKGROUND",   (0, 3), (-1, 3), colors.HexColor("#eff6ff")),
        ("GRID",         (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, 2), [colors.white, colors.HexColor("#f9fafb")]),
        ("TOPPADDING",   (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "TVA : non applicable — exonération art. 259-1 CGI / prestations B2B internationales.",
        s_small,
    ))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"Règlement reçu via Payoneer le {paid_il.strftime('%d/%m/%Y')}.", N,
    ))
    story.append(Spacer(1, 1 * cm))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"{COMPANY_NAME} — {COMPANY_EMAIL} — {COMPANY_WEBSITE}",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()


# ─── Pydantic Models ─────────────────────────────────────────────────────────
class PayoneerInitRequest(BaseModel):
    email: EmailStr
    amount: float = 900.0
    currency: str = "EUR"
    description: str = "Audit Stratégique Israel Growth Venture (60 min)"


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/payments/payoneer/init")
async def init_payoneer_payment(body: PayoneerInitRequest):
    """
    Create a pending PaymentSession.
    Returns: { session_id, payoneer_url, success_url, proforma_url, status }
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    currency = body.currency.upper()
    if currency not in ("EUR", "USD"):
        currency = DEFAULT_CURRENCY.upper()

    payoneer_url = PAYONEER_LINK_EUR if currency == "EUR" else PAYONEER_LINK_USD
    if not payoneer_url:
        raise HTTPException(
            status_code=500,
            detail=f"PAYONEER_PAYMENT_LINK_{currency} not configured on server",
        )

    session_id = str(uuid.uuid4())
    now = _now_utc()

    session_data = {
        "session_id": session_id,
        "email": body.email,
        "amount": body.amount,
        "currency": currency,
        "description": body.description,
        "created_at": now,
    }

    # Generate proforma immediately
    proforma_b64 = None
    try:
        pdf_bytes  = _generate_proforma_pdf(session_data)
        proforma_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        logging.info(f"[payment] Proforma PDF generated for session {session_id[:8]}")
    except Exception as exc:
        logging.error(f"[payment] Proforma PDF failed: {exc}")

    record = {
        "session_id":      session_id,
        "email":           body.email,
        "amount":          body.amount,
        "currency":        currency,
        "description":     body.description,
        "status":          "pending",
        "provider":        "payoneer",
        "provider_link":   currency.lower(),
        "created_at":      now,
        "updated_at":      now,
        "paid_at":         None,
        "proforma_pdf_b64": proforma_b64,
        "invoice_pdf_b64": None,
        "invoice_number":  None,
    }
    await current_db.payment_sessions.insert_one(record)

    success_url  = f"{PUBLIC_BASE_URL}/payment/success?sid={session_id}"
    proforma_url = f"{BACKEND_BASE_URL}/api/invoices/proforma/{session_id}.pdf"

    logging.info(
        f"[payment] Session created: id={session_id[:8]} email={body.email} "
        f"amount={body.amount} {currency}"
    )

    return {
        "session_id":   session_id,
        "payoneer_url": payoneer_url,
        "success_url":  success_url,
        "proforma_url": proforma_url,
        "status":       "pending",
    }


@router.get("/payments/{session_id}")
async def get_payment_session(session_id: str):
    """
    Get payment session status.
    invoice_url is only returned when status == 'paid'.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    session = await current_db.payment_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    proforma_url = (
        f"{BACKEND_BASE_URL}/api/invoices/proforma/{session_id}.pdf"
        if session.get("proforma_pdf_b64") else None
    )
    invoice_url = (
        f"{BACKEND_BASE_URL}/api/invoices/final/{session_id}.pdf"
        if session.get("status") == "paid" and session.get("invoice_pdf_b64") else None
    )

    return {
        "session_id":     session_id,
        "status":         session["status"],
        "email":          session["email"],
        "amount":         session["amount"],
        "currency":       session["currency"],
        "description":    session.get("description"),
        "created_at":     _dt_iso(session.get("created_at")),
        "paid_at":        _dt_iso(session.get("paid_at")),
        "invoice_number": session.get("invoice_number"),
        "proforma_url":   proforma_url,
        "invoice_url":    invoice_url,
    }


@router.post("/admin/payments/{session_id}/mark-paid")
async def mark_payment_paid(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_admin),
):
    """
    Mark a payment session as paid and generate the final invoice PDF.
    Protected: admin only.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    session = await current_db.payment_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] == "paid":
        raise HTTPException(status_code=400, detail="Session already marked as paid")

    invoice_number = _generate_invoice_number()
    now = _now_utc()

    # Build enriched session dict for PDF
    session_for_pdf = {
        **{k: v for k, v in session.items() if k != "_id"},
        "paid_at": now,
        "invoice_number": invoice_number,
    }

    try:
        pdf_bytes   = _generate_invoice_pdf(session_for_pdf)
        invoice_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as exc:
        logging.error(f"[payment] Invoice PDF generation failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Invoice PDF generation failed: {exc}")

    await current_db.payment_sessions.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "status":         "paid",
                "paid_at":        now,
                "updated_at":     now,
                "invoice_number": invoice_number,
                "invoice_pdf_b64": invoice_b64,
                "confirmed_by":   current_user.get("email", "admin"),
            }
        },
    )

    invoice_url = f"{BACKEND_BASE_URL}/api/invoices/final/{session_id}.pdf"
    logging.info(
        f"[payment] PAID: id={session_id[:8]} invoice={invoice_number} "
        f"by={current_user.get('email')}"
    )

    return {
        "success":        True,
        "session_id":     session_id,
        "status":         "paid",
        "invoice_number": invoice_number,
        "invoice_url":    invoice_url,
        "paid_at":        now.isoformat(),
    }


@router.get("/admin/payments")
async def list_payment_sessions(
    status: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_admin),
):
    """List payment sessions — admin only."""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    query: Dict[str, Any] = {}
    if status:
        query["status"] = status

    cursor   = current_db.payment_sessions.find(query).sort("created_at", -1).limit(200)
    sessions = await cursor.to_list(length=200)

    result = []
    for s in sessions:
        result.append({
            "session_id":     s["session_id"],
            "email":          s["email"],
            "amount":         s["amount"],
            "currency":       s["currency"],
            "status":         s["status"],
            "provider":       s.get("provider", "payoneer"),
            "description":    s.get("description"),
            "created_at":     _dt_iso(s.get("created_at")),
            "paid_at":        _dt_iso(s.get("paid_at")),
            "invoice_number": s.get("invoice_number"),
            "proforma_url":   (
                f"{BACKEND_BASE_URL}/api/invoices/proforma/{s['session_id']}.pdf"
                if s.get("proforma_pdf_b64") else None
            ),
            "invoice_url": (
                f"{BACKEND_BASE_URL}/api/invoices/final/{s['session_id']}.pdf"
                if s.get("status") == "paid" and s.get("invoice_pdf_b64") else None
            ),
        })

    return {"payments": result, "total": len(result)}


@router.get("/invoices/proforma/{session_id}.pdf")
async def serve_proforma_pdf(session_id: str):
    """Serve proforma PDF (accessible by anyone with the session_id)."""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    session = await current_db.payment_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_b64 = session.get("proforma_pdf_b64")
    if not pdf_b64:
        raise HTTPException(status_code=404, detail="Proforma PDF not yet generated")

    pdf_bytes = base64.b64decode(pdf_b64)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=proforma_{session_id[:8]}.pdf"
        },
    )


@router.get("/invoices/final/{session_id}.pdf")
async def serve_final_invoice_pdf(session_id: str):
    """
    Serve final invoice PDF.
    Only available when status == 'paid'. Returns 403 otherwise.
    """
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    session = await current_db.payment_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") != "paid":
        raise HTTPException(
            status_code=403,
            detail="Facture non disponible : paiement non encore confirmé",
        )

    pdf_b64 = session.get("invoice_pdf_b64")
    if not pdf_b64:
        raise HTTPException(status_code=404, detail="Invoice PDF not generated")

    pdf_bytes = base64.b64decode(pdf_b64)
    inv_num   = session.get("invoice_number", session_id[:8])
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=facture_{inv_num}.pdf"
        },
    )
