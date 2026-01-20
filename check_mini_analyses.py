"""
Script to check existing mini-analyses and leads in MongoDB
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime

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

async def check_data():
    """Check mini-analyses and leads collections"""
    
    # MongoDB connection
    current_db = get_db()
    if current_db is None:
        print("[ERROR] MONGODB_URI not configured")
        return {
            "mini_analyses_count": 0,
            "leads_count": 0,
            "missing_leads_count": 0,
            "missing_leads": []
        }
    
    # Count mini-analyses
    mini_analyses_count = await current_db.mini_analyses.count_documents({})
    print(f"\n[INFO] Mini-analyses existantes: {mini_analyses_count}")
    
    # Show sample mini-analyses
    if mini_analyses_count > 0:
        print("\n[SAMPLE] Mini-analyses:")
        cursor = current_db.mini_analyses.find({}).limit(5)
        async for analysis in cursor:
            created = analysis.get('created_at', 'N/A')
            email = analysis.get('email', 'N/A')
            brand = analysis.get('brand_name', 'N/A')
            phone = analysis.get('phone', 'N/A')
            print(f"  - {brand} | {email} | {phone} | {created}")
    
    # Count leads
    leads_count = await current_db.leads.count_documents({})
    print(f"\n[INFO] Leads existants: {leads_count}")
    
    # Show sample leads
    if leads_count > 0:
        print("\n[SAMPLE] Leads:")
        cursor = current_db.leads.find({}).limit(5)
        async for lead in cursor:
            created = lead.get('created_at', 'N/A')
            email = lead.get('email', 'N/A')
            brand = lead.get('brand_name', 'N/A')
            status = lead.get('status', 'N/A')
            print(f"  - {brand} | {email} | {status} | {created}")
    
    # Check for mini-analyses without corresponding leads
    print("\n[CHECK] Recherche de mini-analyses sans leads correspondants...")
    
    missing_leads = []
    cursor = current_db.mini_analyses.find({})
    async for analysis in cursor:
        email = analysis.get('email')
        brand_name = analysis.get('brand_name')
        
        if email and brand_name:
            # Check if lead exists
            lead = await current_db.leads.find_one({
                "email": email,
                "brand_name": brand_name
            })
            
            if not lead:
                missing_leads.append({
                    "email": email,
                    "brand_name": brand_name,
                    "phone": analysis.get('phone'),
                    "created_at": analysis.get('created_at'),
                    "analysis_id": str(analysis.get('_id'))
                })
    
    print(f"\n[WARNING] Mini-analyses sans leads: {len(missing_leads)}")
    
    if missing_leads:
        print("\n[TO MIGRATE] Details:")
        for item in missing_leads[:10]:  # Show first 10
            print(f"  - {item['brand_name']} | {item['email']} | {item.get('phone', 'N/A')}")
        
        if len(missing_leads) > 10:
            print(f"  ... et {len(missing_leads) - 10} autres")
    
    return {
        "mini_analyses_count": mini_analyses_count,
        "leads_count": leads_count,
        "missing_leads_count": len(missing_leads),
        "missing_leads": missing_leads
    }

if __name__ == "__main__":
    result = asyncio.run(check_data())
    
    print("\n" + "="*60)
    print("[SUMMARY]")
    print("="*60)
    print(f"Mini-analyses totales: {result['mini_analyses_count']}")
    print(f"Leads totaux: {result['leads_count']}")
    print(f"Mini-analyses sans leads: {result['missing_leads_count']}")
    print("="*60)
