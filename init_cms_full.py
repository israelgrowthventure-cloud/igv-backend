#!/usr/bin/env python3
"""
IGV FULL CMS INITIALIZATION SCRIPT
Définit et injecte le contenu initial pour TOUTES les pages du site.
Langues: FR / EN / HE
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv('MONGODB_URL')
if not MONGODB_URL:
    raise Exception("❌ MONGODB_URL manquant dans .env")

client = AsyncIOMotorClient(MONGODB_URL)
db = client.igv_crm

# 📜 DÉFINITION EXHAUSTIVE DES PAGES
# Structure basée sur les routes React existantes
PAGES_CONTENT = {
    # 1. PAGE D'ACCUEIL
    'home': {
        'fr': {'title': 'Accueil', 'content': '<div class="hero"><h1>Bienvenue chez Israel Growth Venture</h1><p>Votre partenaire stratégique en Israël.</p></div>'},
        'en': {'title': 'Home', 'content': '<div class="hero"><h1>Welcome to Israel Growth Venture</h1><p>Your strategic partner in Israel.</p></div>'},
        'he': {'title': 'בית', 'content': '<div class="hero" dir="rtl"><h1>ברוכים הבאים ל-Israel Growth Venture</h1><p>השותף האסטרטגי שלכם בישראל.</p></div>'}
    },
    
    # 2. MINI ANALYSE (Service AI)
    'mini-analyse': {
        'fr': {'title': 'Mini-Analyse', 'content': '<div class="analysis"><h1>Obtenez votre diagnostic gratuit</h1><p>Analyse IA de votre potentiel en 30 secondes.</p></div>'},
        'en': {'title': 'Free Analysis', 'content': '<div class="analysis"><h1>Get your free assessment</h1><p>AI analysis of your potential in 30 seconds.</p></div>'},
        'he': {'title': 'ניתוח חינם', 'content': '<div class="analysis" dir="rtl"><h1>קבלו הערכה חינם</h1><p>ניתוח AI של הפוטנציאל שלכם תוך 30 שניות.</p></div>'}
    },

    # 3. À PROPOS
    'about': {
        'fr': {'title': 'À Propos', 'content': '<div class="about"><h1>Notre Histoire</h1><p>Experts en implantation depuis 10 ans.</p></div>'},
        'en': {'title': 'About Us', 'content': '<div class="about"><h1>Our Story</h1><p>Market entry experts for 10 years.</p></div>'},
        'he': {'title': 'אודות', 'content': '<div class="about" dir="rtl"><h1>הסיפור שלנו</h1><p>מומחים בכניסה לשוק מזה 10 שנים.</p></div>'}
    },

    # 4. PACKS (Service Offres)
    'packs': {
        'fr': {'title': 'Nos Offres', 'content': '<div class="packs"><h1>Solutions Adaptées</h1><p>Diagnostic, Succursales, Franchise.</p></div>'},
        'en': {'title': 'Our Offers', 'content': '<div class="packs"><h1>Tailored Solutions</h1><p>Diagnostic, Branches, Franchise.</p></div>'},
        'he': {'title': 'החבילות שלנו', 'content': '<div class="packs" dir="rtl"><h1>פתרונות מותאמים</h1><p>אבחון, סניפים, זכיינות.</p></div>'}
    },

    # 5. FUTURE COMMERCE (Devenu BLOG)
    'future-commerce': {
        'fr': {'title': 'Le Blog IGV', 'content': '<div class="blog"><h1>Actualités & Tendances</h1><p>Découvrez les dernières innovations du retail en Israël.</p></div>'},
        'en': {'title': 'IGV Blog', 'content': '<div class="blog"><h1>News & Trends</h1><p>Discover the latest retail innovations in Israel.</p></div>'},
        'he': {'title': 'הבלוג שלנו', 'content': '<div class="blog" dir="rtl"><h1>חדשות ומגמות</h1><p>גלו את החידושים האחרונים בקמעונאות בישראל.</p></div>'}
    },


    # 6. CONTACT
    'contact': {
        'fr': {'title': 'Contact', 'content': '<div class="contact"><h1>Discutons de votre projet</h1><p>Nos experts sont à votre disposition.</p></div>'},
        'en': {'title': 'Contact', 'content': '<div class="contact"><h1>Let\'s discuss your project</h1><p>Our experts are at your disposal.</p></div>'},
        'he': {'title': 'צור קשר', 'content': '<div class="contact" dir="rtl"><h1>בואו נדבר על הפרויקט שלכם</h1><p>המומחים שלנו לרשותכם.</p></div>'}
    },

    # 7. LEGAL (CGU)
    'terms': {
        'fr': {'title': 'CGU', 'content': '<div class="legal"><h1>Conditions Générales d\'Utilisation</h1><p>Mises à jour le 01/01/2025.</p></div>'},
        'en': {'title': 'Terms', 'content': '<div class="legal"><h1>Terms of Service</h1><p>Updated 01/01/2025.</p></div>'},
        'he': {'title': 'תנאי שימוש', 'content': '<div class="legal" dir="rtl"><h1>תנאי שימוש</h1><p>עודכן ב-01/01/2025.</p></div>'}
    },

    # 8. PRIVACY (Confidentialité)
    'privacy': {
        'fr': {'title': 'Confidentialité', 'content': '<div class="legal"><h1>Politique de Confidentialité</h1><p>Protection de vos données RGPD.</p></div>'},
        'en': {'title': 'Privacy', 'content': '<div class="legal"><h1>Privacy Policy</h1><p>GDPR Data Protection.</p></div>'},
        'he': {'title': 'פרטיות', 'content': '<div class="legal" dir="rtl"><h1>מדיניות פרטיות</h1><p>הגנה על נתונים.</p></div>'}
    },

    # 9. COOKIES
    'cookies': {
        'fr': {'title': 'Cookies', 'content': '<div class="legal"><h1>Gestion des Cookies</h1><p>Préférences de navigation.</p></div>'},
        'en': {'title': 'Cookies', 'content': '<div class="legal"><h1>Cookie Policy</h1><p>Browsing preferences.</p></div>'},
        'he': {'title': 'עוגיות', 'content': '<div class="legal" dir="rtl"><h1>מדיניות עוגיות</h1><p>העדפות גלישה.</p></div>'}
    },

    # 10. DEMANDE RAPPEL (Service Lead)
    'demande-rappel': {
        'fr': {'title': 'Rappel', 'content': '<div class="lead"><h1>Être Rapelé</h1><p>Laissez votre numéro, on vous rappelle.</p></div>'},
        'en': {'title': 'Callback', 'content': '<div class="lead"><h1>Request Callback</h1><p>Leave your number, we\'ll call you back.</p></div>'},
        'he': {'title': 'בקשת שיחה', 'content': '<div class="lead" dir="rtl"><h1>בקשו שיחה חוזרת</h1><p>השאירו מספר, נחזור אליכם.</p></div>'}
    },

    # 11. CONTACT EXPERT (Service Consulting)
    'contact-expert': {
        'fr': {'title': 'Expert', 'content': '<div class="expert"><h1>Parler à un Expert</h1><p>Rendez-vous qualifié.</p></div>'},
        'en': {'title': 'Expert', 'content': '<div class="expert"><h1>Talk to an Expert</h1><p>Qualified meeting.</p></div>'},
        'he': {'title': 'מומחה', 'content': '<div class="expert" dir="rtl"><h1>דברו עם מומחה</h1><p>פגישה מוסמכת.</p></div>'}
    },

    # 12. APPOINTMENT (Service Calendly)
    'appointment': {
        'fr': {'title': 'Rendez-vous', 'content': '<div class="appointment"><h1>Prendre Rendez-vous</h1><p>Choisissez votre créneau.</p></div>'},
        'en': {'title': 'Appointment', 'content': '<div class="appointment"><h1>Book Appointment</h1><p>Choose your slot.</p></div>'},
        'he': {'title': 'פגישה', 'content': '<div class="appointment" dir="rtl"><h1>קבע פגישה</h1><p>בחר את המשבצת שלך.</p></div>'}
    }
}

async def init_full_cms():
    print(f"🚀 Démarrage initialisation CMS GLOBAL ({len(PAGES_CONTENT)} pages)...")
    
    count = 0
    updated = 0
    
    for page_key, langs in PAGES_CONTENT.items():
        for lang, data in langs.items():
            # Structure standardisée CMS
            doc = {
                "page": page_key,
                "language": lang,
                "content": {
                    "main": {
                        "html": data['content'],
                        "title": data['title']
                    },
                    "seo": {
                        "title": f"{data['title']} | IGV",
                        "description": f"Page {data['title']} Israel Growth Venture"
                    }
                },
                "version": 1,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Upsert (Insérer OU METTRE À JOUR)
            # Modifié pour forcer la mise à jour des contenus
            result = await db.page_content.update_one(
                {"page": page_key, "language": lang},
                {"$set": doc},  # FORCE UPDATE
                upsert=True
            )
            
            if result.upserted_id:
                print(f"✅ Créé: {page_key} ({lang})")
                count += 1
            elif result.modified_count > 0:
                print(f"✏️  Mis à jour: {page_key} ({lang})")
                updated += 1
            else:
                print(f"ℹ️  Identique: {page_key} ({lang})")

                
    print(f"\nRÉSULTAT INITIALISATION:")
    print(f"✨ {count} nouvelles pages créées")
    print(f"🔄 {updated} pages existantes préservées")
    print(f"Total pages gérées: {len(PAGES_CONTENT)}")
    
    # Validation
    pages = await db.page_content.distinct("page")
    print(f"\n📋 Pages disponibles dans MongoDB: {pages}")

if __name__ == "__main__":
    asyncio.run(init_full_cms())
