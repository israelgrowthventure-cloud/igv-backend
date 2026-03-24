#!/usr/bin/env python3
"""
IGV Blog — Seed Script: expansion-israel-5-erreurs
====================================================
Reads content/blog/expansion-israel-5-erreurs.md (source of truth),
parses FR / HE / EN sections, converts Markdown to HTML,
then upserts content into the blog_articles MongoDB collection.

Rules:
- Only updates an article if its `content` field is empty ("" or missing).
- Never overwrites content modified via the CMS admin.
- Safe to run multiple times (idempotent).

Usage:
    python seed_expansion_israel.py

Requires:
    MONGODB_URI env var (same as server.py)
    pip install motor python-dotenv markdown
"""

import asyncio
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import markdown

load_dotenv()

# ── Config ─────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "igv_production")
SLUG = "expansion-israel-5-erreurs"
CONTENT_FILE = Path(__file__).parent / "content" / "blog" / f"{SLUG}.md"

ARTICLE_META = {
    "fr": {
        "title": "Expansion en Israël : 5 Erreurs à Éviter pour les Enseignes Internationales",
        "category": "EXPANSION",
        "excerpt": (
            "Israël est un marché attractif mais exigeant. "
            "Découvrez les 5 erreurs stratégiques les plus courantes des enseignes internationales "
            "et comment les éviter pour réussir votre implantation."
        ),
        "tags": ["expansion", "israel", "enseignes internationales", "erreurs", "marché israélien"],
    },
    "en": {
        "title": "Expanding in Israel: 5 Mistakes to Avoid for International Brands",
        "category": "EXPANSION",
        "excerpt": (
            "Israel is an attractive but demanding market. "
            "Discover the 5 most common strategic mistakes international brands make "
            "and how to avoid them to succeed in your expansion."
        ),
        "tags": ["expansion", "israel", "international brands", "mistakes", "israeli market"],
    },
    "he": {
        "title": "התרחבות בישראל: 5 טעויות שכיחות שיש להימנע מהן עבור מותגים בינלאומיים",
        "category": "התרחבות",
        "excerpt": (
            "ישראל היא שוק אטרקטיבי אך דורשני. "
            "גלו את 5 הטעויות האסטרטגיות הנפוצות ביותר של מותגים בינלאומיים "
            "וכיצד להימנע מהן כדי להצליח בהתרחבות שלכם."
        ),
        "tags": ["התרחבות", "ישראל", "מותגים בינלאומיים", "טעויות", "שוק ישראלי"],
    },
}

LANG_HEADERS = {
    "fr": "## **Français**",
    "he": "## **Hébreu**",
    "en": "## **English**",
}


def parse_language_sections(raw: str) -> dict:
    sections = {}
    positions = {}

    for lang, header in LANG_HEADERS.items():
        idx = raw.find(header)
        if idx == -1:
            print(f"❌ Section header not found: {header!r}")
            sys.exit(1)
        positions[lang] = idx

    sorted_langs = sorted(positions, key=lambda l: positions[l])

    for i, lang in enumerate(sorted_langs):
        start = positions[lang]
        end = positions[sorted_langs[i + 1]] if i + 1 < len(sorted_langs) else len(raw)
        block = raw[start:end]
        block = re.sub(r"^##\s+\*\*[^*]+\*\*\s*\n?", "", block, count=1)
        sections[lang] = block.strip()

    return sections


def md_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "nl2br"],
        output_format="html",
    )


async def seed(db):
    if not CONTENT_FILE.exists():
        print(f"❌ Content file not found: {CONTENT_FILE}")
        sys.exit(1)

    raw = CONTENT_FILE.read_text(encoding="utf-8")
    sections = parse_language_sections(raw)
    now = datetime.now(timezone.utc)
    seeded = 0
    skipped = 0

    for lang in ["fr", "en", "he"]:
        existing = await db.blog_articles.find_one({"slug": SLUG, "language": lang})
        if existing and existing.get("content"):
            print(f"  ⏭  [{lang}] Already has content — skipping (CMS-safe).")
            skipped += 1
            continue

        html = md_to_html(sections[lang])
        meta = ARTICLE_META[lang]

        if existing:
            await db.blog_articles.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "content": html,
                        "tags": meta["tags"],
                        "updated_at": now,
                    }
                },
            )
            print(f"  ✅ [{lang}] Content updated (was empty).")
        else:
            await db.blog_articles.insert_one(
                {
                    "title": meta["title"],
                    "slug": SLUG,
                    "excerpt": meta["excerpt"],
                    "content": html,
                    "category": meta["category"],
                    "image_url": "/images/blog/expansion-israel-5-erreurs.webp",
                    "language": lang,
                    "published": True,
                    "tags": meta["tags"],
                    "author": "IGV",
                    "views": 0,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": "system_seed",
                    "group_slug": SLUG,
                }
            )
            print(f"  ✅ [{lang}] Article inserted.")

        seeded += 1

    print(f"\nDone. {seeded} article(s) seeded, {skipped} skipped.")


async def main():
    if not MONGODB_URI:
        print("❌ MONGODB_URI not set. Add it to your .env file.")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]

    print(f"🔌 Connected to MongoDB — db: {DB_NAME}")
    print(f"📄 Reading: {CONTENT_FILE}")
    print(f"🎯 Slug: {SLUG}\n")

    try:
        await seed(db)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
