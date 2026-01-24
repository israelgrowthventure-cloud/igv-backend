"""Quick public endpoint tests"""
import requests
import json

BASE_URL = 'https://igv-cms-backend.onrender.com'

print("=" * 50)
print("IGV API Public Endpoint Tests")
print("=" * 50)

# Test 1: Health
print('\nT00_Health...')
try:
    r = requests.get(f'{BASE_URL}/api/health', timeout=30)
    data = r.json()
    status = 'PASS' if r.status_code == 200 and data.get('status') == 'ok' else 'FAIL'
    print(f'  [{status}] MongoDB: {data.get("mongodb")}, DB: {data.get("db")}')
except Exception as e:
    print(f'  [FAIL] {e}')

# Test 2: Diag Gemini
print('\nT00b_DiagGemini...')
try:
    r = requests.get(f'{BASE_URL}/api/diag-gemini', timeout=30)
    data = r.json()
    status = 'PASS' if r.status_code == 200 else 'FAIL'
    print(f'  [{status}] Status: {r.status_code}, Gemini configured: {data.get("gemini_configured", "N/A")}')
except Exception as e:
    print(f'  [FAIL] {e}')

# Test 3: Login with wrong creds (should return 401)
print('\nT01_LoginWrongCreds...')
try:
    r = requests.post(f'{BASE_URL}/api/admin/login', json={'email': 'test@test.com', 'password': 'wrong'}, timeout=30)
    status = 'EXPECTED' if r.status_code == 401 else 'UNEXPECTED'
    print(f'  [{status}] Status: {r.status_code} (401 expected for wrong creds)')
except Exception as e:
    print(f'  [FAIL] {e}')

# Test 4: CRM without auth (should return 401/403)
print('\nT02_CRMNoAuth...')
try:
    r = requests.get(f'{BASE_URL}/api/crm/leads', timeout=30)
    status = 'EXPECTED' if r.status_code in [401, 403] else 'UNEXPECTED'
    print(f'  [{status}] Status: {r.status_code} (401/403 expected without auth)')
except Exception as e:
    print(f'  [FAIL] {e}')

print("\n" + "=" * 50)
print("Public tests complete. For authenticated tests:")
print("Set TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD env vars")
print("Then run: python test_crm_full.py")
print("=" * 50)
