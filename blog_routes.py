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
    
    return {
        "success": True,
        "message": "Article created successfully",
        "article": article_doc
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
