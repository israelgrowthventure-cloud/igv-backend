#!/usr/bin/env python3
"""
Test Import - Vérification que tous les modules se chargent sans erreur
Created: 28 Janvier 2026
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)

def test_imports():
    """Test que tous les routers peuvent être importés"""
    errors = []
    
    print("🔍 Test des imports des modules...")
    print("="*60)
    
    # Test tasks_routes
    try:
        from tasks_routes import router as tasks_router
        print("✅ tasks_routes importé avec succès")
    except Exception as e:
        errors.append(f"tasks_routes: {e}")
        print(f"❌ tasks_routes: {e}")
    
    # Test client_routes
    try:
        from client_routes import router as client_router
        print("✅ client_routes importé avec succès")
    except Exception as e:
        errors.append(f"client_routes: {e}")
        print(f"❌ client_routes: {e}")
    
    # Test server
    try:
        import server
        print("✅ server.py importé avec succès")
    except Exception as e:
        errors.append(f"server: {e}")
        print(f"❌ server: {e}")
    
    print("="*60)
    
    if errors:
        print(f"\n❌ {len(errors)} erreur(s) détectée(s):")
        for err in errors:
            print(f"  - {err}")
        return 1
    else:
        print("\n✅ TOUS LES MODULES SE CHARGENT CORRECTEMENT")
        return 0

if __name__ == "__main__":
    sys.exit(test_imports())
