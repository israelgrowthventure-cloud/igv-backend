"""
Script to initialize CMS page_content collection with default content.
This ensures the CMS Editor displays existing content from the website.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGODB_URI")

# Default content for all pages in all languages
PAGE_CONTENT = {
    "home": {
        "fr": {
            "hero_title": "Réussir Votre Expansion en Israël",
            "hero_subtitle": "Des startups aux grandes marques internationales",
            "hero_description": "Accompagnement stratégique et opérationnel pour les entreprises souhaitant s'implanter et se développer sur le marché israélien.",
            "cta_button": "Demander une Mini-Analyse",
            "services_title": "Nos Services",
            "about_preview": "Israel Growth Venture accompagne les entreprises dans leur expansion sur le marché israélien depuis Tel Aviv."
        },
        "en": {
            "hero_title": "Succeed in Your Expansion to Israel",
            "hero_subtitle": "From startups to major international brands",
            "hero_description": "Strategic and operational support for companies looking to establish and grow in the Israeli market.",
            "cta_button": "Request a Mini-Analysis",
            "services_title": "Our Services",
            "about_preview": "Israel Growth Venture supports companies in their expansion to the Israeli market from Tel Aviv."
        },
        "he": {
            "hero_title": "להצליח בהתרחבות שלכם לישראל",
            "hero_subtitle": "מסטארטאפים למותגים בינלאומיים גדולים",
            "hero_description": "ליווי אסטרטגי ותפעולי לחברות המעוניינות להתבסס ולצמוח בשוק הישראלי.",
            "cta_button": "בקש מיני-אנליזה",
            "services_title": "השירותים שלנו",
            "about_preview": "Israel Growth Venture מלווה חברות בהתרחבות שלהן לשוק הישראלי מתל אביב."
        }
    },
    "about": {
        "fr": {
            "title": "Qui Sommes-Nous",
            "intro": "Israel Growth Venture est une société de conseil spécialisée dans l'accompagnement des entreprises internationales souhaitant s'implanter en Israël.",
            "mission": "Notre mission est de faciliter l'entrée sur le marché israélien grâce à notre expertise locale et notre réseau de partenaires.",
            "team": "Notre équipe est composée d'experts en développement commercial, marketing et stratégie d'expansion."
        },
        "en": {
            "title": "Who We Are",
            "intro": "Israel Growth Venture is a consulting firm specializing in supporting international companies looking to establish themselves in Israel.",
            "mission": "Our mission is to facilitate entry into the Israeli market through our local expertise and partner network.",
            "team": "Our team is composed of experts in business development, marketing, and expansion strategy."
        },
        "he": {
            "title": "מי אנחנו",
            "intro": "Israel Growth Venture היא חברת ייעוץ המתמחה בליווי חברות בינלאומיות המעוניינות להתבסס בישראל.",
            "mission": "המשימה שלנו היא להקל על הכניסה לשוק הישראלי באמצעות המומחיות המקומית שלנו ורשת השותפים שלנו.",
            "team": "הצוות שלנו מורכב ממומחים בפיתוח עסקי, שיווק ואסטרטגיית התרחבות."
        }
    },
    "mini-analyse": {
        "fr": {
            "title": "Mini-Analyse Gratuite",
            "subtitle": "Évaluez votre potentiel sur le marché israélien",
            "form_intro": "Remplissez ce formulaire pour recevoir une analyse personnalisée de votre projet d'expansion en Israël."
        },
        "en": {
            "title": "Free Mini-Analysis",
            "subtitle": "Evaluate your potential in the Israeli market",
            "form_intro": "Fill out this form to receive a personalized analysis of your expansion project in Israel."
        },
        "he": {
            "title": "מיני-אנליזה חינמית",
            "subtitle": "העריכו את הפוטנציאל שלכם בשוק הישראלי",
            "form_intro": "מלאו טופס זה כדי לקבל ניתוח מותאם אישית של פרויקט ההתרחבות שלכם בישראל."
        }
    },
    "contact": {
        "fr": {
            "title": "Contactez-Nous",
            "subtitle": "Notre équipe est à votre disposition",
            "address": "Tel Aviv, Israël",
            "phone": "+972 XX XXX XXXX",
            "email": "contact@israelgrowthventure.com"
        },
        "en": {
            "title": "Contact Us",
            "subtitle": "Our team is at your disposal",
            "address": "Tel Aviv, Israel",
            "phone": "+972 XX XXX XXXX",
            "email": "contact@israelgrowthventure.com"
        },
        "he": {
            "title": "צור קשר",
            "subtitle": "הצוות שלנו לרשותכם",
            "address": "תל אביב, ישראל",
            "phone": "+972 XX XXX XXXX",
            "email": "contact@israelgrowthventure.com"
        }
    },
    "packs": {
        "fr": {
            "title": "Nos Packs",
            "subtitle": "Des solutions adaptées à vos besoins",
            "intro": "Découvrez nos différentes offres d'accompagnement pour votre expansion en Israël."
        },
        "en": {
            "title": "Our Packs",
            "subtitle": "Solutions tailored to your needs",
            "intro": "Discover our various support packages for your expansion in Israel."
        },
        "he": {
            "title": "החבילות שלנו",
            "subtitle": "פתרונות המותאמים לצרכים שלכם",
            "intro": "גלו את חבילות הליווי השונות שלנו להתרחבות שלכם בישראל."
        }
    },
    "future-commerce": {
        "fr": {
            "title": "Le Commerce de Demain",
            "subtitle": "Blog & FAQ",
            "description": "Découvrez les tendances du retail et les opportunités d'expansion en Israël",
            "cta_title": "Prêt à conquérir le marché israélien ?",
            "cta_description": "Obtenez une analyse gratuite de votre potentiel d'expansion",
            "cta_button": "Demander une Mini-Analyse"
        },
        "en": {
            "title": "The Commerce of Tomorrow",
            "subtitle": "Blog & FAQ",
            "description": "Discover retail trends and expansion opportunities in Israel",
            "cta_title": "Ready to conquer the Israeli market?",
            "cta_description": "Get a free analysis of your expansion potential",
            "cta_button": "Request a Mini-Analysis"
        },
        "he": {
            "title": "המסחר של המחר",
            "subtitle": "בלוג ושאלות נפוצות",
            "description": "גלו מגמות קמעונאות והזדמנויות התרחבות בישראל",
            "cta_title": "מוכנים לכבוש את השוק הישראלי?",
            "cta_description": "קבלו ניתוח חינמי של פוטנציאל ההתרחבות שלכם",
            "cta_button": "בקש מיני-אנליזה"
        }
    }
}


async def init_page_content():
    """Initialize or update page content in MongoDB"""
    if not MONGO_URL:
        print("❌ MONGO_URL not configured")
        return
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.get_default_database()
    
    now = datetime.now(timezone.utc)
    
    print("🚀 Initializing CMS page content...")
    
    for page_id, languages in PAGE_CONTENT.items():
        for lang, content in languages.items():
            # Check if exists
            existing = await db.page_content.find_one({
                "page": page_id,
                "language": lang
            })
            
            if existing:
                print(f"  ⏭️  {page_id}/{lang} already exists, skipping")
                continue
            
            doc = {
                "page": page_id,
                "language": lang,
                "content": content,
                "version": 1,
                "created_at": now,
                "updated_at": now,
                "created_by": "system"
            }
            
            await db.page_content.insert_one(doc)
            print(f"  ✅ Created {page_id}/{lang}")
    
    # Create index
    await db.page_content.create_index([("page", 1), ("language", 1)], unique=True)
    
    print("\n✅ CMS page content initialized successfully!")
    
    # Show stats
    count = await db.page_content.count_documents({})
    print(f"📊 Total page content documents: {count}")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(init_page_content())
