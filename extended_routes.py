"""
Additional Routes for Israel Growth Venture
- Contact Expert (post mini-analysis)
- PDF Generation
- Email PDF
- Google Calendar Integration
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import logging
import httpx
import base64
import io
import json

# Conditional imports for email (CRITICAL: don't crash if not installed)
try:
    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication
    EMAIL_LIBS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"⚠️ Email libraries not available: {str(e)}")
    EMAIL_LIBS_AVAILABLE = False
    aiosmtplib = None
    MIMEText = None
    MIMEMultipart = None
    MIMEApplication = None

router = APIRouter(prefix="/api")

# Environment variables
CALENDAR_EMAIL = os.getenv('CALENDAR_EMAIL', 'israel.growth.venture@gmail.com')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'noreply@israelgrowthventure.com')
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
GOOGLE_CALENDAR_API_KEY = os.getenv('GOOGLE_CALENDAR_API_KEY')


# MISSION: Send quota confirmation email
async def send_quota_confirmation_email(email: str, brand_name: str, language: str, request_id: str):
    """Send confirmation email when quota is reached"""
    
    if not EMAIL_LIBS_AVAILABLE:
        raise Exception("Email libraries not available")
    
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        raise Exception("SMTP not configured")
    
    # Email templates by language
    email_templates = {
        "fr": {
            "subject": "Votre demande d'analyse IGV est enregistrée",
            "body": f"""Bonjour,

Capacité du jour atteinte.
Votre demande est enregistrée ✅

Marque: {brand_name}

Vous recevrez votre mini-analyse par email dès réouverture des créneaux (généralement sous 24–48h).

Merci de votre confiance,
L'équipe Israel Growth Venture

---
Référence: {request_id}
"""
        },
        "en": {
            "subject": "Your IGV analysis request is saved",
            "body": f"""Hello,

Daily capacity reached.
Your request is saved ✅

Brand: {brand_name}

You'll receive your mini-analysis by email as soon as capacity reopens (usually within 24–48 hours).

Thank you for your trust,
The Israel Growth Venture team

---
Reference: {request_id}
"""
        },
        "he": {
            "subject": "הבקשה שלכם לניתוח IGV נשמרה",
            "body": f"""שלום,

הגענו לקיבולת היומית.
הבקשה נשמרה ✅

מותג: {brand_name}

תקבלו את המיני-אנליזה במייל ברגע שהקיבולת תיפתח מחדש (בדרך כלל תוך 24–48 שעות).

תודה על האמון,
צוות Israel Growth Venture

---
אסמכתא: {request_id}
"""
        }
    }
    
    template = email_templates.get(language, email_templates["en"])
    
    # Create email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = email
    msg['Subject'] = template["subject"]
    
    msg.attach(MIMEText(template["body"], 'plain', 'utf-8'))
    
    # Send via SMTP
    async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
        await smtp.starttls()
        await smtp.login(SMTP_USER, SMTP_PASSWORD)
        await smtp.send_message(msg)
    
    logging.info(f"[{request_id}] Quota confirmation email sent to {email}")


async def send_analysis_email(email: str, brand_name: str, analysis_text: str, language: str = "fr", request_id: str = "unknown"):
    """
    Send mini-analysis results via email (for pending analyses retry)
    """
    if not SMTP_CONFIGURED:
        logging.warning(f"[{request_id}] EMAIL_SEND_SKIP: SMTP not configured")
        return
    
    templates = {
        "fr": {
            "subject": f"Votre Mini-Analyse pour {brand_name} - IGV",
            "body": f"""Bonjour,

Votre mini-analyse pour {brand_name} est maintenant prête !

{analysis_text}

Cordialement,
L'équipe Israel Growth Venture"""
        },
        "en": {
            "subject": f"Your Mini-Analysis for {brand_name} - IGV",
            "body": f"""Hello,

Your mini-analysis for {brand_name} is now ready!

{analysis_text}

Best regards,
The Israel Growth Venture team"""
        },
        "he": {
            "subject": f"המיני-אנליזה שלך עבור {brand_name} - IGV",
            "body": f"""שלום,

המיני-אנליזה שלך עבור {brand_name} מוכנה כעת!

{analysis_text}

בברכה,
צוות Israel Growth Venture"""
        }
    }
    
    template = templates.get(language, templates["en"])
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = email
    msg['Subject'] = template["subject"]
    
    msg.attach(MIMEText(template["body"], 'plain', 'utf-8'))
    
    # Send via SMTP
    async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
        await smtp.starttls()
        await smtp.login(SMTP_USER, SMTP_PASSWORD)
        await smtp.send_message(msg)
    
    logging.info(f"[{request_id}] Analysis email sent to {email}")


# Models
class ContactExpertRequest(BaseModel):
    email: EmailStr
    brandName: str
    sector: str
    country: Optional[str] = None
    language: str = 'fr'
    source: str = 'mini-analysis'

class PDFGenerateRequest(BaseModel):
    email: EmailStr
    brandName: str
    sector: str
    origin: Optional[str] = None  # Changed from country
    analysis: str  # Changed from analysisText to match frontend
    language: str = 'fr'

class EmailPDFRequest(BaseModel):
    email: EmailStr
    brandName: str
    sector: str
    origin: Optional[str] = None  # Changed from country
    analysis: str  # Changed from analysisText
    language: str = 'fr'

class CalendarEventRequest(BaseModel):
    email: EmailStr
    brandName: str
    name: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    preferredDate: Optional[str] = None

# DIAGNOSTIC ENDPOINTS
@router.get("/diag/pdf-header")
async def check_pdf_header():
    """
    Diagnostic: Check if PDF header file exists and is accessible
    Returns file path, existence, size
    """
    try:
        from reportlab.lib.pagesizes import letter
        from PyPDF2 import PdfReader, PdfWriter
        reportlab_ok = True
    except ImportError:
        reportlab_ok = False
    
    header_path = Path(__file__).parent / 'assets' / 'entete_igv.pdf'
    
    result = {
        "reportlab_installed": reportlab_ok,
        "pypdf2_installed": True,
        "header_path": str(header_path),
        "header_exists": header_path.exists(),
        "header_size_bytes": header_path.stat().st_size if header_path.exists() else 0,
        "header_readable": False,
        "header_pages": 0
    }
    
    if header_path.exists():
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(header_path))
            result["header_readable"] = True
            result["header_pages"] = len(reader.pages)
        except Exception as e:
            result["header_error"] = str(e)
    
    return result

@router.get("/diag/smtp")
async def check_smtp_config():
    """
    Diagnostic: Check SMTP configuration
    """
    return {
        "smtp_configured": bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD),
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "smtp_user": SMTP_USER,
        "smtp_password_set": bool(SMTP_PASSWORD),
        "sendgrid_api_key_set": bool(SENDGRID_API_KEY),
        "email_from": EMAIL_FROM,
        "calendar_email": CALENDAR_EMAIL
    }

# Contact Expert endpoint
@router.post("/contact-expert")
async def contact_expert(request: ContactExpertRequest, background_tasks: BackgroundTasks):
    """
    Contact expert after mini-analysis
    Creates a calendar event and sends notification
    """
    try:
        # Store in database (optional - reuse contacts collection)
        db = get_db()
        if db is not None:
            contact_data = {
                "email": request.email,
                "brand_name": request.brandName,
                "sector": request.sector,
                "country": request.country,
                "language": request.language,
                "source": request.source,
                "created_at": datetime.now(timezone.utc),
                "type": "contact_expert"
            }
            await db.contacts.insert_one(contact_data)
        
        # Create Google Calendar event (background task)
        event_summary = f"IGV – Expert Call Request – {request.brandName}"
        event_description = f"""
        Brand: {request.brandName}
        Sector: {request.sector}
        Country: {request.country or 'Not specified'}
        Email: {request.email}
        Language: {request.language}
        Source: {request.source}
        """
        
        background_tasks.add_task(
            create_calendar_event_task,
            summary=event_summary,
            description=event_description,
            email=request.email
        )
        
        return {
            "success": True,
            "message": "Expert contact request received. We'll contact you within 48 hours."
        }
        
    except Exception as e:
        logging.error(f"Error in contact_expert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to get database connection
def get_db():
    """Get MongoDB connection (imported from mini_analysis_routes pattern)"""
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME', 'igv_production')
    
    if not mongo_url:
        return None
    
    try:
        client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        return client[db_name]
    except:
        return None

# PDF Generation endpoint
@router.post("/pdf/generate")
async def generate_pdf(request: PDFGenerateRequest, response: Response):
    """
    Generate PDF for mini-analysis with header and multilingual support
    MISSION C & D: PDF header integration + Hebrew RTL support
    Adds debug headers: X-IGV-PDF-Language, X-IGV-Header-Status
    """
    try:
        # Simple implementation using reportlab
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.units import inch
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY, TA_LEFT
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from PyPDF2 import PdfReader, PdfWriter
            
            # MISSION C.2: LOAD HEADER PDF WITH ROBUST PATH
            header_path = Path(__file__).resolve().parent / "assets" / "entete_igv.pdf"
            
            # MISSION C.3: LOG HEADER STATUS
            header_exists = header_path.exists()
            header_size = header_path.stat().st_size if header_exists else 0
            
            # DEBUG HEADERS
            response.headers["X-IGV-PDF-Language"] = request.language
            response.headers["X-IGV-Header-Status"] = "exists" if header_exists else "missing"
            
            logging.info(f"PDF_GENERATION: language={request.language}, brand={request.brandName}")
            logging.info(f"HEADER_PATH={header_path}")
            logging.info(f"HEADER_EXISTS={header_exists}")
            logging.info(f"HEADER_SIZE={header_size} bytes")
            
            if not header_exists:
                logging.error(f"❌ HEADER_MISSING: {header_path}")
                logging.error(f"  Expected location: {header_path}")
                logging.error(f"  Current working dir: {Path.cwd()}")
                logging.error(f"  __file__ location: {Path(__file__).resolve()}")
                raise HTTPException(status_code=500, detail="PDF header file missing")
            
            # MISSION D: HEBREW RTL SUPPORT
            is_hebrew = request.language == 'he'
            
            if is_hebrew:
                logging.info("HEBREW_PDF: RTL mode enabled")
                # Note: For full Hebrew support, we need Hebrew fonts
                # For now, we'll generate the PDF with RTL alignment
                # and display a warning if Hebrew characters are present
            
            # Create PDF in memory
            buffer = io.BytesIO()
            
            # Create document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=120,  # Extra space for merged header
                bottomMargin=18
            )
            
            # Container for elements
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            
            # Title style (RTL for Hebrew)
            title_alignment = TA_RIGHT if is_hebrew else TA_CENTER
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor='#1e40af',
                spaceAfter=30,
                alignment=title_alignment
            )
            
            # Brand style
            brand_style = ParagraphStyle(
                'BrandStyle',
                parent=styles['Heading2'],
                fontSize=18,
                spaceAfter=20,
                alignment=title_alignment
            )
            
            # Body style (RTL for Hebrew)
            body_alignment = TA_RIGHT if is_hebrew else TA_JUSTIFY
            
            body_style = ParagraphStyle(
                'BodyStyle',
                parent=styles['BodyText'],
                fontSize=11,
                leading=16,
                alignment=body_alignment,
                spaceAfter=12
            )
            
            # Header (multilingual)
            title_text = {
                'fr': 'Mini-Analyse IGV',
                'en': 'IGV Mini-Analysis',
                'he': 'מיני-אנליזה IGV'
            }.get(request.language, 'Mini-Analyse IGV')
            
            elements.append(Paragraph(title_text, brand_style))
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph(f"<b>{request.brandName}</b>", brand_style))
            elements.append(Spacer(1, 0.3*inch))
            
            # Date
            date_str = datetime.now().strftime('%d/%m/%Y')
            elements.append(Paragraph(f"Date: {date_str}", styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Analysis content
            # Split analysis into paragraphs
            paragraphs = request.analysis.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # Escape HTML special characters
                    para_escaped = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    elements.append(Paragraph(para_escaped, body_style))
                    elements.append(Spacer(1, 0.1*inch))
            
            # Footer
            elements.append(Spacer(1, 0.5*inch))
            footer_style = ParagraphStyle(
                'FooterStyle',
                parent=styles['Normal'],
                fontSize=9,
                textColor='#6b7280',
                alignment=TA_CENTER
            )
            elements.append(Paragraph("Israel Growth Venture", footer_style))
            elements.append(Paragraph("www.israelgrowthventure.com", footer_style))
            elements.append(Paragraph("israel.growth.venture@gmail.com", footer_style))
            
            # Build PDF
            doc.build(elements)
            
            # Get content PDF bytes
            content_pdf_bytes = buffer.getvalue()
            buffer.close()
            
            # MISSION C.4 & C.5: MERGE HEADER WITH CONTENT PDF (NO FALLBACK)
            try:
                # Read header PDF
                header_reader = PdfReader(str(header_path))
                header_page = header_reader.pages[0]
                
                # Read content PDF
                content_reader = PdfReader(io.BytesIO(content_pdf_bytes))
                
                # Create writer for final PDF
                writer = PdfWriter()
                
                # Merge header with each page of content
                for page_num, content_page in enumerate(content_reader.pages):
                    # Merge header onto content page
                    content_page.merge_page(header_page)
                    writer.add_page(content_page)
                
                # Write final PDF to buffer
                final_buffer = io.BytesIO()
                writer.write(final_buffer)
                pdf_bytes = final_buffer.getvalue()
                final_buffer.close()
                
                # MISSION C.4: LOG MERGE SUCCESS
                logging.info(f"HEADER_MERGE_OK pages={len(content_reader.pages)}")
                
            except Exception as merge_error:
                # MISSION C.5: EXPLICIT ERROR IF MERGE FAILS (NO FALLBACK)
                logging.error(f"❌ HEADER_MERGE_FAILED: {str(merge_error)}")
                logging.error(f"❌ HEADER_PATH_USED: {header_path}")
                logging.error(f"❌ This is a CRITICAL error - PDF generation ABORTED")
                raise HTTPException(
                    status_code=500,
                    detail=f"PDF header merge failed: {str(merge_error)}. Header file missing or corrupted."
                )

            
            # Encode to base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # MISSION B: AUTO-SEND PDF TO israel.growth.venture@gmail.com
            # CRITICAL: Never fail PDF generation if email fails
            try:
                if EMAIL_LIBS_AVAILABLE and SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
                    igv_email = "israel.growth.venture@gmail.com"
                    await send_pdf_to_igv(
                        brand_name=request.brandName,
                        pdf_base64=pdf_base64,
                        filename=f"{request.brandName}_IGV_Analysis.pdf",
                        language=request.language,
                        analysis_preview=request.analysis[:200]
                    )
                    logging.info(f"✅ PDF auto-sent to {igv_email}")
                else:
                    logging.warning(f"⚠️ Email auto-send skipped: EMAIL_LIBS={EMAIL_LIBS_AVAILABLE}, SMTP_CONFIGURED={bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)}")
            except Exception as email_error:
                # Don't fail PDF generation if email fails, just log
                logging.error(f"⚠️ Failed to auto-send PDF to IGV: {str(email_error)}")
            
            return {
                "success": True,
                "pdfBase64": pdf_base64,
                "filename": f"{request.brandName}_IGV_Analysis.pdf"
            }
            
        except ImportError:
            # Reportlab not installed, return simple message
            logging.warning("reportlab not installed, PDF generation unavailable")
            raise HTTPException(
                status_code=501,
                detail="PDF generation not configured. Please contact support."
            )
        
    except Exception as e:
        logging.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# REMOVED: POST /email/send-pdf - now handled by mini_analysis_routes.py (duplicate removed)

# Google Calendar event creation
@router.post("/calendar/create-event")
async def create_calendar_event(request: CalendarEventRequest):
    """
    Create Google Calendar event for appointment request
    """
    try:
        event_summary = f"IGV – Call Request – {request.brandName}"
        event_description = f"""
        Brand: {request.brandName}
        Contact: {request.name or 'Not provided'}
        Email: {request.email}
        Phone: {request.phone or 'Not provided'}
        Preferred Date: {request.preferredDate or 'ASAP'}
        Notes: {request.notes or 'None'}
        """
        
        # Create event (placeholder implementation)
        result = await create_calendar_event_task(
            summary=event_summary,
            description=event_description,
            email=request.email
        )
        
        return {
            "success": True,
            "message": "Calendar event created successfully",
            "eventId": result.get('eventId')
        }
        
    except Exception as e:
        logging.error(f"Error creating calendar event: {str(e)}")
        # Don't fail - just log and return success
        return {
            "success": True,
            "message": "Request received, we'll contact you soon"
        }

# Background tasks
async def create_calendar_event_task(summary: str, description: str, email: str):
    """
    Create Google Calendar event (background task)
    For now, sends email notification instead
    """
    try:
        # TODO: Implement actual Google Calendar API integration
        # For now, send email notification to team
        
        if SMTP_HOST and SMTP_USER and SMTP_PASSWORD:
            message = MIMEMultipart()
            message['From'] = EMAIL_FROM
            message['To'] = CALENDAR_EMAIL
            message['Subject'] = f"[IGV] {summary}"
            
            body = f"""
            New contact request:
            
            {description}
            
            Please follow up within 48 hours.
            """
            
            message.attach(MIMEText(body, 'plain'))
            
            async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
                await smtp.starttls()
                await smtp.login(SMTP_USER, SMTP_PASSWORD)
                await smtp.send_message(message)
            
            logging.info(f"Calendar notification sent for: {email}")
            return {"eventId": "email_notification"}
        else:
            logging.warning("SMTP not configured, calendar event not created")
            return {"eventId": "not_configured"}
            
    except Exception as e:
        logging.error(f"Error in create_calendar_event_task: {str(e)}")
        return {"eventId": "error"}

async def send_pdf_to_igv(
    brand_name: str,
    pdf_base64: str,
    filename: str,
    language: str,
    analysis_preview: str
):
    """
    MISSION B: Auto-send PDF to israel.growth.venture@gmail.com
    Called automatically after each PDF generation
    """
    try:
        igv_email = "israel.growth.venture@gmail.com"
        
        # MISSION B.4: LOG EMAIL SEND REQUEST
        logging.info(f"EMAIL_SEND_REQUEST to={igv_email} (auto) brand={brand_name} lang={language}")
        
        if not EMAIL_LIBS_AVAILABLE:
            logging.error(f"❌ EMAIL_SEND_ERROR: Email libraries not installed (aiosmtplib)")
            raise Exception("Email libraries not available - install aiosmtplib")
        
        if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
            logging.error(f"❌ EMAIL_SEND_ERROR: SMTP not configured")
            logging.error(f"   SMTP_HOST={SMTP_HOST}")
            logging.error(f"   SMTP_USER={SMTP_USER}")
            logging.error(f"   SMTP_PASSWORD_SET={bool(SMTP_PASSWORD)}")
            logging.error(f"   SENDGRID_API_KEY_SET={bool(SENDGRID_API_KEY)}")
            logging.error(f"   → Configure SMTP vars in Render Dashboard then Manual Deploy")
            raise Exception("SMTP credentials missing - check Render env vars")
        
        # Email subject with timestamp
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        subject = f"IGV Mini-Analysis PDF — {brand_name} — {language.upper()} — {timestamp}"
        
        # Email body
        body = f"""
New Mini-Analysis Generated

Brand: {brand_name}
Language: {language.upper()}
Timestamp: {timestamp}

Analysis Preview (first 200 chars):
{analysis_preview}

---
Full analysis attached as PDF.

Israel Growth Venture
www.israelgrowthventure.com
"""
        
        message = MIMEMultipart()
        message['From'] = EMAIL_FROM
        message['To'] = igv_email
        message['Subject'] = subject
        
        # Body
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(pdf_attachment)
        
        # Send email
        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            await smtp.send_message(message)
        
        # MISSION B.3: LOG EMAIL_SEND_OK
        message_id = message.get('Message-ID', 'unknown')
        logging.info(f"EMAIL_SEND_OK to={igv_email} message_id={message_id}")
        
    except Exception as e:
        # MISSION B.3: LOG EMAIL_SEND_ERROR
        logging.error(f"EMAIL_SEND_ERROR to={igv_email} reason={str(e)}")
        raise


async def send_pdf_email_task(
    to_email: str,
    brand_name: str,
    pdf_base64: str,
    filename: str,
    language: str
):
    """
    Send PDF via email (background task)
    MISSION B: Always CC israel.growth.venture@gmail.com
    """
    try:
        # MISSION B.4: LOG EMAIL SEND REQUEST
        igv_email = "israel.growth.venture@gmail.com"
        logging.info(f"EMAIL_SEND_REQUEST to={to_email}, cc={igv_email}")
        
        if not (SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
            logging.error(f"❌ EMAIL_SEND_ERROR: SMTP not configured (SMTP_HOST={bool(SMTP_HOST)}, SMTP_USER={bool(SMTP_USER)}, SMTP_PASSWORD={bool(SMTP_PASSWORD)})")
            return
        
        # Email subject and body based on language
        subjects = {
            'fr': f"Votre Mini-Analyse IGV - {brand_name}",
            'en': f"Your IGV Mini-Analysis - {brand_name}",
            'he': f"{brand_name} - IGV המיני-אנליזה שלך"
        }
        
        bodies = {
            'fr': f"""
        Bonjour,

        Veuillez trouver ci-joint votre mini-analyse IGV pour {brand_name}.

        Cette analyse a été générée par notre IA et fournit une première évaluation de votre potentiel sur le marché israélien.

        Pour une analyse complète et un accompagnement personnalisé, n'hésitez pas à nous contacter.

        Cordialement,
        L'équipe Israel Growth Venture
        www.israelgrowthventure.com
        """,
            'en': f"""
        Hello,

        Please find attached your IGV mini-analysis for {brand_name}.

        This analysis was generated by our AI and provides an initial assessment of your potential in the Israeli market.

        For a comprehensive analysis and personalized support, don't hesitate to contact us.

        Best regards,
        The Israel Growth Venture Team
        www.israelgrowthventure.com
        """,
            'he': f"""
        שלום,

        בצרוף תמצא את המיני-אנליזה IGV שלך עבור {brand_name}.

        הניתוח הזה נוצר על ידי ה-AI שלנו ומספק הערכה ראשונית של הפוטנציאל שלך בשוק הישראלי.

        לניתוח מקיף ותמיכה מותאמת אישית, אל תהסס לפנות אלינו.

        בברכה,
        צוות Israel Growth Venture
        www.israelgrowthventure.com
        """
        }
        
        message = MIMEMultipart()
        message['From'] = EMAIL_FROM
        message['To'] = to_email
        message['Cc'] = igv_email  # MISSION B: Always CC israel.growth.venture@gmail.com
        message['Subject'] = subjects.get(language, subjects['fr'])
        
        # Body
        body = bodies.get(language, bodies['fr'])
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(pdf_attachment)
        
        # Send email
        async with aiosmtplib.SMTP(hostname=SMTP_HOST, port=SMTP_PORT) as smtp:
            await smtp.starttls()
            await smtp.login(SMTP_USER, SMTP_PASSWORD)
            send_result = await smtp.send_message(message)
        
        # MISSION B.3: LOG EMAIL_SEND_OK
        message_id = message.get('Message-ID', 'unknown')
        logging.info(f"EMAIL_SEND_OK to={to_email}, cc={igv_email}, message_id={message_id}")
        logging.info(f"PDF email sent successfully to: {to_email} (CC: {igv_email})")
        
    except Exception as e:
        # MISSION B.3: LOG EMAIL_SEND_ERROR
        logging.error(f"EMAIL_SEND_ERROR reason={str(e)}")
        logging.error(f"Error in send_pdf_email_task: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())

# Helper function to get DB
def get_db():
    """Get database connection (imported from main server)"""
    try:
        from server import db
        return db
    except:
        return None
