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
    group_slug: Optional[str] = None  # Cross-language group identifier


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
    group_slug: Optional[str] = None  # Cross-language group identifier


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


@router.get("/articles/{slug}/related")
async def get_article_related(slug: str):
    """
    Returns the translated slugs for all language versions of an article.
    Uses the group_slug field to find related articles across languages.
    Response: {"translations": {"fr": "slug-fr", "en": "slug-en", "he": "slug-he"}, "group_slug": ".."}
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    article = await db.blog_articles.find_one({"slug": slug})
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    group_slug = article.get("group_slug")
    article_lang = article.get("language", "fr")

    if not group_slug:
        # No group_slug set — try to reconstruct siblings via translated_from linkage.
        # Case 1: this article IS a translation (has translated_from pointing to a source slug).
        # Case 2: this article IS a source (other articles have translated_from = this slug).
        translations = {article_lang: slug}
        source_slug = article.get("translated_from")
        if source_slug:
            # Find the source article + its other translations
            siblings_cursor = db.blog_articles.find(
                {"$or": [{"slug": source_slug}, {"translated_from": source_slug}], "published": True},
                {"slug": 1, "language": 1, "_id": 0}
            )
        else:
            # This may be the source — find articles translated from this slug
            siblings_cursor = db.blog_articles.find(
                {"translated_from": slug, "published": True},
                {"slug": 1, "language": 1, "_id": 0}
            )
        siblings = await siblings_cursor.to_list(length=10)
        for s in siblings:
            translations[s["language"]] = s["slug"]
        return {"translations": translations, "group_slug": None}

    cursor = db.blog_articles.find(
        {"group_slug": group_slug, "published": True},
        {"slug": 1, "language": 1, "_id": 0}
    )
    docs = await cursor.to_list(length=10)
    translations = {doc["language"]: doc["slug"] for doc in docs}
    return {"translations": translations, "group_slug": group_slug}


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


@router.post("/admin/migrate-group-slugs")
async def admin_migrate_group_slugs(user: Dict = Depends(get_current_user)):
    """
    Force-trigger the group_slug migration on all seeded blog articles.
    Idempotent: only updates articles where group_slug is null or missing.
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    GROUPS = [
        ("alyah-franchise-entrepreneur",
         ["alyah-franchise-entrepreneur", "aliyah-franchise-entrepreneur-guide", "alyah-franchise-entrepreneur-he"]),
    ]
    total = 0
    for group_slug, slugs in GROUPS:
        for slug in slugs:
            result = await db.blog_articles.update_many(
                {"slug": slug, "$or": [{"group_slug": {"$exists": False}}, {"group_slug": None}]},
                {"$set": {"group_slug": group_slug}}
            )
            total += result.modified_count
    return {"success": True, "articles_updated": total}


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
    
    # group_slug: cross-language link identifier — default to article slug
    group_slug = data.group_slug or slug

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
        "created_by": user.get("email"),
        "group_slug": group_slug,
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
            "translated_from": str(result.inserted_id),
            "group_slug": group_slug,
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
            "translated_from": str(result.inserted_id),
            "group_slug": group_slug,
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
# MIGRATION — SET GROUP SLUGS
# ==========================================

@router.post("/admin/migrate-group-slugs")
async def migrate_group_slugs(user: Dict = Depends(get_current_user)):
    """
    One-time migration: sets group_slug on the 9 seeded articles so that
    the language switcher can find the correct translation per language.
    Safe to run multiple times (idempotent).
    """
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    # Known article groups: each tuple = (group_slug, [slugs in this group])
    GROUPS = [
        (
            "retail-ia-israel-2026",
            ["ia-retail-israelien-2026", "ai-israeli-retail-2026", "ai-retail-israel-2026-he"],
        ),
        (
            "opening-network-israel-guide",
            ["ouvrir-reseau-israel-guide", "opening-network-israel-guide", "opening-network-israel-guide-he"],
        ),
        (
            "food-courts-premium",
            ["essor-food-courts-premium", "rise-premium-food-courts", "rise-premium-food-courts-he"],
        ),
    ]

    updated = 0
    for group_slug, slugs in GROUPS:
        for slug in slugs:
            result = await db.blog_articles.update_many(
                {"slug": slug},
                {"$set": {"group_slug": group_slug}}
            )
            updated += result.modified_count

    return {
        "success": True,
        "message": f"group_slug set on {updated} articles",
        "groups": [g for g, _ in GROUPS],
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
            "title": "Faire son Alyah en tant qu'entrepreneur-franchisé",
            "slug": "alyah-franchise-entrepreneur",
            "excerpt": "Vous avez quitté Paris pour Haïfa avec vos valises et votre projet de franchise. Voici les clés pour réussir votre implantation commerciale en Israël dès la première année.",
            "content": """
                <h2>Du CDG-TLV à votre premier local commercial</h2>
                <p>Chaque année, des centaines d'entrepreneurs francophones débarquent à l'aéroport Ben Gourion ou au port de Haïfa avec une idée claire : reproduire en Israël le modèle commercial qui a fait ses preuves en France. Réseau de restauration, concept retail, service à la personne... le rêve est là. La réalité, elle, demande une préparation sérieuse.</p>
                <h3>1. Comprendre le marché israélien avant tout</h3>
                <p>Israël n'est pas la France avec du soleil. Le consommateur israélien est exigeant, ultra-connecté et n'hésite pas à comparer les prix en temps réel. Il attend une expérience, pas seulement un produit. Votre concept doit être adapté, pas seulement traduit.</p>
                <ul>
                    <li><strong>Le prix est roi</strong> mais la qualité prime — le consommateur paiera plus pour ce qui vaut vraiment</li>
                    <li><strong>La rapidité de service</strong> est non-négociable dans le retail alimentaire</li>
                    <li><strong>Le digital</strong> : les avis Google et Waze sont consultés avant chaque visite</li>
                </ul>
                <h3>2. Le statut d'Olé Hadach : vos avantages fiscaux</h3>
                <p>En tant que nouvel immigrant (<em>Olé Hadach</em>), vous bénéficiez d'exemptions fiscales significatives pendant 10 ans sur vos revenus étrangers. Ces avantages sont un levier réel pour financer votre implantation initiale et réduire la pression sur votre trésorerie.</p>
                <h3>3. Choisir la bonne ville d'implantation</h3>
                <p>Tel Aviv, Jérusalem, Haïfa ou les nouvelles villes de périphérie ? Chaque marché a ses dynamiques :</p>
                <ul>
                    <li><strong>Tel Aviv</strong> : fort pouvoir d'achat, concurrence intense, loyers élevés</li>
                    <li><strong>Jérusalem</strong> : clientèle mixte, flux touristiques importants</li>
                    <li><strong>Haïfa</strong> : ville en mutation, loyers raisonnables, clientèle locale fidèle</li>
                    <li><strong>Périphérie</strong> : moins de concurrence, soutien gouvernemental, croissance démographique</li>
                </ul>
                <h3>4. L'accompagnement IGV : de l'idée au premier jour d'ouverture</h3>
                <p>Notre mission est de transformer votre expérience française en succès israélien. De la validation du concept à la formation des équipes locales, en passant par les démarches administratives, nous gérons chaque étape à vos côtés.</p>
                <blockquote><p>« Maintenant que tu es israélien, c'est ton tour de construire. »</p></blockquote>
                <p><strong>Vous avez un concept ? Parlez-nous de votre projet dès aujourd'hui.</strong></p>
            """,
            "category": "Alyah & Entrepreneuriat",
            "image_url": "https://israelgrowthventure.com/images/blog/olim-entrepreneur.jpg",
            "language": "fr",
            "published": True,
            "tags": ["Alyah", "Franchise", "Entrepreneur", "Olim", "Implantation"],
            "author": "IGV Team",
            "views": 0,
            "group_slug": "alyah-franchise-entrepreneur",
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
            "title": "Faire son Alyah en tant qu'entrepreneur-franchisé",
            "slug": "alyah-franchise-entrepreneur",
            "excerpt": "Vous avez quitté Paris pour Haïfa avec vos valises et votre projet de franchise. Voici les clés pour réussir votre implantation commerciale en Israël dès la première année.",
            "content": """
                <h2>Du CDG-TLV à votre premier local commercial</h2>
                <p>Chaque année, des centaines d'entrepreneurs francophones débarquent à l'aéroport Ben Gourion ou au port de Haïfa avec une idée claire : reproduire en Israël le modèle commercial qui a fait ses preuves en France. Réseau de restauration, concept retail, service à la personne... le rêve est là. La réalité, elle, demande une préparation sérieuse.</p>
                <h3>1. Comprendre le marché israélien avant tout</h3>
                <p>Israël n'est pas la France avec du soleil. Le consommateur israélien est exigeant, ultra-connecté et n'hésite pas à comparer les prix en temps réel. Il attend une expérience, pas seulement un produit. Votre concept doit être adapté, pas seulement traduit.</p>
                <ul>
                    <li><strong>Le prix est roi</strong> mais la qualité prime — le consommateur paiera plus pour ce qui vaut vraiment</li>
                    <li><strong>La rapidité de service</strong> est non-négociable dans le retail alimentaire</li>
                    <li><strong>Le digital</strong> : les avis Google et Waze sont consultés avant chaque visite</li>
                </ul>
                <h3>2. Le statut d'Olé Hadach : vos avantages fiscaux</h3>
                <p>En tant que nouvel immigrant (<em>Olé Hadach</em>), vous bénéficiez d'exemptions fiscales significatives pendant 10 ans sur vos revenus étrangers. Ces avantages sont un levier réel pour financer votre implantation initiale et réduire la pression sur votre trésorerie.</p>
                <h3>3. Choisir la bonne ville d'implantation</h3>
                <p>Tel Aviv, Jérusalem, Haïfa ou les nouvelles villes de périphérie ? Chaque marché a ses dynamiques :</p>
                <ul>
                    <li><strong>Tel Aviv</strong> : fort pouvoir d'achat, concurrence intense, loyers élevés</li>
                    <li><strong>Jérusalem</strong> : clientèle mixte, flux touristiques importants</li>
                    <li><strong>Haïfa</strong> : ville en mutation, loyers raisonnables, clientèle locale fidèle</li>
                    <li><strong>Périphérie</strong> : moins de concurrence, soutien gouvernemental, croissance démographique</li>
                </ul>
                <h3>4. L'accompagnement IGV : de l'idée au premier jour d'ouverture</h3>
                <p>Notre mission est de transformer votre expérience française en succès israélien. De la validation du concept à la formation des équipes locales, en passant par les démarches administratives, nous gérons chaque étape à vos côtés.</p>
                <blockquote><p>« Maintenant que tu es israélien, c'est ton tour de construire. »</p></blockquote>
                <p><strong>Vous avez un concept ? Parlez-nous de votre projet dès aujourd'hui.</strong></p>
            """,
            "category": "Alyah & Entrepreneuriat",
            "image_url": "https://israelgrowthventure.com/images/blog/olim-entrepreneur.jpg",
            "language": "fr",
            "published": True,
            "tags": ["Alyah", "Franchise", "Entrepreneur", "Olim", "Implantation"],
            "author": "IGV Team",
            "views": 0,
            "group_slug": "alyah-franchise-entrepreneur",
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        # ============ ENGLISH ============
        {
            "title": "Making Aliyah as a Franchise Entrepreneur",
            "slug": "aliyah-franchise-entrepreneur-guide",
            "excerpt": "You left Paris for Haifa with your suitcase and your business idea. Here are the keys to successfully launching your franchise in Israel from day one.",
            "content": """
                <h2>From CDG-TLV to Your First Commercial Space</h2>
                <p>Every year, hundreds of French-speaking entrepreneurs land at Ben Gurion Airport or arrive at the port of Haifa with a clear vision: to replicate in Israel the business model that worked in France. Restaurant chains, retail concepts, personal services... the dream is there. Reality, however, requires serious preparation.</p>
                <h3>1. Understanding the Israeli Market First</h3>
                <p>Israel is not France with sunshine. Israeli consumers are demanding, hyper-connected, and don't hesitate to compare prices in real time. They expect an experience, not just a product. Your concept must be adapted, not just translated.</p>
                <ul>
                    <li><strong>Price matters</strong> but quality comes first — consumers will pay more for real value</li>
                    <li><strong>Speed of service</strong> is non-negotiable in food retail</li>
                    <li><strong>Digital presence</strong>: Google and Waze reviews are checked before every visit</li>
                </ul>
                <h3>2. Oleh Hadash Status: Your Tax Advantages</h3>
                <p>As a new immigrant (<em>Oleh Hadash</em>), you benefit from significant tax exemptions for 10 years on foreign income. These advantages are a real lever to finance your initial setup and reduce cash flow pressure.</p>
                <h3>3. Choosing the Right City</h3>
                <p>Tel Aviv, Jerusalem, Haifa, or the new peripheral cities? Each market has its own dynamics:</p>
                <ul>
                    <li><strong>Tel Aviv</strong>: high purchasing power, intense competition, high rents</li>
                    <li><strong>Jerusalem</strong>: mixed clientele, significant tourist traffic</li>
                    <li><strong>Haifa</strong>: city in transition, reasonable rents, loyal local customers</li>
                    <li><strong>Periphery</strong>: less competition, government support, demographic growth</li>
                </ul>
                <h3>4. IGV Support: From Idea to Opening Day</h3>
                <p>Our mission is to turn your French experience into Israeli success. From concept validation to local team training and administrative processes, we manage every step alongside you.</p>
                <blockquote><p>"Now that you are Israeli, it's your turn to build."</p></blockquote>
                <p><strong>Have a concept? Tell us about your project today.</strong></p>
            """,
            "category": "Aliyah & Entrepreneurship",
            "image_url": "https://israelgrowthventure.com/images/blog/olim-entrepreneur.jpg",
            "language": "en",
            "published": True,
            "tags": ["Aliyah", "Franchise", "Entrepreneur", "Olim", "Business"],
            "author": "IGV Team",
            "views": 0,
            "group_slug": "alyah-franchise-entrepreneur",
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
        # ============ HEBREW ============
        {
            "title": "לעלות לישראל כיזם-זכיין: המדריך המלא לעולים",
            "slug": "alyah-franchise-entrepreneur-he",
            "excerpt": "עזבתם את פריז לחיפה עם המזוודות והרעיון העסקי שלכם. הנה המפתחות להצליח בהקמת הזיכיון בישראל כבר מהשנה הראשונה.",
            "content": """
                <h2>מ-CDG-TLV לחנות הראשונה שלכם</h2>
                <p>מדי שנה עולים מאות יזמים דוברי צרפתית לישראל דרך שדה התעופה בן גוריון או נמל חיפה עם חזון ברור: לשחזר בישראל את המודל העסקי שעבד בצרפת. רשת מסעדות, קונספט קמעונאי, שירות אישי... החלום שם. המציאות, לעומת זאת, דורשת הכנה רצינית.</p>
                <h3>1. להכיר את השוק הישראלי לפני הכל</h3>
                <p>ישראל אינה צרפת עם שמש. הצרכן הישראלי תובעני, מחובר לרשת ולא מהסס להשוות מחירים בזמן אמת. הוא מצפה לחוויה, לא רק למוצר. הקונספט שלכם חייב להיות מותאם, לא רק מתורגם.</p>
                <ul>
                    <li><strong>המחיר חשוב</strong> אך האיכות קובעת — הצרכן ישלם יותר עבור מה שבאמת שווה</li>
                    <li><strong>מהירות השירות</strong> אינה ניתנת למשא ומתן בקמעונאות המזון</li>
                    <li><strong>נוכחות דיגיטלית</strong>: חוות דעת ב-Google ו-Waze נקראות לפני כל ביקור</li>
                </ul>
                <h3>2. מעמד עולה חדש: היתרונות המיסויים שלכם</h3>
                <p>כעולה חדש, אתם נהנים מפטורים ממס משמעותיים למשך 10 שנים על הכנסות ממקורות זרים. יתרונות אלה הם מנוף אמיתי למימון ההקמה הראשונית ולהפחתת לחץ תזרים המזומנים.</p>
                <h3>3. בחירת העיר הנכונה</h3>
                <p>תל אביב, ירושלים, חיפה או הערים החדשות בפריפריה? לכל שוק הדינמיקה שלו:</p>
                <ul>
                    <li><strong>תל אביב</strong>: כוח קנייה גבוה, תחרות עזה, שכירות יקרה</li>
                    <li><strong>ירושלים</strong>: לקוחות מגוונים, תנועת תיירים משמעותית</li>
                    <li><strong>חיפה</strong>: עיר בשינוי, שכירות סבירה, לקוחות מקומיים נאמנים</li>
                    <li><strong>פריפריה</strong>: פחות תחרות, תמיכה ממשלתית, צמיחה דמוגרפית</li>
                </ul>
                <h3>4. ליווי IGV: מהרעיון ליום הפתיחה</h3>
                <p>המשימה שלנו היא להפוך את הניסיון הצרפתי שלכם להצלחה ישראלית. מאימות הקונספט ועד להכשרת הצוות המקומי והליכי המנהל, אנו מנהלים כל שלב לצידכם.</p>
                <blockquote><p>« עכשיו אתה הישראלי. הגיע תורך לבנות. »</p></blockquote>
                <p><strong>יש לכם קונספט? ספרו לנו על הפרויקט שלכם היום.</strong></p>
            """,
            "category": "עלייה ויזמות",
            "image_url": "https://israelgrowthventure.com/images/blog/olim-entrepreneur.jpg",
            "language": "he",
            "published": True,
            "tags": ["עלייה", "זיכיון", "יזם", "עולים", "עסקים"],
            "author": "צוות IGV",
            "views": 0,
            "group_slug": "alyah-franchise-entrepreneur",
            "created_at": now,
            "updated_at": now,
            "published_at": now
        },
    ]

    result = await db.blog_articles.insert_many(articles)

    return {
        "success": True,
        "message": f"{len(result.inserted_ids)} articles created (1 FR + 1 EN + 1 HE)",
        "seeded": len(result.inserted_ids)
    }
