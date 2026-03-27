#!/usr/bin/env python3
"""
IGV Blog Articles Seed Script
==============================
Reads content/blog/alyah-franchise-entrepreneur.md (source of truth),
parses FR / HE / EN sections, converts Markdown to HTML,
then upserts content into the blog_articles MongoDB collection.

Rules:
- Only updates an article if its `content` field is empty ("" or missing).
- Never overwrites content modified via the CMS admin.
- Safe to run multiple times (idempotent).

Usage:
    python seed_blog_articles.py

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
SLUG = "alyah-franchise-entrepreneur"
CONTENT_FILE = Path(__file__).parent / "content" / "blog" / f"{SLUG}.md"

ARTICLE_META = {
    "fr": {
        "title": "Olim Hadashim : votre alyah, une aventure professionnelle à écrire",
        "category": "ALYAH PRO",
        "excerpt": (
            "De la blague sur le bateau à la success story : comment les olim "
            "entrepreneurs transforment leur alyah en carrière réussie en Israël."
        ),
        "tags": ["alyah", "entrepreneur", "israel", "installation professionnelle", "olim hadashim"],
    },
    "en": {
        "title": "Olim Hadashim: your aliyah, a professional adventure to write",
        "category": "ALYAH PRO",
        "excerpt": (
            "From the joke on the boat to the success story: how entrepreneur olim "
            "transform their aliyah into a successful career in Israel."
        ),
        "tags": ["alyah", "entrepreneur", "israel", "professional integration", "olim hadashim"],
    },
    "he": {
        "title": "עולים חדשים: עלייתכם – הרפתקה מקצועית לכתיבה",
        "category": "עלייה פרו",
        "excerpt": (
            "מהבדיחה על הסיפון לסיפור ההצלחה: כיצד יזמים עולים הופכים את עלייתם "
            "לקריירה מצליחה בישראל."
        ),
        "tags": ["עלייה", "יזם", "ישראל", "התבססות מקצועית", "עולים חדשים"],
    },
}

# Language section headers as they appear in the Markdown file
LANG_HEADERS = {
    "fr": "## **Français**",
    "he": "## **Hébreu**",
    "en": "## **English**",
}

# Order defines parsing boundaries
LANG_ORDER = ["fr", "he", "en"]


def parse_language_sections(raw: str) -> dict[str, str]:
    """
    Split the Markdown file into per-language blocks based on the
    ## **Français** / ## **Hébreu** / ## **English** section headers.
    Returns {"fr": "<md text>", "he": "<md text>", "en": "<md text>"}.
    """
    sections = {}
    positions = {}

    for lang, header in LANG_HEADERS.items():
        idx = raw.find(header)
        if idx == -1:
            print(f"❌ Section header not found: {header!r}")
            sys.exit(1)
        positions[lang] = idx

    # Sort by position so we know the boundaries
    sorted_langs = sorted(positions, key=lambda l: positions[l])

    for i, lang in enumerate(sorted_langs):
        start = positions[lang]
        end = positions[sorted_langs[i + 1]] if i + 1 < len(sorted_langs) else len(raw)
        # Strip the section header line itself
        block = raw[start:end]
        block = re.sub(r"^##\s+\*\*[^*]+\*\*\s*\n?", "", block, count=1)
        sections[lang] = block.strip()

    return sections


def md_to_html(md_text: str) -> str:
    """Convert Markdown text to HTML using the markdown library."""
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
            # Shell exists with empty content — fill it in
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
            # No document at all — insert full article
            await db.blog_articles.insert_one(
                {
                    "title": meta["title"],
                    "slug": SLUG,
                    "excerpt": meta["excerpt"],
                    "content": html,
                    "category": meta["category"],
                    "image_url": "/images/blog/olim-entrepreneur.webp",
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
