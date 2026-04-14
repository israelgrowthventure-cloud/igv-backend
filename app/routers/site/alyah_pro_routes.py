"""
Alyah Pro Lead Endpoint — IGV
POST /api/leads/alyah-pro

Reçoit le formulaire de découverte Alyah Pro, sauvegarde en MongoDB
collection "leads" et envoie un email de notification SMTP à l'équipe IGV.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from motor.motor_asyncio import AsyncIOMotorClient

# ── Configuration ────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api")

mongo_url = os.getenv('MONGODB_URI')
db_name = os.getenv('DB_NAME', 'igv_production')

EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@israelgrowthventure.com')
EMAIL_NOTIFY = os.getenv('NOTIFY_EMAIL', 'israel.growth.venture@gmail.com')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

# Conditional email imports
try:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    EMAIL_LIBS_AVAILABLE = True
except ImportError:
    EMAIL_LIBS_AVAILABLE = False
    aiosmtplib = None
    MIMEText = None
    MIMEMultipart = None

# MongoDB lazy init
_mongo_client = None
_db = None


def get_db():
    global _mongo_client, _db
    if _db is None and mongo_url:
        _mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        _db = _mongo_client[db_name]
    return _db


# ── Pydantic Model ────────────────────────────────────────────────────────────

class AlyahProLeadRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    target_city: str
    budget: str
    sector: str
    aliyah_date: str
    message: Optional[str] = None
    request_type: str = "alyah_pro"
    lang: Literal["fr", "en", "he"] = "fr"


# ── Email notification ────────────────────────────────────────────────────────

async def send_alyah_pro_notification(lead: AlyahProLeadRequest, lead_id: str):
    """Send email notification to IGV team when a new Alyah Pro lead arrives."""
    if not EMAIL_LIBS_AVAILABLE:
        logging.warning("[AlyahPro] Email libs not available, skipping notification")
        return
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logging.warning("[AlyahPro] SMTP not configured, skipping notification")
        return

    subject = f"[IGV Alyah Pro] {lead.first_name} {lead.last_name} — {lead.target_city}"

    body = f"""Nouvelle demande Alyah Pro reçue.

Prénom    : {lead.first_name}
Nom       : {lead.last_name}
Email     : {lead.email}
Téléphone : {lead.phone or '—'}
Ville cible : {lead.target_city}
Budget    : {lead.budget}
Secteur   : {lead.sector}
Date Alyah : {lead.aliyah_date}
Langue    : {lead.lang}

Message   :
{lead.message or '—'}

---
Lead ID   : {lead_id}
Source    : Formulaire /alyah-pro
"""

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_NOTIFY
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(msg)

        logging.info(f"[AlyahPro] Notification email sent for lead {lead_id}")
    except Exception as e:
        logging.error(f"[AlyahPro] Failed to send notification email: {e}")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/leads/alyah-pro")
async def create_alyah_pro_lead(
    lead: AlyahProLeadRequest,
    background_tasks: BackgroundTasks
):
    """
    Reçoit un formulaire de découverte Alyah Pro.
    Sauvegarde en MongoDB collection "leads" avec type "alyah_pro".
    Envoie un email de notification SMTP en arrière-plan.
    """
    db = get_db()

    # Prépare le document lead
    now = datetime.now(timezone.utc)
    lead_doc = {
        "type": "alyah_pro",
        "status": "new",
        "source": "alyah_pro_form",
        "request_type": "alyah_pro",
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "name": f"{lead.first_name} {lead.last_name}",
        "email": lead.email,
        "phone": lead.phone,
        "target_city": lead.target_city,
        "budget": lead.budget,
        "sector": lead.sector,
        "aliyah_date": lead.aliyah_date,
        "message": lead.message,
        "language": lead.lang,
        "created_at": now,
        "updated_at": now
    }

    lead_id = "alyah_pro_no_db"

    # Sauvegarde MongoDB (si disponible)
    if db is not None:
        try:
            result = await db["leads"].insert_one(lead_doc)
            lead_id = str(result.inserted_id)
            logging.info(f"[AlyahPro] Lead saved: {lead_id}")
        except Exception as e:
            logging.error(f"[AlyahPro] MongoDB insert failed: {e}")
            # On ne bloque pas la réponse si MongoDB échoue
    else:
        logging.warning("[AlyahPro] MongoDB not available, lead not persisted")

    # Email notification en arrière-plan
    background_tasks.add_task(send_alyah_pro_notification, lead, lead_id)

    return {"success": True, "lead_id": lead_id}
