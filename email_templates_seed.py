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
# Names must match existing FR templates in database
DEFAULT_EMAIL_TEMPLATES = [
    # Template 1: Premier contact - Demande d'information
    {
        "name": {
            "fr": "Premier contact - Demande d'information",
            "en": "First Contact - Information Request",
            "he": "יצירת קשר ראשונה - בקשת מידע"
        },
        "subject": {
            "fr": "Votre projet d'expansion en Israël - Israel Growth Venture",
            "en": "Your expansion project in Israel - Israel Growth Venture",
            "he": "פרויקט ההתרחבות שלכם בישראל - Israel Growth Venture"
        },
        "body": {
            "fr": "Bonjour {{name}},\n\nMerci pour votre intérêt pour le marché israélien !\n\nNous avons bien reçu votre demande concernant {{brand}}.\n\nUn expert de notre équipe vous contactera dans les 24h pour discuter de votre projet d'expansion.\n\nCordialement,\nL'équipe Israel Growth Venture",
            "en": "Hello {{name}},\n\nThank you for your interest in the Israeli market!\n\nWe have received your inquiry regarding {{brand}}.\n\nAn expert from our team will contact you within 24 hours to discuss your expansion project.\n\nBest regards,\nThe Israel Growth Venture team",
            "he": "שלום {{name}},\n\nתודה על ההתעניינות שלכם בשוק הישראלי!\n\nקיבלנו את הפנייה שלכם בנוגע ל-{{brand}}.\n\nמומחה מהצוות שלנו ייצור איתכם קשר תוך 24 שעות לדון בפרויקט ההתרחבות.\n\nבברכה,\nצוות Israel Growth Venture"
        },
        "category": "contact",
        "variables": ["name", "brand"]
    },
    # Template 2: Suivi après analyse
    {
        "name": {
            "fr": "Suivi après analyse",
            "en": "Analysis Follow-up",
            "he": "מעקב לאחר ניתוח"
        },
        "subject": {
            "fr": "Votre mini-analyse IGV est prête",
            "en": "Your IGV mini-analysis is ready",
            "he": "המיני-אנליזה שלכם מ-IGV מוכנה"
        },
        "body": {
            "fr": "Bonjour {{name}},\n\nVotre mini-analyse pour {{brand}} est maintenant disponible !\n\n{{analysis_summary}}\n\nPour recevoir l'analyse complète et discuter des opportunités, n'hésitez pas à prendre rendez-vous avec l'un de nos experts.\n\nCordialement,\nL'équipe Israel Growth Venture",
            "en": "Hello {{name}},\n\nYour mini-analysis for {{brand}} is now available!\n\n{{analysis_summary}}\n\nTo receive the full analysis and discuss opportunities, feel free to schedule a meeting with one of our experts.\n\nBest regards,\nThe Israel Growth Venture team",
            "he": "שלום {{name}},\n\nהמיני-אנליזה שלכם עבור {{brand}} זמינה כעת!\n\n{{analysis_summary}}\n\nכדי לקבל את הניתוח המלא ולדון בהזדמנויות, מוזמנים לקבוע פגישה עם אחד המומחים שלנו.\n\nבברכה,\nצוות Israel Growth Venture"
        },
        "category": "analysis",
        "variables": ["name", "brand", "analysis_summary"]
    },
    # Template 3: Relance prospect
    {
        "name": {
            "fr": "Relance prospect",
            "en": "Lead Follow-up",
            "he": "מעקב ליד"
        },
        "subject": {
            "fr": "Suite à notre échange - Israel Growth Venture",
            "en": "Following our conversation - Israel Growth Venture",
            "he": "בהמשך לשיחתנו - Israel Growth Venture"
        },
        "body": {
            "fr": "Bonjour {{name}},\n\nJe me permets de vous recontacter suite à notre dernier échange concernant {{brand}}.\n\nAvez-vous eu le temps d'examiner notre proposition ? Je reste à votre disposition pour répondre à vos questions.\n\nCordialement,\n{{sender_name}}\nIsrael Growth Venture",
            "en": "Hello {{name}},\n\nI'm following up on our last conversation regarding {{brand}}.\n\nHave you had time to review our proposal? I remain at your disposal to answer any questions.\n\nBest regards,\n{{sender_name}}\nIsrael Growth Venture",
            "he": "שלום {{name}},\n\nאני חוזר אליכם בהמשך לשיחתנו האחרונה בנוגע ל-{{brand}}.\n\nהאם הספקתם לבחון את ההצעה שלנו? אני עומד לרשותכם לכל שאלה.\n\nבברכה,\n{{sender_name}}\nIsrael Growth Venture"
        },
        "category": "followup",
        "variables": ["name", "brand", "sender_name"]
    },
    # Template 4: Proposition de rendez-vous
    {
        "name": {
            "fr": "Proposition de rendez-vous",
            "en": "Meeting Request",
            "he": "הצעה לפגישה"
        },
        "subject": {
            "fr": "Planifions un rendez-vous - Israel Growth Venture",
            "en": "Let's schedule a meeting - Israel Growth Venture",
            "he": "בואו נקבע פגישה - Israel Growth Venture"
        },
        "body": {
            "fr": "Bonjour {{name}},\n\nSuite à votre intérêt pour le marché israélien, je vous propose d'organiser un appel pour discuter plus en détail de votre projet {{brand}}.\n\nVoici mes disponibilités :\n- {{slot1}}\n- {{slot2}}\n- {{slot3}}\n\nN'hésitez pas à me proposer un créneau qui vous convient.\n\nCordialement,\n{{sender_name}}\nIsrael Growth Venture",
            "en": "Hello {{name}},\n\nFollowing your interest in the Israeli market, I would like to propose a call to discuss your {{brand}} project in more detail.\n\nHere are my availabilities:\n- {{slot1}}\n- {{slot2}}\n- {{slot3}}\n\nFeel free to suggest a time that works for you.\n\nBest regards,\n{{sender_name}}\nIsrael Growth Venture",
            "he": "שלום {{name}},\n\nבעקבות ההתעניינות שלכם בשוק הישראלי, אשמח להציע שיחה לדון בפרויקט {{brand}} שלכם לעומק.\n\nהנה הזמינות שלי:\n- {{slot1}}\n- {{slot2}}\n- {{slot3}}\n\nמוזמנים להציע זמן שמתאים לכם.\n\nבברכה,\n{{sender_name}}\nIsrael Growth Venture"
        },
        "category": "meeting",
        "variables": ["name", "brand", "sender_name", "slot1", "slot2", "slot3"]
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
            template_name = template_def["name"][lang]
            
            # Check if template already exists by name and language
            existing = await current_db.email_templates.find_one({
                "name": template_name,
                "language": lang
            })
            
            if existing:
                skipped_count += 1
                continue
            
            template_doc = {
                "name": template_name,
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
            logging.info(f"✓ Created template: {template_name} ({lang})")
    
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
    """Called on startup to seed missing templates (for each language)"""
    current_db = get_db()
    if current_db is None:
        logging.warning("Cannot auto-seed templates: database not configured")
        return
    
    created = 0
    skipped = 0
    
    for template_def in DEFAULT_EMAIL_TEMPLATES:
        for lang in ["fr", "en", "he"]:
            template_name = template_def["name"][lang]
            
            # Check if this specific template+language combo exists
            existing = await current_db.email_templates.find_one({
                "name": template_name,
                "language": lang
            })
            
            if existing:
                skipped += 1
                continue
            
            template_doc = {
                "name": template_name,
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
            logging.info(f"✓ Created template: {template_name} ({lang})")
    
    if created > 0:
        logging.info(f"✓ Auto-seeded {created} email templates (skipped {skipped} existing)")
    else:
        logging.info(f"All {skipped} email templates already exist")
