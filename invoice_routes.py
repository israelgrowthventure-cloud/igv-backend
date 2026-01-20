"""
Invoice Routes - Complete Invoicing System
Production-ready with PDF generation, email sending, VAT 18%
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import logging
import jwt
from bson import ObjectId
import hashlib
import base64

# PDF generation
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    logging.warning("reportlab not available - PDF generation will fail")
    PDF_AVAILABLE = False

# Email
try:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email import encoders
    EMAIL_AVAILABLE = True
except ImportError:
    logging.warning("Email libraries not available")
    EMAIL_AVAILABLE = False

from models.invoice_models import Invoice, InvoiceItem, InvoiceStatus, PaymentStatus, EmailEvent

router = APIRouter(prefix="/api/invoices")
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

# SMTP Config - Support both naming conventions
SMTP_SERVER = os.getenv('SMTP_SERVER') or os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USERNAME = os.getenv('SMTP_USERNAME') or os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SMTP_FROM_EMAIL = os.getenv('SMTP_FROM_EMAIL') or os.getenv('SMTP_FROM', 'israel.growth.venture@gmail.com')
SMTP_FROM_NAME = os.getenv('SMTP_FROM_NAME', 'Israel Growth Venture')

# Company info
COMPANY_NAME = "Israel Growth Venture"
COMPANY_ADDRESS = "Tel Aviv, Israel"
COMPANY_EMAIL = "israel.growth.venture@gmail.com"
COMPANY_WEBSITE = "israelgrowthventure.com"


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
        
        email = payload.get("email")
        
        # First try crm_users, then fallback to users collection
        user = await current_db.crm_users.find_one({"email": email})
        if not user:
            user = await current_db.users.find_one({"email": email})
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="User inactive")
        
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "name": user.get("name", email.split("@")[0]),
            "role": user.get("role", "admin")  # Default to admin for main users
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_role(user: Dict[str, Any], required_roles: List[str]):
    """Check if user has required role"""
    if user["role"] not in required_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


# ==========================================
# INVOICE NUMBER GENERATION
# ==========================================

async def generate_invoice_number() -> str:
    """Generate unique invoice number: INV-2025-00001"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    now = datetime.now(timezone.utc)
    year = now.year
    
    # Find last invoice number for this year
    last_invoice = await current_db.invoices.find_one(
        {"invoice_number": {"$regex": f"^INV-{year}-"}},
        sort=[("invoice_number", -1)]
    )
    
    if last_invoice:
        last_number = int(last_invoice["invoice_number"].split("-")[-1])
        next_number = last_number + 1
    else:
        next_number = 1
    
    return f"INV-{year}-{next_number:05d}"


# ==========================================
# PDF GENERATION
# ==========================================

def generate_invoice_pdf(invoice_data: Dict[str, Any], language: str = "fr") -> bytes:
    """Generate invoice PDF with IGV header and VAT 18%"""
    if not PDF_AVAILABLE:
        raise HTTPException(status_code=500, detail="PDF generation not available")
    
    from io import BytesIO
    buffer = BytesIO()
    
    # Create PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4b5563')
    )
    
    # Header: Company Info
    story.append(Paragraph(COMPANY_NAME, title_style))
    story.append(Paragraph(f"{COMPANY_ADDRESS} | {COMPANY_EMAIL} | {COMPANY_WEBSITE}", header_style))
    story.append(Spacer(1, 1*cm))
    
    # Invoice title
    invoice_title = {
        "fr": "FACTURE",
        "en": "INVOICE",
        "he": "חשבונית"
    }.get(language, "FACTURE")
    
    story.append(Paragraph(f"<b>{invoice_title} {invoice_data['invoice_number']}</b>", styles['Heading2']))
    story.append(Spacer(1, 0.5*cm))
    
    # Invoice details table
    invoice_info = [
        [{
            "fr": "Date:",
            "en": "Date:",
            "he": "תאריך:"
        }.get(language, "Date:"), datetime.fromisoformat(invoice_data['invoice_date'].replace('Z', '+00:00')).strftime("%d/%m/%Y")],
        [{
            "fr": "Échéance:",
            "en": "Due date:",
            "he": "תאריך יעד:"
        }.get(language, "Échéance:"), datetime.fromisoformat(invoice_data['due_date'].replace('Z', '+00:00')).strftime("%d/%m/%Y") if invoice_data.get('due_date') else "-"],
    ]
    
    info_table = Table(invoice_info, colWidths=[4*cm, 6*cm])
    info_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 1*cm))
    
    # Client info
    story.append(Paragraph({
        "fr": "<b>Facturé à:</b>",
        "en": "<b>Billed to:</b>",
        "he": "<b>לתשומת לב:</b>"
    }.get(language, "<b>Facturé à:</b>"), styles['Normal']))
    story.append(Paragraph(invoice_data['client_name'], styles['Normal']))
    if invoice_data.get('client_company'):
        story.append(Paragraph(invoice_data['client_company'], styles['Normal']))
    if invoice_data.get('client_email'):
        story.append(Paragraph(invoice_data['client_email'], styles['Normal']))
    story.append(Spacer(1, 1*cm))
    
    # Items table
    items_header = {
        "fr": ["Description", "Qté", "Prix unitaire", "Remise", "HT", "TVA (18%)", "Total TTC"],
        "en": ["Description", "Qty", "Unit price", "Discount", "Subtotal", "VAT (18%)", "Total"],
        "he": ["תיאור", "כמות", "מחיר יחידה", "הנחה", "סכום ביניים", "מע\"מ (18%)", "סה\"כ"]
    }.get(language, ["Description", "Qté", "Prix unitaire", "Remise", "HT", "TVA (18%)", "Total TTC"])
    
    items_data = [items_header]
    
    for item in invoice_data['items']:
        discount_text = f"{item.get('discount_percent', 0)}%" if item.get('discount_percent', 0) > 0 else "-"
        items_data.append([
            item['description'],
            str(item['quantity']),
            f"{item['unit_price']} {invoice_data['currency']}",
            discount_text,
            f"{item.get('subtotal', 0):.2f}",
            f"{item.get('tax_amount', 0):.2f}",
            f"{item.get('total', 0):.2f}"
        ])
    
    items_table = Table(items_data, colWidths=[6*cm, 1.5*cm, 2.5*cm, 1.5*cm, 2*cm, 2*cm, 2*cm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 1*cm))
    
    # Totals
    totals_label = {
        "fr": ["Sous-total HT:", "TVA (18%):", "Total TTC:"],
        "en": ["Subtotal:", "VAT (18%):", "Total:"],
        "he": ["סכום ביניים:", "מע\"מ (18%):", "סה\"כ:"]
    }.get(language, ["Sous-total HT:", "TVA (18%):", "Total TTC:"])
    
    totals_data = [
        [totals_label[0], f"{invoice_data['subtotal']:.2f} {invoice_data['currency']}"],
        [totals_label[1], f"{invoice_data['tax_amount']:.2f} {invoice_data['currency']}"],
        [totals_label[2], f"<b>{invoice_data['total_amount']:.2f} {invoice_data['currency']}</b>"],
    ]
    
    totals_table = Table(totals_data, colWidths=[12*cm, 4*cm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 12),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 1*cm))
    
    # Notes
    if invoice_data.get('notes'):
        story.append(Paragraph({
            "fr": "<b>Notes:</b>",
            "en": "<b>Notes:</b>",
            "he": "<b>הערות:</b>"
        }.get(language, "<b>Notes:</b>"), styles['Normal']))
        story.append(Paragraph(invoice_data['notes'], styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


# ==========================================
# EMAIL SENDING
# ==========================================

async def send_invoice_email(invoice_data: Dict[str, Any], pdf_bytes: bytes, language: str = "fr") -> Dict[str, Any]:
    """Send invoice by email with PDF attachment"""
    if not EMAIL_AVAILABLE or not SMTP_USERNAME or not SMTP_PASSWORD:
        logging.warning("Email not configured - skipping email send")
        return {"success": False, "error": "Email not configured"}
    
    try:
        # Create message
        message = MIMEMultipart()
        message['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        message['To'] = invoice_data['client_email']
        message['Cc'] = COMPANY_EMAIL
        message['Subject'] = {
            "fr": f"Facture {invoice_data['invoice_number']} - Israel Growth Venture",
            "en": f"Invoice {invoice_data['invoice_number']} - Israel Growth Venture",
            "he": f"חשבונית {invoice_data['invoice_number']} - Israel Growth Venture"
        }.get(language, f"Facture {invoice_data['invoice_number']}")
        
        # Email body
        body_template = {
            "fr": f"""Bonjour {invoice_data['client_name']},

Veuillez trouver ci-joint votre facture {invoice_data['invoice_number']}.

Montant total: {invoice_data['total_amount']:.2f} {invoice_data['currency']} TTC (TVA 18% incluse)

Merci de votre confiance.

Cordialement,
L'équipe Israel Growth Venture

{COMPANY_EMAIL}
{COMPANY_WEBSITE}
""",
            "en": f"""Hello {invoice_data['client_name']},

Please find attached your invoice {invoice_data['invoice_number']}.

Total amount: {invoice_data['total_amount']:.2f} {invoice_data['currency']} (VAT 18% included)

Thank you for your trust.

Best regards,
Israel Growth Venture Team

{COMPANY_EMAIL}
{COMPANY_WEBSITE}
""",
            "he": f"""שלום {invoice_data['client_name']},

בצרוף מצורפת חשבונית {invoice_data['invoice_number']}.

סכום כולל: {invoice_data['total_amount']:.2f} {invoice_data['currency']} (כולל מע"מ 18%)

תודה על אמונך.

בברכה,
צוות Israel Growth Venture

{COMPANY_EMAIL}
{COMPANY_WEBSITE}
"""
        }.get(language, body_template["fr"])
        
        message.attach(MIMEText(body_template, 'plain', 'utf-8'))
        
        # Attach PDF
        pdf_attachment = MIMEBase('application', 'pdf')
        pdf_attachment.set_payload(pdf_bytes)
        encoders.encode_base64(pdf_attachment)
        pdf_attachment.add_header(
            'Content-Disposition',
            f'attachment; filename=Invoice_{invoice_data["invoice_number"]}.pdf'
        )
        message.attach(pdf_attachment)
        
        # Send
        async with aiosmtplib.SMTP(hostname=SMTP_SERVER, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            await smtp.send_message(message)
        
        logging.info(f"Invoice email sent: {invoice_data['invoice_number']} to {invoice_data['client_email']}")
        
        return {"success": True, "sent_at": datetime.now(timezone.utc).isoformat()}
        
    except Exception as e:
        logging.error(f"Failed to send invoice email: {str(e)}")
        return {"success": False, "error": str(e)}


# ==========================================
# PYDANTIC MODELS
# ==========================================

class InvoiceCreate(BaseModel):
    client_email: EmailStr
    client_name: str
    client_company: Optional[str] = None
    client_address: Optional[str] = None
    client_city: Optional[str] = None
    client_country: Optional[str] = None
    
    contact_id: Optional[str] = None
    lead_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    
    items: List[Dict[str, Any]]
    
    due_days: int = 30
    currency: str = "USD"
    language: str = "fr"
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatus] = None
    paid_amount: Optional[float] = None
    payment_method: Optional[str] = None
    notes: Optional[str] = None


# ==========================================
# ROUTES
# ==========================================

@router.get("/")
async def list_invoices(
    user: Dict = Depends(get_current_user),
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """List all invoices"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    query = {}
    if status:
        query["status"] = status
    
    invoices = await current_db.invoices.find(query).skip(skip).limit(limit).sort("created_at", -1).to_list(limit)
    
    for invoice in invoices:
        invoice["_id"] = str(invoice["_id"])
    
    total = await current_db.invoices.count_documents(query)
    
    return {
        "invoices": invoices,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/")
async def create_invoice(
    invoice_create: InvoiceCreate,
    user: Dict = Depends(get_current_user)
):
    """Create new invoice"""
    await require_role(user, ["admin", "sales"])
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Generate invoice number
    invoice_number = await generate_invoice_number()
    
    # Calculate amounts
    subtotal = 0.0
    tax_amount = 0.0
    total_amount = 0.0
    
    processed_items = []
    for item_data in invoice_create.items:
        item = InvoiceItem(**item_data)
        processed_items.append(item.dict())
        subtotal += item.subtotal
        tax_amount += item.tax_amount
        total_amount += item.total
    
    # Create invoice
    invoice_data = {
        "invoice_number": invoice_number,
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=invoice_create.due_days),
        "client_email": invoice_create.client_email,
        "client_name": invoice_create.client_name,
        "client_company": invoice_create.client_company,
        "client_address": invoice_create.client_address,
        "client_city": invoice_create.client_city,
        "client_country": invoice_create.client_country,
        "contact_id": invoice_create.contact_id,
        "lead_id": invoice_create.lead_id,
        "opportunity_id": invoice_create.opportunity_id,
        "items": processed_items,
        "subtotal": round(subtotal, 2),
        "tax_rate": 18.0,
        "tax_amount": round(tax_amount, 2),
        "total_amount": round(total_amount, 2),
        "currency": invoice_create.currency,
        "status": InvoiceStatus.DRAFT,
        "language": invoice_create.language,
        "notes": invoice_create.notes,
        "paid_amount": 0.0,
        "email_sent": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    result = await current_db.invoices.insert_one(invoice_data)
    invoice_data["_id"] = str(result.inserted_id)
    
    # Create timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "invoice",
        "entity_id": str(result.inserted_id),
        "event_type": "created",
        "description": f"Invoice {invoice_number} created",
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    logging.info(f"Invoice created: {invoice_number}")
    
    return invoice_data


@router.get("/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user: Dict = Depends(get_current_user)
):
    """Get invoice by ID"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        invoice = await current_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    invoice["_id"] = str(invoice["_id"])
    return invoice


@router.post("/{invoice_id}/generate-pdf")
async def generate_pdf_for_invoice(
    invoice_id: str,
    user: Dict = Depends(get_current_user)
):
    """Generate PDF for invoice"""
    await require_role(user, ["admin", "sales"])
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        invoice = await current_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    pdf_bytes = generate_invoice_pdf(invoice, invoice.get("language", "fr"))
    
    # Store PDF (for now, return base64)
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    # Update invoice
    await current_db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {
            "$set": {
                "pdf_generated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "event_type": "pdf_generated",
        "description": f"PDF generated for invoice {invoice['invoice_number']}",
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "success": True,
        "pdf_base64": pdf_base64,
        "invoice_number": invoice["invoice_number"]
    }


@router.post("/{invoice_id}/send")
async def send_invoice(
    invoice_id: str,
    user: Dict = Depends(get_current_user)
):
    """Send invoice by email"""
    await require_role(user, ["admin", "sales"])
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        invoice = await current_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Generate PDF
    pdf_bytes = generate_invoice_pdf(invoice, invoice.get("language", "fr"))
    
    # Send email
    email_result = await send_invoice_email(invoice, pdf_bytes, invoice.get("language", "fr"))
    
    # Update invoice
    update_data = {
        "updated_at": datetime.now(timezone.utc)
    }
    
    if email_result["success"]:
        update_data["email_sent"] = True
        update_data["email_sent_at"] = datetime.fromisoformat(email_result["sent_at"])
        update_data["status"] = InvoiceStatus.SENT
        update_data["sent_at"] = datetime.fromisoformat(email_result["sent_at"])
    else:
        update_data["email_error"] = email_result.get("error")
    
    await current_db.invoices.update_one(
        {"_id": ObjectId(invoice_id)},
        {"$set": update_data}
    )
    
    # Log email event
    await current_db.email_events.insert_one({
        "email_type": "invoice",
        "to_email": invoice["client_email"],
        "cc": [COMPANY_EMAIL],
        "subject": f"Invoice {invoice['invoice_number']}",
        "language": invoice.get("language", "fr"),
        "status": "sent" if email_result["success"] else "failed",
        "error_message": email_result.get("error"),
        "invoice_id": invoice_id,
        "created_at": datetime.now(timezone.utc),
        "sent_at": datetime.fromisoformat(email_result["sent_at"]) if email_result["success"] else None
    })
    
    # Timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "event_type": "email_sent" if email_result["success"] else "email_failed",
        "description": f"Invoice {invoice['invoice_number']} {'sent' if email_result['success'] else 'failed to send'}",
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "success": email_result["success"],
        "message": "Invoice sent successfully" if email_result["success"] else "Failed to send invoice",
        "error": email_result.get("error")
    }


@router.patch("/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    invoice_update: InvoiceUpdate,
    user: Dict = Depends(get_current_user)
):
    """Update invoice"""
    await require_role(user, ["admin", "sales"])
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    update_data = invoice_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    # If marking as paid
    if update_data.get("status") == InvoiceStatus.PAID and update_data.get("paid_amount"):
        update_data["payment_date"] = datetime.now(timezone.utc)
    
    try:
        result = await current_db.invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {"$set": update_data}
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Timeline event
    await current_db.timeline_events.insert_one({
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "event_type": "updated",
        "description": f"Invoice updated: {', '.join(update_data.keys())}",
        "user_email": user["email"],
        "created_at": datetime.now(timezone.utc)
    })
    
    return {"success": True, "message": "Invoice updated"}


@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: str,
    user: Dict = Depends(get_current_user)
):
    """Delete invoice (soft delete - mark as CANCELED)"""
    await require_role(user, ["admin"])
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    try:
        result = await current_db.invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$set": {
                    "status": InvoiceStatus.CANCELED,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    return {"success": True, "message": "Invoice canceled"}


@router.get("/stats/overview")
async def get_invoice_stats(user: Dict = Depends(get_current_user)):
    """Get invoice statistics"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Aggregate stats
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$total_amount"}
            }
        }
    ]
    
    stats_by_status = {}
    async for stat in current_db.invoices.aggregate(pipeline):
        stats_by_status[stat["_id"]] = {
            "count": stat["count"],
            "total_amount": stat["total_amount"]
        }
    
    # Total invoiced
    total_invoiced = sum(s["total_amount"] for s in stats_by_status.values())
    
    # Total paid
    total_paid = stats_by_status.get(InvoiceStatus.PAID, {}).get("total_amount", 0)
    
    # Total outstanding
    total_outstanding = (
        stats_by_status.get(InvoiceStatus.SENT, {}).get("total_amount", 0) +
        stats_by_status.get(InvoiceStatus.OVERDUE, {}).get("total_amount", 0)
    )
    
    return {
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "by_status": stats_by_status
    }
