"""
migrate_blog_groups.py — One-time migration
Sets group_slug on the 9 seeded blog articles so the language switcher
can find the correct translation slug per language.

Usage:
  python migrate_blog_groups.py

Requires MONGO_URL env var (or .env file).
"""
import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL") or os.getenv("MONGODB_URL")
DB_NAME = os.getenv("DB_NAME", "igv_cms")

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


async def migrate():
    if not MONGO_URL:
        print("ERROR: MONGO_URL not set")
        return

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    total = 0
    for group_slug, slugs in GROUPS:
        print(f"\nGroup: {group_slug}")
        for slug in slugs:
            result = await db.blog_articles.update_many(
                {"slug": slug},
                {"$set": {"group_slug": group_slug}}
            )
            print(f"  {slug} → modified: {result.modified_count}")
            total += result.modified_count

    print(f"\nDone. {total} articles updated.")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
