#!/usr/bin/env python
"""Test script to verify CRM routes are loaded correctly"""
import sys
sys.path.insert(0, '.')

from server import app

print("=" * 60)
print("CRM ROUTES CHECK - After removing crm_routes.py")
print("=" * 60)

crm_routes = []
for route in app.routes:
    if hasattr(route, 'path') and 'crm' in route.path.lower():
        methods = list(route.methods) if hasattr(route, 'methods') else []
        crm_routes.append((route.path, methods))

print(f"\nFound {len(crm_routes)} CRM routes:\n")
for path, methods in sorted(crm_routes):
    print(f"  {', '.join(methods):20} {path}")

# Check specific required routes
required = [
    '/api/crm/leads',
    '/api/crm/contacts', 
    '/api/crm/pipeline',
    '/api/crm/dashboard/stats'
]

print("\n" + "=" * 60)
print("REQUIRED ROUTES CHECK:")
print("=" * 60)
for r in required:
    found = any(path == r for path, _ in crm_routes)
    status = "✅ OK" if found else "❌ MISSING"
    print(f"  {status} {r}")

print("\n✅ Server loaded successfully with CRM Complete only")
