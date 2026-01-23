"""
Email Templates Default Data and Seed Endpoints
Contains default templates in FR, EN, HE for the CRM
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from datetime import datetime, timezone
import logging

from auth_middleware import get_current_user, require_role, get_db

router = APIRouter(prefix="/api/crm/emails")


# Default email templates in all 3 languages (4 templates × 3 languages = 12 documents)
DEFAULT_EMAIL_TEMPLATES = [
    {
        "name": "Confirmation de demande",
        "subject": {
            "fr": "Votre demande d'analyse IGV est enregistrée",
            "en": "Your IGV analysis request is saved",
            "he": "הבקשה שלכם לניתוח IGV נשמרה"
        },
        "body": {
            "fr": "Bonjour,\n\nCapacité du jour atteinte.\nVotre demande est enregistrée ✅\n\nMarque: {{brand}}\n\nVous recevrez votre mini-analyse par email dès réouverture des créneaux (généralement sous 24–48h).\n\nMerci de votre confiance,\nL'équipe Israel Growth Venture\n\n---\nRéférence: {{request_id}}",
            "en": "Hello,\n\nDaily capacity reached.\nYour request is saved ✅\n\nBrand: {{brand}}\n\nYou'll receive your mini-analysis by email as soon as capacity reopens (usually within 24–48 hours).\n\nThank you for your trust,\nThe Israel Growth Venture team\n\n---\nReference: {{request_id}}",
            "he": "שלום,\n\nהגענו לקיבולת היומית.\nהבקשה נשמרה ✅\n\nמותג: {{brand}}\n\nתקבלו את המיני-אנליזה במייל ברגע שהקיבולת תיפתח מחדש (בדרך כלל תוך 24–48 שעות).\n\nתודה על האמון,\nצוות Israel Growth Venture\n\n---\nאסמכתא: {{request_id}}"
        },
        "category": "notification",
        "variables": ["brand", "request_id"]
    },
    {
        "name": "Envoi Mini-Analyse",
        "subject": {
            "fr": "Votre Mini-Analyse pour {{brand}} - IGV",
            "en": "Your Mini-Analysis for {{brand}} - IGV",
            "he": "המיני-אנליזה שלך עבור {{brand}} - IGV"
        },
        "body": {
            "fr": "Bonjour,\n\nVotre mini-analyse pour {{brand}} est maintenant prête !\n\n{{analysis}}\n\nCordialement,\nL'équipe Israel Growth Venture",
            "en": "Hello,\n\nYour mini-analysis for {{brand}} is now ready!\n\n{{analysis}}\n\nBest regards,\nThe Israel Growth Venture team",
            "he": "שלום,\n\nהמיני-אנליזה שלך עבור {{brand}} מוכנה כעת!\n\n{{analysis}}\n\nבברכה,\nצוות Israel Growth Venture"
        },
        "category": "analysis",
        "variables": ["brand", "analysis"]
    },
    {
        "name": "Prise de contact expert",
        "subject": {
            "fr": "Demande de contact expert - {{brand}}",
            "en": "Expert contact request - {{brand}}",
            "he": "בקשת יצירת קשר עם מומחה - {{brand}}"
        },
        "body": {
            "fr": "Bonjour,\n\nUne nouvelle demande de contact expert a été reçue.\n\nMarque: {{brand}}\nSecteur: {{sector}}\nPays: {{country}}\nEmail: {{email}}\n\nUn expert va bientôt prendre contact avec ce prospect.\n\nCordialement,\nL'équipe Israel Growth Venture",
            "en": "Hello,\n\nA new expert contact request has been received.\n\nBrand: {{brand}}\nSector: {{sector}}\nCountry: {{country}}\nEmail: {{email}}\n\nAn expert will soon contact this lead.\n\nBest regards,\nThe Israel Growth Venture team",
            "he": "שלום,\n\nהתקבלה בקשה חדשה ליצירת קשר עם מומחה.\n\nמותג: {{brand}}\nמגזר: {{sector}}\nמדינה: {{country}}\nמייל: {{email}}\n\nמומחה יצור קשר עם הליד בהקדם.\n\nבברכה,\nצוות Israel Growth Venture"
        },
        "category": "lead",
        "variables": ["brand", "sector", "country", "email"]
    },
    {
        "name": "Rappel de disponibilité",
        "subject": {
            "fr": "Rappel - slots disponibles pour {{brand}}",
            "en": "Reminder - slots available for {{brand}}",
            "he": "תזכורת - יחידות זמינות עבור {{brand}}"
        },
        "body": {
            "fr": "Bonjour {{name}},\n\nNous avons le plaisir de vous informer que des slots sont désormais disponibles pour votre analyse.\n\nMarque: {{brand}}\n\nCliquez sur le lien ci-dessous pour réserver votre créneau :\n{{link}}\n\nÀ très bientôt,\nL'équipe Israel Growth Venture",
            "en": "Hello {{name}},\n\nWe are pleased to inform you that slots are now available for your analysis.\n\nBrand: {{brand}}\n\nClick the link below to book your slot:\n{{link}}\n\nSee you soon,\nThe Israel Growth Venture team",
            "he": "שלום {{name}},\n\nאנו שמחים להודיע לכם שיחידות זמינות כעת עבור הניתוח שלכם.\n\nמותג: {{brand}}\n\nלחצו על הקישור למטה להזמנת המשבצת שלכם:\n{{link}}\n\nנתראה בקרוב,\nצוות Israel Growth Venture"
        },
        "category": "reminder",
        "variables": ["name", "brand", "link"]
    }
]


@router.post("/templates/seed")
async def seed_email_templates(user: Dict = Depends(get_current_user)):
    """Seed default email templates (Admin only) - Creates templates if they don't exist"""
    await require_role(["admin"], user)
    
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    created_count = 0
    skipped_count = 0
    
    for template_def in DEFAULT_EMAIL_TEMPLATES:
        for lang in ["fr", "en", "he"]:
            # Check if template already exists
            existing = await current_db.email_templates.find_one({
                "name": template_def["name"],
                "language": lang
            })
            
            if existing:
                skipped_count += 1
                continue
            
            template_doc = {
                "name": template_def["name"],
                "subject": template_def["subject"][lang],
                "body": template_def["body"][lang],
                "language": lang,
                "category": template_def["category"],
                "variables": template_def["variables"],
                "created_by": "system",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            await current_db.email_templates.insert_one(template_doc)
            created_count += 1
            logging.info(f"✓ Created template: {template_def['name']} ({lang})")
    
    return {
        "success": True,
        "created": created_count,
        "skipped": skipped_count,
        "message": f"Seeded {created_count} templates, skipped {skipped_count} existing"
    }


@router.get("/templates/count")
async def get_email_templates_count(user: Dict = Depends(get_current_user)):
    """Get count of email templates by language"""
    current_db = get_db()
    if current_db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    counts = {}
    for lang in ["fr", "en", "he"]:
        counts[lang] = await current_db.email_templates.count_documents({"language": lang})
    
    total = await current_db.email_templates.count_documents({})
    
    return {
        "total": total,
        "by_language": counts,
        "expected_per_language": len(DEFAULT_EMAIL_TEMPLATES)
    }


async def auto_seed_templates_if_empty():
    """Called on startup to seed templates if collection is empty"""
    current_db = get_db()
    if current_db is None:
        logging.warning("Cannot auto-seed templates: database not configured")
        return
    
    count = await current_db.email_templates.count_documents({})
    if count == 0:
        logging.info("Email templates collection is empty, seeding defaults...")
        created = 0
        for template_def in DEFAULT_EMAIL_TEMPLATES:
            for lang in ["fr", "en", "he"]:
                template_doc = {
                    "name": template_def["name"],
                    "subject": template_def["subject"][lang],
                    "body": template_def["body"][lang],
                    "language": lang,
                    "category": template_def["category"],
                    "variables": template_def["variables"],
                    "created_by": "system",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                await current_db.email_templates.insert_one(template_doc)
                created += 1
        logging.info(f"✓ Auto-seeded {created} email templates")
    else:
        logging.info(f"Email templates already exist ({count} templates), skipping auto-seed")
