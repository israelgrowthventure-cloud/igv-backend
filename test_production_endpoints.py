"""
Test Production Endpoints - IGV Backend
========================================
Verification physique des endpoints en production
"""

import httpx
import asyncio

async def test_endpoints():
    base = "https://igv-backend.onrender.com"
    
    tests = {
        "Health Check": "/health",
        "CRM Opportunities": "/api/crm/opportunities",
        "CRM Pipeline": "/api/crm/pipeline",
        "CRM Activities": "/api/crm/activities",
        "CRM Users (Settings)": "/api/crm/settings/users",
        "CRM Dispatch": "/api/crm/settings/dispatch",
        "Admin Users": "/api/admin/users",
        "CMS Content": "/api/cms/content"
    }
    
    print("\nTEST DES ENDPOINTS EN PRODUCTION\n")
    print("="*70)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, endpoint in tests.items():
            try:
                res = await client.get(f"{base}{endpoint}")
                if res.status_code == 200:
                    status = "OK     "
                elif res.status_code == 401:
                    status = "AUTH   "
                else:
                    status = "ERROR  "
                
                print(f"{status} {name:30s} {endpoint:40s} -> {res.status_code}")
            except Exception as e:
                print(f"FAILED {name:30s} {endpoint:40s} -> {str(e)[:40]}")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
