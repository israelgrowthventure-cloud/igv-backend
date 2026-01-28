# Blog Articles Routes
# CRUD operations for blog articles with admin authentication

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import os
import uuid
from bson import ObjectId

# Import auth middleware
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth_middleware import get_current_user, get_db

# Create router
router = APIRouter(prefix="/api/blog", tags=["Blog"])


# ==========================================
# MODELS
# ==========================================

class ArticleCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = None  # Auto-generated if not provided
    excerpt: str = Field(..., min_length=1, max_length=500)
    content: str  # HTML content
    category: str = Field(default="General")
    image_url: Optional[str] = None
    language: str = Field(default="fr")
    published: bool = Field(default=False)
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    translate_en: bool = Field(default=False)
    translate_he: bool = Field(default=False)


class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    language: Optional[str] = None
    published: Optional[bool] = None
    tags: Optional[List[str]] = None
    author: Optional[str] = None


# ==========================================
# SIMPLE TRANSLATION DICTIONARY
# ==========================================
TRANSLATIONS_FR_EN = {
    "L'IA": "AI",
    "intelligence artificielle": "artificial intelligence",
    "retail": "retail",
    "israélien": "Israeli",
    "Israël": "Israel",
    "centre commercial": "shopping center",
    "centres commerciaux": "shopping centers",
    "Tel Aviv": "Tel Aviv",
    "experience client": "customer experience",
    "franchise": "franchise",
    "marché": "market",
    "entreprise": "business",
    "entreprises": "businesses",
    "Comment": "How",
    "Pourquoi": "Why",
    "partenaire": "partner",
    "partenaires": "partners",
    "accompagne": "supports",
    "étude de marché": "market research",
    "négociation": "negotiation",
    "bail": "lease",
    "baux": "leases",
    "lancement": "launch",
    "mois": "months",
    "ans": "years",
    "secteur": "sector",
    "restauration": "food service",
    "mode": "fashion",
    "cosmétiques": "cosmetics",
    "local": "local",
    "locaux": "local",
}

TRANSLATIONS_FR_HE = {
    "L'IA": "בינה מלאכותית",
    "intelligence artificielle": "בינה מלאכותית",
    "retail": "קמעונאות",
    "israélien": "ישראלי",
    "Israël": "ישראל",
    "centre commercial": "מרכז קניות",
    "centres commerciaux": "מרכזי קניות",
    "Tel Aviv": "תל אביב",
    "experience client": "חוויית לקוח",
    "franchise": "זיכיון",
    "marché": "שוק",
    "entreprise": "עסק",
    "entreprises": "עסקים",
    "Comment": "כיצד",
    "Pourquoi": "מדוע",
    "partenaire": "שותף",
    "partenaires": "שותפים",
    "accompagne": "מלווה",
    "étude de marché": "מחקר שוק",
    "négociation": "משא ומתן",
    "bail": "חוזה שכירות",
    "baux": "חוזי שכירות",
    "lancement": "השקה",
    "mois": "חודשים",
    "ans": "שנים",
    "secteur": "ענף",
    "restauration": "מסעדנות",
    "mode": "אופנה",
    "cosmétiques": "קוסמטיקה",
    "local": "מקומי",
    "locaux": "מקומיים",
}


def simple_translate(text: str, target_lang: str) -> str:
    """Simple translation using dictionary - for basic translations"""
    if not text:
        return text
    
    result = text
    if target_lang == "en":
        for fr, en in TRANSLATIONS_FR_EN.items():
            result = result.replace(fr, en)
    elif target_lang == "he":
        for fr, he in TRANSLATIONS_FR_HE.items():
            result = result.replace(fr, he)
    
    return result


def generate_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    import re
    slug = title.lower()
    slug = re.sub(r'[àáâãäå]', 'a', slug)
    slug = re.sub(r'[èéêë]', 'e', slug)
    slug = re.sub(r'[ìíîï]', 'i', slug)
    slug = re.sub(r'[òóôõö]', 'o', slug)
    slug = re.sub(r'[ùúûü]', 'u', slug)
    slug = re.sub(r'[ç]', 'c', slug)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


# ==========================================
# PUBLIC ENDPOINTS (No auth required)
# ==========================================

@router.get("/articles")
async def list_articles_public(
    language: str = Query("fr", description="Language filter"),
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50)
):
    """
    List published articles for public display.
    Returns only published articles, sorted by date (newest first).
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Build query - only published articles
    query = {"published": True, "language": language}
    if category:
        query["category"] = category
    
    # Get total count
    total = await db.blog_articles.count_documents(query)
    
    # Get articles with pagination
    skip = (page - 1) * limit
    cursor = db.blog_articles.find(query, {"content": 0}).sort("created_at", -1).skip(skip).limit(limit)
    articles = await cursor.to_list(length=limit)
    
    # Convert ObjectId to string
    for article in articles:
        article["_id"] = str(article["_id"])
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/articles/{slug}")
async def get_article_public(slug: str, language: str = Query("fr")):
    """
    Get a single published article by slug.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    article = await db.blog_articles.find_one({
        "slug": slug,
        "language": language,
        "published": True
    })
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article["_id"] = str(article["_id"])
    
    # Increment view count
    await db.blog_articles.update_one(
        {"_id": ObjectId(article["_id"])},
        {"$inc": {"views": 1}}
    )
    
    return article


@router.get("/categories")
async def list_categories(language: str = Query("fr")):
    """
    List all categories with article counts.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    pipeline = [
        {"$match": {"published": True, "language": language}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    cursor = db.blog_articles.aggregate(pipeline)
    categories = await cursor.to_list(length=100)
    
    return {"categories": [{"name": c["_id"], "count": c["count"]} for c in categories]}


# ==========================================
# ADMIN ENDPOINTS (Auth required)
# ==========================================

@router.get("/admin/articles")
async def list_articles_admin(
    user: Dict = Depends(get_current_user),
    language: Optional[str] = None,
    published: Optional[bool] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List all articles for admin (including drafts).
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Build query
    query = {}
    if language:
        query["language"] = language
    if published is not None:
        query["published"] = published
    
    # Get total count
    total = await db.blog_articles.count_documents(query)
    
    # Get articles
    skip = (page - 1) * limit
    cursor = db.blog_articles.find(query).sort("created_at", -1).skip(skip).limit(limit)
    articles = await cursor.to_list(length=limit)
    
    for article in articles:
        article["_id"] = str(article["_id"])
    
    return {
        "articles": articles,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.post("/admin/articles")
async def create_article(
    data: ArticleCreate,
    user: Dict = Depends(get_current_user)
):
    """
    Create a new blog article.
    If translate_en or translate_he is True, also creates translated versions.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Generate slug if not provided
    slug = data.slug or generate_slug(data.title)
    
    # Check for duplicate slug
    existing = await db.blog_articles.find_one({"slug": slug, "language": data.language})
    if existing:
        # Add random suffix
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    
    now = datetime.now(timezone.utc)
    
    article_doc = {
        "title": data.title,
        "slug": slug,
        "excerpt": data.excerpt,
        "content": data.content,
        "category": data.category,
        "image_url": data.image_url,
        "language": data.language,
        "published": data.published,
        "tags": data.tags,
        "author": data.author or user.get("email", "Admin"),
        "views": 0,
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("email")
    }
    
    result = await db.blog_articles.insert_one(article_doc)
    article_doc["_id"] = str(result.inserted_id)
    
    # Auto-translation logic
    translations_created = []
    
    if data.translate_en and data.language == "fr":
        # Create English version
        en_doc = {
            "title": simple_translate(data.title, "en"),
            "slug": slug,  # Same slug, different language
            "excerpt": simple_translate(data.excerpt, "en"),
            "content": simple_translate(data.content, "en"),
            "category": data.category,
            "image_url": data.image_url,
            "language": "en",
            "published": data.published,
            "tags": data.tags,
            "author": data.author or user.get("email", "Admin"),
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email"),
            "translated_from": str(result.inserted_id)
        }
        await db.blog_articles.insert_one(en_doc)
        translations_created.append("en")
    
    if data.translate_he and data.language == "fr":
        # Create Hebrew version
        he_doc = {
            "title": simple_translate(data.title, "he"),
            "slug": slug,  # Same slug, different language
            "excerpt": simple_translate(data.excerpt, "he"),
            "content": simple_translate(data.content, "he"),
            "category": data.category,
            "image_url": data.image_url,
            "language": "he",
            "published": data.published,
            "tags": data.tags,
            "author": data.author or user.get("email", "Admin"),
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email"),
            "translated_from": str(result.inserted_id)
        }
        await db.blog_articles.insert_one(he_doc)
        translations_created.append("he")
    
    message = "Article created successfully"
    if translations_created:
        message += f" + translations: {', '.join(translations_created)}"
    
    return {
        "success": True,
        "message": message,
        "article": article_doc,
        "translations_created": translations_created
    }


@router.get("/admin/articles/{article_id}")
async def get_article_admin(
    article_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Get a single article by ID for editing.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        article = await db.blog_articles.find_one({"_id": ObjectId(article_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid article ID")
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    article["_id"] = str(article["_id"])
    return article


@router.put("/admin/articles/{article_id}")
async def update_article(
    article_id: str,
    data: ArticleUpdate,
    user: Dict = Depends(get_current_user)
):
    """
    Update an existing article.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        existing = await db.blog_articles.find_one({"_id": ObjectId(article_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid article ID")
    
    if not existing:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # Build update document
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")
    
    # Regenerate slug if title changed
    if "title" in update_data and "slug" not in update_data:
        update_data["slug"] = generate_slug(update_data["title"])
    
    update_data["updated_at"] = datetime.now(timezone.utc)
    update_data["updated_by"] = user.get("email")
    
    await db.blog_articles.update_one(
        {"_id": ObjectId(article_id)},
        {"$set": update_data}
    )
    
    # Get updated article
    updated = await db.blog_articles.find_one({"_id": ObjectId(article_id)})
    updated["_id"] = str(updated["_id"])
    
    return {
        "success": True,
        "message": "Article updated successfully",
        "article": updated
    }


@router.delete("/admin/articles/{article_id}")
async def delete_article(
    article_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Delete an article.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        result = await db.blog_articles.delete_one({"_id": ObjectId(article_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid article ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Article not found")
    
    return {
        "success": True,
        "message": "Article deleted successfully"
    }


@router.post("/admin/articles/{article_id}/publish")
async def toggle_publish(
    article_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Toggle article published status.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        article = await db.blog_articles.find_one({"_id": ObjectId(article_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid article ID")
    
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    new_status = not article.get("published", False)
    
    await db.blog_articles.update_one(
        {"_id": ObjectId(article_id)},
        {
            "$set": {
                "published": new_status,
                "updated_at": datetime.now(timezone.utc),
                "published_at": datetime.now(timezone.utc) if new_status else None
            }
        }
    )
    
    return {
        "success": True,
        "published": new_status,
        "message": f"Article {'published' if new_status else 'unpublished'}"
    }


# ==========================================
# SEED SAMPLE ARTICLES
# ==========================================

@router.post("/admin/seed")
async def seed_sample_articles(user: Dict = Depends(get_current_user)):
    """
    Seed the database with sample articles.
    Only works if no articles exist yet.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Check if articles already exist
    count = await db.blog_articles.count_documents({})
    if count > 0:
        return {"success": False, "message": f"{count} articles already exist", "seeded": 0}
    
    now = datetime.now(timezone.utc)
    
    sample_articles = [
        {
            "title": "L'IA dans le retail israélien en 2026",
            "slug": "ia-retail-israelien-2026",
            "excerpt": "Comment l'intelligence artificielle transforme l'expérience client dans les centres commerciaux de Tel Aviv.",
            "content": """
                <h2>L'Intelligence Artificielle Révolutionne le Commerce</h2>
                <p>En 2026, les centres commerciaux israéliens sont à la pointe de l'innovation technologique. L'IA est désormais omniprésente dans l'expérience d'achat.</p>
                <h3>Personnalisation en Temps Réel</h3>
                <p>Les systèmes d'IA analysent les comportements d'achat pour proposer des recommandations personnalisées instantanément.</p>
                <h3>Gestion des Stocks Intelligente</h3>
                <p>Les algorithmes prédictifs permettent une gestion optimale des inventaires, réduisant le gaspillage de 40%.</p>
            """,
            "category": "Retail Tech",
            "image_url": None,
            "language": "fr",
            "published": True,
            "tags": ["IA", "Retail", "Innovation", "Tel Aviv"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "Ouvrir son réseau en Israël : Guide Complet",
            "slug": "ouvrir-reseau-israel-guide",
            "excerpt": "Les étapes clés pour réussir son implantation de franchise sur le marché local.",
            "content": """
                <h2>Réussir son Expansion en Israël</h2>
                <p>Le marché israélien offre des opportunités uniques pour les franchises internationales. Voici les étapes essentielles.</p>
                <h3>1. Étude de Marché</h3>
                <p>Comprendre les spécificités culturelles et commerciales du marché local est primordial.</p>
                <h3>2. Partenaire Local</h3>
                <p>Trouver un master-franchisé local avec une connaissance approfondie du terrain.</p>
                <h3>3. Adaptation du Concept</h3>
                <p>Adapter votre offre aux goûts et attentes des consommateurs israéliens.</p>
            """,
            "category": "Expansion",
            "image_url": None,
            "language": "fr",
            "published": True,
            "tags": ["Franchise", "Expansion", "Business", "Guide"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "L'essor des Food Courts Premium",
            "slug": "essor-food-courts-premium",
            "excerpt": "Analyse du changement des habitudes de consommation post-2025.",
            "content": """
                <h2>La Révolution des Espaces de Restauration</h2>
                <p>Les food courts traditionnels cèdent la place à des concepts premium offrant une expérience gastronomique raffinée.</p>
                <h3>Tendances Observées</h3>
                <ul>
                    <li>Montée en gamme des offres culinaires</li>
                    <li>Design architectural soigné</li>
                    <li>Focus sur les produits locaux et durables</li>
                </ul>
                <h3>Opportunités pour les Franchises</h3>
                <p>Cette évolution ouvre de nouvelles perspectives pour les concepts de restauration haut de gamme.</p>
            """,
            "category": "Success Story",
            "image_url": None,
            "language": "fr",
            "published": True,
            "tags": ["Food Court", "Restauration", "Tendances"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        }
    ]
    
    result = await db.blog_articles.insert_many(sample_articles)
    
    return {
        "success": True,
        "message": f"{len(result.inserted_ids)} sample articles created",
        "seeded": len(result.inserted_ids)
    }


# ==========================================
# FAQ ENDPOINTS
# ==========================================

class FAQItem(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., min_length=1, max_length=2000)
    language: str = Field(default="fr")
    order: int = Field(default=0)
    published: bool = Field(default=True)
    translate_en: bool = Field(default=False)
    translate_he: bool = Field(default=False)


@router.get("/faq")
async def get_faq_public(language: str = Query("fr")):
    """
    Get published FAQ items for public display.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    cursor = db.blog_faq.find(
        {"language": language, "published": True}
    ).sort("order", 1)
    
    items = await cursor.to_list(length=100)
    
    for item in items:
        item["_id"] = str(item["_id"])
    
    return {"items": items}


@router.get("/admin/faq")
async def get_faq_admin(
    user: Dict = Depends(get_current_user),
    language: Optional[str] = None
):
    """
    Get all FAQ items for admin.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    query = {}
    if language:
        query["language"] = language
    
    cursor = db.blog_faq.find(query).sort("order", 1)
    items = await cursor.to_list(length=100)
    
    for item in items:
        item["_id"] = str(item["_id"])
    
    return {"items": items}


@router.post("/admin/faq")
async def create_faq(
    data: FAQItem,
    user: Dict = Depends(get_current_user)
):
    """
    Create a new FAQ item.
    If translate_en or translate_he is True, also creates translated versions.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    now = datetime.now(timezone.utc)
    
    # Get max order
    max_order_doc = await db.blog_faq.find_one(
        {"language": data.language},
        sort=[("order", -1)]
    )
    max_order = max_order_doc["order"] + 1 if max_order_doc else 0
    
    faq_doc = {
        "question": data.question,
        "answer": data.answer,
        "language": data.language,
        "order": data.order or max_order,
        "published": data.published,
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("email")
    }
    
    result = await db.blog_faq.insert_one(faq_doc)
    faq_doc["_id"] = str(result.inserted_id)
    
    # Auto-translation logic for FAQ
    translations_created = []
    
    if data.translate_en and data.language == "fr":
        # Get max order for English
        max_order_en = await db.blog_faq.find_one(
            {"language": "en"},
            sort=[("order", -1)]
        )
        order_en = max_order_en["order"] + 1 if max_order_en else 0
        
        en_doc = {
            "question": simple_translate(data.question, "en"),
            "answer": simple_translate(data.answer, "en"),
            "language": "en",
            "order": order_en,
            "published": data.published,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email"),
            "translated_from": str(result.inserted_id)
        }
        await db.blog_faq.insert_one(en_doc)
        translations_created.append("en")
    
    if data.translate_he and data.language == "fr":
        # Get max order for Hebrew
        max_order_he = await db.blog_faq.find_one(
            {"language": "he"},
            sort=[("order", -1)]
        )
        order_he = max_order_he["order"] + 1 if max_order_he else 0
        
        he_doc = {
            "question": simple_translate(data.question, "he"),
            "answer": simple_translate(data.answer, "he"),
            "language": "he",
            "order": order_he,
            "published": data.published,
            "created_at": now,
            "updated_at": now,
            "created_by": user.get("email"),
            "translated_from": str(result.inserted_id)
        }
        await db.blog_faq.insert_one(he_doc)
        translations_created.append("he")
    
    message = "FAQ créée avec succès"
    if translations_created:
        message += f" + traductions: {', '.join(translations_created)}"
    
    return {"success": True, "item": faq_doc, "message": message, "translations_created": translations_created}


@router.put("/admin/faq/{faq_id}")
async def update_faq(
    faq_id: str,
    data: FAQItem,
    user: Dict = Depends(get_current_user)
):
    """
    Update a FAQ item.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        await db.blog_faq.update_one(
            {"_id": ObjectId(faq_id)},
            {"$set": {
                "question": data.question,
                "answer": data.answer,
                "language": data.language,
                "order": data.order,
                "published": data.published,
                "updated_at": datetime.now(timezone.utc),
                "updated_by": user.get("email")
            }}
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID")
    
    return {"success": True}


@router.delete("/admin/faq/{faq_id}")
async def delete_faq(
    faq_id: str,
    user: Dict = Depends(get_current_user)
):
    """
    Delete a FAQ item.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    try:
        result = await db.blog_faq.delete_one({"_id": ObjectId(faq_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid FAQ ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    return {"success": True}


@router.post("/admin/faq/seed")
async def seed_faq(user: Dict = Depends(get_current_user)):
    """
    Seed default FAQ items in FR, EN and HE.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Clear existing FAQ
    await db.blog_faq.delete_many({})
    
    now = datetime.now(timezone.utc)
    
    default_faq = [
        # ============ FRENCH ============
        {
            "question": "Comment IGV peut m'aider à m'implanter en Israël ?",
            "answer": "IGV vous accompagne de A à Z : étude de marché, recherche de partenaires locaux, négociation de baux commerciaux et lancement opérationnel.",
            "language": "fr",
            "order": 0,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Combien de temps faut-il pour ouvrir en Israël ?",
            "answer": "En moyenne 6 à 12 mois selon la complexité du projet et le secteur d'activité.",
            "language": "fr",
            "order": 1,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Quels secteurs sont porteurs en Israël ?",
            "answer": "La restauration, la mode, les cosmétiques et le retail tech connaissent une forte croissance.",
            "language": "fr",
            "order": 2,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Avez-vous des partenaires locaux en Israël ?",
            "answer": "Oui, nous avons un réseau solide de partenaires locaux : avocats, comptables, agents immobiliers et professionnels du retail.",
            "language": "fr",
            "order": 3,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Quels sont vos tarifs ?",
            "answer": "Nos tarifs varient selon la complexité de votre projet. Contactez-nous pour un devis personnalisé gratuit.",
            "language": "fr",
            "order": 4,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        # ============ ENGLISH ============
        {
            "question": "How can IGV help me expand to Israel?",
            "answer": "IGV supports you from A to Z: market research, local partner search, commercial lease negotiation and operational launch.",
            "language": "en",
            "order": 0,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "How long does it take to open in Israel?",
            "answer": "On average 6 to 12 months depending on project complexity and industry.",
            "language": "en",
            "order": 1,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Which sectors are growing in Israel?",
            "answer": "Food & beverage, fashion, cosmetics and retail tech are experiencing strong growth.",
            "language": "en",
            "order": 2,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "Do you have local partners in Israel?",
            "answer": "Yes, we have a strong network of local partners: lawyers, accountants, real estate agents and retail professionals.",
            "language": "en",
            "order": 3,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "What are your rates?",
            "answer": "Our rates vary depending on the complexity of your project. Contact us for a free personalized quote.",
            "language": "en",
            "order": 4,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        # ============ HEBREW ============
        {
            "question": "כיצד IGV יכולה לעזור לי להתרחב לישראל?",
            "answer": "IGV מלווה אתכם מא' ועד ת': מחקר שוק, חיפוש שותפים מקומיים, משא ומתן על חוזי שכירות מסחריים והשקה תפעולית.",
            "language": "he",
            "order": 0,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "כמה זמן לוקח לפתוח עסק בישראל?",
            "answer": "בממוצע 6 עד 12 חודשים, בהתאם למורכבות הפרויקט ולענף הפעילות.",
            "language": "he",
            "order": 1,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "אילו תחומים צומחים בישראל?",
            "answer": "מסעדנות, אופנה, קוסמטיקה וטכנולוגיית קמעונאות חווים צמיחה משמעותית.",
            "language": "he",
            "order": 2,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "האם יש לכם שותפים מקומיים בישראל?",
            "answer": "כן, יש לנו רשת חזקה של שותפים מקומיים: עורכי דין, רואי חשבון, סוכני נדל\"ן ואנשי מקצוע בתחום הקמעונאות.",
            "language": "he",
            "order": 3,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
        {
            "question": "מהם התעריפים שלכם?",
            "answer": "התעריפים שלנו משתנים בהתאם למורכבות הפרויקט. צרו איתנו קשר לקבלת הצעת מחיר מותאמת אישית בחינם.",
            "language": "he",
            "order": 4,
            "published": True,
            "created_at": now,
            "updated_at": now
        },
    ]
    
    result = await db.blog_faq.insert_many(default_faq)
    
    return {
        "success": True,
        "message": f"{len(result.inserted_ids)} FAQ items created (FR, EN, HE)",
        "seeded": len(result.inserted_ids)
    }


# ==========================================
# SEED ARTICLES IN 3 LANGUAGES
# ==========================================

@router.post("/admin/seed-all-languages")
async def seed_articles_all_languages(user: Dict = Depends(get_current_user)):
    """
    Seed articles in all 3 languages (FR, EN, HE).
    Clears existing articles first.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Clear existing articles
    await db.blog_articles.delete_many({})
    
    now = datetime.now(timezone.utc)
    
    articles = [
        # ============ FRENCH ============
        {
            "title": "L'IA dans le retail israélien en 2026",
            "slug": "ia-retail-israelien-2026",
            "excerpt": "Comment l'intelligence artificielle transforme l'expérience client dans les centres commerciaux de Tel Aviv.",
            "content": """
                <h2>L'Intelligence Artificielle Révolutionne le Commerce</h2>
                <p>En 2026, les centres commerciaux israéliens sont à la pointe de l'innovation technologique. L'IA est désormais omniprésente dans l'expérience d'achat.</p>
                <h3>Personnalisation en Temps Réel</h3>
                <p>Les systèmes d'IA analysent les comportements d'achat pour proposer des recommandations personnalisées instantanément. Chaque visiteur reçoit une expérience unique adaptée à ses préférences.</p>
                <h3>Gestion des Stocks Intelligente</h3>
                <p>Les algorithmes prédictifs permettent une gestion optimale des inventaires, réduisant le gaspillage de 40% et améliorant la disponibilité des produits.</p>
                <h3>L'Avenir du Retail</h3>
                <p>Israël se positionne comme leader mondial de l'innovation retail, attirant les marques internationales souhaitant tester les technologies de demain.</p>
            """,
            "category": "Retail Tech",
            "image_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=800",
            "language": "fr",
            "published": True,
            "tags": ["IA", "Retail", "Innovation", "Tel Aviv"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "Ouvrir son réseau en Israël : Guide Complet",
            "slug": "ouvrir-reseau-israel-guide",
            "excerpt": "Les étapes clés pour réussir son implantation de franchise sur le marché local.",
            "content": """
                <h2>Réussir son Expansion en Israël</h2>
                <p>Le marché israélien offre des opportunités uniques pour les franchises internationales. Voici les étapes essentielles pour réussir.</p>
                <h3>1. Étude de Marché Approfondie</h3>
                <p>Comprendre les spécificités culturelles et commerciales du marché local est primordial. Le consommateur israélien est exigeant et connecté.</p>
                <h3>2. Trouver le Bon Partenaire Local</h3>
                <p>Un master-franchisé local avec une connaissance approfondie du terrain est votre meilleur atout. IGV peut vous aider à identifier le partenaire idéal.</p>
                <h3>3. Adapter Votre Concept</h3>
                <p>L'adaptation aux goûts locaux est cruciale. Cela inclut le menu, les horaires, et même la communication marketing.</p>
                <h3>4. Aspects Juridiques et Fiscaux</h3>
                <p>Le cadre réglementaire israélien a ses particularités. Un accompagnement juridique spécialisé est recommandé.</p>
            """,
            "category": "Expansion",
            "image_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800",
            "language": "fr",
            "published": True,
            "tags": ["Franchise", "Expansion", "Business", "Guide"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "L'essor des Food Courts Premium",
            "slug": "essor-food-courts-premium",
            "excerpt": "Analyse du changement des habitudes de consommation post-2025.",
            "content": """
                <h2>La Révolution des Espaces de Restauration</h2>
                <p>Les food courts traditionnels cèdent la place à des concepts premium offrant une expérience gastronomique raffinée.</p>
                <h3>Tendances Observées en 2026</h3>
                <ul>
                    <li><strong>Montée en gamme</strong> : Des chefs renommés ouvrent dans les centres commerciaux</li>
                    <li><strong>Design architectural</strong> : Espaces soignés rivalisant avec les restaurants indépendants</li>
                    <li><strong>Produits locaux</strong> : Focus sur la durabilité et les circuits courts</li>
                </ul>
                <h3>Opportunités pour les Franchises</h3>
                <p>Cette évolution ouvre de nouvelles perspectives pour les concepts de restauration haut de gamme cherchant une implantation rapide.</p>
            """,
            "category": "Success Story",
            "image_url": "https://images.unsplash.com/photo-1567521464027-f127ff144326?w=800",
            "language": "fr",
            "published": True,
            "tags": ["Food Court", "Restauration", "Tendances"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        # ============ ENGLISH ============
        {
            "title": "AI in Israeli Retail in 2026",
            "slug": "ai-israeli-retail-2026",
            "excerpt": "How artificial intelligence is transforming the customer experience in Tel Aviv shopping centers.",
            "content": """
                <h2>Artificial Intelligence Revolutionizes Commerce</h2>
                <p>In 2026, Israeli shopping centers are at the forefront of technological innovation. AI is now ubiquitous in the shopping experience.</p>
                <h3>Real-Time Personalization</h3>
                <p>AI systems analyze shopping behaviors to offer personalized recommendations instantly. Each visitor receives a unique experience tailored to their preferences.</p>
                <h3>Intelligent Inventory Management</h3>
                <p>Predictive algorithms enable optimal inventory management, reducing waste by 40% and improving product availability.</p>
                <h3>The Future of Retail</h3>
                <p>Israel positions itself as a global leader in retail innovation, attracting international brands wanting to test tomorrow's technologies.</p>
            """,
            "category": "Retail Tech",
            "image_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=800",
            "language": "en",
            "published": True,
            "tags": ["AI", "Retail", "Innovation", "Tel Aviv"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "Opening Your Network in Israel: Complete Guide",
            "slug": "opening-network-israel-guide",
            "excerpt": "Key steps to successfully establish your franchise in the local market.",
            "content": """
                <h2>Succeeding in Your Expansion to Israel</h2>
                <p>The Israeli market offers unique opportunities for international franchises. Here are the essential steps to succeed.</p>
                <h3>1. In-Depth Market Research</h3>
                <p>Understanding the cultural and commercial specificities of the local market is paramount. Israeli consumers are demanding and connected.</p>
                <h3>2. Finding the Right Local Partner</h3>
                <p>A local master-franchisee with deep knowledge of the terrain is your best asset. IGV can help you identify the ideal partner.</p>
                <h3>3. Adapting Your Concept</h3>
                <p>Adaptation to local tastes is crucial. This includes menu, hours, and even marketing communication.</p>
                <h3>4. Legal and Tax Aspects</h3>
                <p>The Israeli regulatory framework has its particularities. Specialized legal support is recommended.</p>
            """,
            "category": "Expansion",
            "image_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800",
            "language": "en",
            "published": True,
            "tags": ["Franchise", "Expansion", "Business", "Guide"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "The Rise of Premium Food Courts",
            "slug": "rise-premium-food-courts",
            "excerpt": "Analysis of changing consumption habits post-2025.",
            "content": """
                <h2>The Revolution of Dining Spaces</h2>
                <p>Traditional food courts are giving way to premium concepts offering a refined gastronomic experience.</p>
                <h3>Trends Observed in 2026</h3>
                <ul>
                    <li><strong>Upscaling</strong>: Renowned chefs opening in shopping centers</li>
                    <li><strong>Architectural design</strong>: Carefully designed spaces rivaling independent restaurants</li>
                    <li><strong>Local products</strong>: Focus on sustainability and short circuits</li>
                </ul>
                <h3>Opportunities for Franchises</h3>
                <p>This evolution opens new perspectives for high-end restaurant concepts seeking rapid establishment.</p>
            """,
            "category": "Success Story",
            "image_url": "https://images.unsplash.com/photo-1567521464027-f127ff144326?w=800",
            "language": "en",
            "published": True,
            "tags": ["Food Court", "Restaurant", "Trends"],
            "author": "IGV Team",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        # ============ HEBREW ============
        {
            "title": "בינה מלאכותית בקמעונאות הישראלית ב-2026",
            "slug": "ai-retail-israel-2026-he",
            "excerpt": "כיצד הבינה המלאכותית משנה את חוויית הלקוח במרכזי הקניות של תל אביב.",
            "content": """
                <h2>הבינה המלאכותית מחוללת מהפכה במסחר</h2>
                <p>ב-2026, מרכזי הקניות בישראל נמצאים בחזית החדשנות הטכנולוגית. הבינה המלאכותית נמצאת כעת בכל מקום בחוויית הקנייה.</p>
                <h3>התאמה אישית בזמן אמת</h3>
                <p>מערכות AI מנתחות התנהגויות קנייה כדי להציע המלצות מותאמות אישית באופן מיידי. כל מבקר מקבל חוויה ייחודית המותאמת להעדפותיו.</p>
                <h3>ניהול מלאי חכם</h3>
                <p>אלגוריתמים חזויים מאפשרים ניהול מלאי אופטימלי, מפחיתים בזבוז ב-40% ומשפרים את זמינות המוצרים.</p>
                <h3>עתיד הקמעונאות</h3>
                <p>ישראל ממצבת את עצמה כמובילה עולמית בחדשנות קמעונאית, ומושכת מותגים בינלאומיים המעוניינים לבחון את הטכנולוגיות של מחר.</p>
            """,
            "category": "Retail Tech",
            "image_url": "https://images.unsplash.com/photo-1531297484001-80022131f5a1?w=800",
            "language": "he",
            "published": True,
            "tags": ["AI", "קמעונאות", "חדשנות", "תל אביב"],
            "author": "צוות IGV",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "פתיחת רשת בישראל: מדריך מלא",
            "slug": "opening-network-israel-guide-he",
            "excerpt": "השלבים המרכזיים להצלחה בהקמת זיכיון בשוק המקומי.",
            "content": """
                <h2>להצליח בהתרחבות לישראל</h2>
                <p>השוק הישראלי מציע הזדמנויות ייחודיות לזיכיונות בינלאומיים. הנה השלבים החיוניים להצלחה.</p>
                <h3>1. מחקר שוק מעמיק</h3>
                <p>הבנת המאפיינים התרבותיים והמסחריים של השוק המקומי היא קריטית. הצרכן הישראלי תובעני ומחובר.</p>
                <h3>2. מציאת השותף המקומי הנכון</h3>
                <p>מאסטר-זכיין מקומי עם היכרות עמוקה של השטח הוא הנכס הטוב ביותר שלכם. IGV יכולה לעזור לכם לזהות את השותף האידיאלי.</p>
                <h3>3. התאמת הקונספט</h3>
                <p>התאמה לטעם המקומי היא קריטית. זה כולל תפריט, שעות פעילות, ואפילו תקשורת שיווקית.</p>
                <h3>4. היבטים משפטיים ומיסויים</h3>
                <p>למסגרת הרגולטורית הישראלית יש מאפיינים ייחודיים. ליווי משפטי מתמחה מומלץ.</p>
            """,
            "category": "Expansion",
            "image_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=800",
            "language": "he",
            "published": True,
            "tags": ["זיכיון", "התרחבות", "עסקים", "מדריך"],
            "author": "צוות IGV",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        {
            "title": "עליית פודקורטים הפרימיום",
            "slug": "rise-premium-food-courts-he",
            "excerpt": "ניתוח השינוי בהרגלי הצריכה לאחר 2025.",
            "content": """
                <h2>המהפכה במרחבי האוכל</h2>
                <p>פודקורטים מסורתיים פינו את מקומם לקונספטים פרימיום המציעים חוויה גסטרונומית מעודנת.</p>
                <h3>מגמות שנצפו ב-2026</h3>
                <ul>
                    <li><strong>שדרוג</strong>: שפים מפורסמים פותחים במרכזי קניות</li>
                    <li><strong>עיצוב אדריכלי</strong>: חללים מעוצבים בקפידה המתחרים במסעדות עצמאיות</li>
                    <li><strong>מוצרים מקומיים</strong>: דגש על קיימות ומעגלים קצרים</li>
                </ul>
                <h3>הזדמנויות לזיכיונות</h3>
                <p>התפתחות זו פותחת אופקים חדשים לקונספטים של מסעדנות יוקרתית המחפשים התבססות מהירה.</p>
            """,
            "category": "Success Story",
            "image_url": "https://images.unsplash.com/photo-1567521464027-f127ff144326?w=800",
            "language": "he",
            "published": True,
            "tags": ["פודקורט", "מסעדנות", "מגמות"],
            "author": "צוות IGV",
            "views": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
    ]
    
    result = await db.blog_articles.insert_many(articles)
    
    return {
        "success": True,
        "message": f"{len(result.inserted_ids)} articles created (3 FR + 3 EN + 3 HE)",
        "seeded": len(result.inserted_ids)
    }
