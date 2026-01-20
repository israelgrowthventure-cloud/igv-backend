"""
Email Templates Seed Script
Creates email templates in French, English, and Hebrew for the CRM
Run this script to populate the email_templates collection in MongoDB
"""

import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

# MongoDB connection
MONGODB_URI = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL') or 'mongodb://localhost:27017'
DB_NAME = os.getenv('DB_NAME') or 'igv_site'

# Email templates in all 3 languages
EMAIL_TEMPLATES = [
    {
        "name": "Confirmation de demande",
        "subject": {
            "fr": "Votre demande d'analyse IGV est enregistrée",
            "en": "Your IGV analysis request is saved",
            "he": "הבקשה שלכם לניתוח IGV נשמרה"
        },
        "body": {
            "fr": """Bonjour,

Capacité du jour atteinte.
Votre demande est enregistrée ✅

Marque: {{brand}}

Vous recevrez votre mini-analyse par email dès réouverture des créneaux (généralement sous 24–48h).

Merci de votre confiance,
L'équipe Israel Growth Venture

---
Référence: {{request_id}}""",
            "en": """Hello,

Daily capacity reached.
Your request is saved ✅

Brand: {{brand}}

You'll receive your mini-analysis by email as soon as capacity reopens (usually within 24–48 hours).

Thank you for your trust,
The Israel Growth Venture team

---
Reference: {{request_id}}""",
            "he": """שלום,

הגענו לקיבולת היומית.
הבקשה נשמרה ✅

מותג: {{brand}}

תקבלו את המיני-אנליזה במייל ברגע שהקיבולת תיפתח מחדש (בדרך כלל תוך 24–48 שעות).

תודה על האמון,
צוות Israel Growth Venture

---
אסמכתא: {{request_id}}"""
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
            "fr": """Bonjour,

Votre mini-analyse pour {{brand}} est maintenant prête !

{{analysis}}

Cordialement,
L'équipe Israel Growth Venture""",
            "en": """Hello,

Your mini-analysis for {{brand}} is now ready!

{{analysis}}

Best regards,
The Israel Growth Venture team""",
            "he": """שלום,

המיני-אנליזה שלך עבור {{brand}} מוכנה כעת!

{{analysis}}

בברכה,
צוות Israel Growth Venture"""
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
            "fr": """Bonjour,

Une nouvelle demande de contact expert a été reçue.

Marque: {{brand}}
Secteur: {{sector}}
Pays: {{country}}
Email: {{email}}

Un expert va bientôt prendre contact avec ce prospect.

Cordialement,
L'équipe Israel Growth Venture""",
            "en": """Hello,

A new expert contact request has been received.

Brand: {{brand}}
Sector: {{sector}}
Country: {{country}}
Email: {{email}}

An expert will soon contact this lead.

Best regards,
The Israel Growth Venture team""",
            "he": """שלום,

התקבלה בקשה חדשה ליצירת קשר עם מומחה.

מותג: {{brand}}
מגזר: {{sector}}
מדינה: {{country}}
מייל: {{email}}

מומחה יצור קשר עם הליד בהקדם.

בברכה,
צוות Israel Growth Venture"""
        },
        "category": "lead",
        "variables": ["brand", "sector", "country", "email"]
    },
    {
        "name": "Rappel de disponibilité",
        "subject": {
            "fr": "Rappel -slots disponibles pour {{brand}}",
            "en": "Reminder - slots available for {{brand}}",
            "he": "תזכורת - יחידות זמינות עבור {{brand}}"
        },
        "body": {
            "fr": """Bonjour {{name}},

Nous avons le plaisir de vous informer que des slots sont désormais disponibles pour votre analyse.

Marque: {{brand}}

Cliquez sur le lien ci-dessous pour réserver votre créneau :
{{link}}

À très bientôt,
L'équipe Israel Growth Venture""",
            "en": """Hello {{name}},

We are pleased to inform you that slots are now available for your analysis.

Brand: {{brand}}

Click the link below to book your slot:
{{link}}

See you soon,
The Israel Growth Venture team""",
            "he": """שלום {{name}},

אנו שמחים להודיע לכם שיחידות זמינות כעת עבור הניתוח שלכם.

מותג: {{brand}}

לחצו על הקישור למטה להזמנת המשבצת שלכם:
{{link}}

נתראה בקרוב,
צוות Israel Growth Venture"""
        },
        "category": "reminder",
        "variables": ["name", "brand", "link"]
    },
    {
        "name": "Confirmation de rendez-vous",
        "subject": {
            "fr": "Confirmation de votre rendez-vous - {{brand}}",
            "en": "Your appointment confirmation - {{brand}}",
            "he": "אישור הפגישה שלכם - {{brand}}"
        },
        "body": {
            "fr": """Bonjour {{name}},

Votre rendez-vous est confirmé !

Date: {{date}}
Heure: {{time}}
Marque: {{brand}}

Nous avons hâte de vous retrouver.

Cordialement,
L'équipe Israel Growth Venture""",
            "en": """Hello {{name}},

Your appointment is confirmed!

Date: {{date}}
Time: {{time}}
Brand: {{brand}}

We look forward to seeing you.

Best regards,
The Israel Growth Venture team""",
            "he": """שלום {{name}},

הפגישה שלכם אושרה!

תאריך: {{date}}
שעה: {{time}}
מותג: {{brand}}

אנחנו מצפים להיפגש.

בברכה,
צוות Israel Growth Venture"""
        },
        "category": "appointment",
        "variables": ["name", "date", "time", "brand"]
    }
]


async def seed_email_templates():
    """Create email templates in all languages"""
    print(f"Connecting to MongoDB: {MONGODB_URI}")
    
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    templates_collection = db["email_templates"]
    
    # Clear existing templates
    print("Clearing existing templates...")
    await templates_collection.delete_many({})
    
    created_count = 0
    
    for template_def in EMAIL_TEMPLATES:
        # Create a template for each language
        for lang in ["fr", "en", "he"]:
            template_doc = {
                "name": template_def["name"],
                "subject": template_def["subject"][lang],
                "body": template_def["body"][lang],
                "language": lang,
                "category": template_def["category"],
                "variables": template_def["variables"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = await templates_collection.insert_one(template_doc)
            print(f"  ✓ Created template: {template_def['name']} ({lang})")
            created_count += 1
    
    print(f"\n✅ Successfully created {created_count} email templates in {DB_NAME}")
    
    # List all templates
    print("\n📋 Created templates:")
    async for template in templates_collection.find({}):
        print(f"  - {template['name']} [{template['language']}]")
    
    client.close()
    return created_count


if __name__ == "__main__":
    print("=" * 60)
    print("Email Templates Seeding Script")
    print("=" * 60)
    asyncio.run(seed_email_templates())
