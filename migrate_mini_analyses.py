"""
Migration script to create leads from existing mini-analyses
Run this ONCE to migrate the 40+ mini-analyses to the CRM leads collection
"""
import sys
import os

# Add parent directory to path to import server modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
mongo_url = os.getenv('MONGODB_URI') or os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME', 'igv_production')

mongo_client = None
db = None

def get_db():
    """Lazy initialization of MongoDB connection"""
    global mongo_client, db
    if db is None and mongo_url:
        mongo_client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000
        )
        db = mongo_client[db_name]
    return db

logging.basicConfig(level=logging.INFO)

async def migrate_mini_analyses_to_leads():
    """
    Migrate existing mini-analyses to leads collection
    Creates a lead for each mini-analysis that doesn't already have one
    """
    
    current_db = get_db()
    
    if current_db is None:
        print("[ERROR] Database not configured - cannot migrate")
        return {"error": "Database not available"}
    
    # Count existing data
    mini_count = await current_db.mini_analyses.count_documents({})
    leads_count = await current_db.leads.count_documents({})
    
    print(f"\n[BEFORE MIGRATION]")
    print(f"Mini-analyses: {mini_count}")
    print(f"Leads: {leads_count}")
    
    # Find mini-analyses without corresponding leads
    migrated = 0
    skipped = 0
    errors = 0
    
    cursor = current_db.mini_analyses.find({})
    async for analysis in cursor:
        email = analysis.get('email')
        brand_name = analysis.get('brand_name')
        
        if not email or not brand_name:
            print(f"[SKIP] Missing email or brand: {analysis.get('_id')}")
            skipped += 1
            continue
        
        # Check if lead already exists
        existing_lead = await current_db.leads.find_one({
            "email": email,
            "brand_name": brand_name
        })
        
        if existing_lead:
            skipped += 1
            continue
        
        # Create lead from mini-analysis data
        try:
            lead_record = {
                "email": email,
                "phone": analysis.get('phone', ''),
                "brand_name": brand_name,
                "sector": analysis.get('payload_form', {}).get('secteur', analysis.get('sector', 'Unknown')),
                "language": analysis.get('language', 'fr'),
                "status": "GENERATED",  # Analysis already generated
                "source": "mini-analysis-migration",
                "assigned_to": None,
                "created_at": analysis.get('created_at', datetime.now(timezone.utc)),
                "updated_at": datetime.now(timezone.utc),
                "mini_analysis_id": str(analysis.get('_id')),
                "pdf_url": analysis.get('pdf_url'),
                "analysis_text": analysis.get('response_text', '')[:500],  # First 500 chars
                "request_count": 1,
                "notes": f"Migrated from mini-analysis collection on {datetime.now(timezone.utc).isoformat()}"
            }
            
            result = await current_db.leads.insert_one(lead_record)
            migrated += 1
            
            if migrated <= 5:  # Show first 5
                print(f"[MIGRATED] {brand_name} | {email}")
            
        except Exception as e:
            print(f"[ERROR] Failed to create lead for {brand_name}: {str(e)}")
            errors += 1
    
    # Final count
    final_leads_count = await current_db.leads.count_documents({})
    
    print(f"\n[AFTER MIGRATION]")
    print(f"Leads created: {migrated}")
    print(f"Skipped (already exist): {skipped}")
    print(f"Errors: {errors}")
    print(f"Total leads now: {final_leads_count}")
    
    return {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "final_count": final_leads_count
    }

if __name__ == "__main__":
    print("="*60)
    print("MIGRATION: Mini-Analyses -> CRM Leads")
    print("="*60)
    
    result = asyncio.run(migrate_mini_analyses_to_leads())
    
    print("\n" + "="*60)
    print("[MIGRATION COMPLETE]")
    print("="*60)
    print(f"Total migrated: {result.get('migrated', 0)}")
    print(f"Check /admin/crm/prospects to see the leads!")
    print("="*60)
