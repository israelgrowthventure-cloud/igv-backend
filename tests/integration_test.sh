#!/bin/bash
# Tests d'intégration complets - Backend IGV
# Date: 2026-01-27

API_URL="https://igv-cms-backend.onrender.com"

echo "╔══════════════════════════════════════════════════════╗"
echo "║   🧪 Tests Backend IGV - Validation Complète        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

PASSED=0
FAILED=0

# Fonction pour tester une route
test_endpoint() {
  local name=$1
  local method=$2
  local endpoint=$3
  local headers=$4
  local data=$5
  
  echo -n "Testing $name... "
  
  if [ "$method" = "GET" ]; then
    response=$(curl -s -w "\n%{http_code}" $headers "$API_URL$endpoint")
  else
    response=$(curl -s -w "\n%{http_code}" -X $method $headers -d "$data" "$API_URL$endpoint")
  fi
  
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | head -n-1)
  
  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
    echo "✅ OK ($http_code)"
    PASSED=$((PASSED + 1))
    return 0
  else
    echo "❌ FAILED ($http_code)"
    echo "   Response: $body"
    FAILED=$((FAILED + 1))
    return 1
  fi
}

# 1. Health Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Health & Status Checks"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "Health check" "GET" "/health" ""

# 2. Test Auth (Login Admin)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Authentication"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -n "Testing admin login... "
login_response=$(curl -s -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "postmaster@israelgrowthventure.com",
    "password": "Admin@igv2025#"
  }')

TOKEN=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  echo "✅ OK (Token received)"
  PASSED=$((PASSED + 1))
else
  echo "❌ FAILED (No token)"
  echo "   Response: $login_response"
  FAILED=$((FAILED + 1))
  TOKEN=""
fi

# 3. Test Routes CRM (Public - Création lead)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  CRM Routes (Public)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "Create lead" "POST" "/api/crm/leads" \
  "-H 'Content-Type: application/json'" \
  '{
    "email": "test-validation@example.com",
    "brand_name": "Test Validation Brand",
    "name": "Test Contact",
    "phone": "+33123456789",
    "sector": "restauration",
    "language": "fr"
  }'

# 4. Test Routes CRM (Protected)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  CRM Routes (Protected)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$TOKEN" ]; then
  test_endpoint "Get leads list" "GET" "/api/crm/leads" \
    "-H 'Authorization: Bearer $TOKEN'"
  
  test_endpoint "Get contacts list" "GET" "/api/crm/contacts" \
    "-H 'Authorization: Bearer $TOKEN'"
  
  test_endpoint "Get opportunities list" "GET" "/api/crm/opportunities" \
    "-H 'Authorization: Bearer $TOKEN'"
else
  echo "⚠️  Skipping protected routes (no token)"
  FAILED=$((FAILED + 3))
fi

# 5. Test Routes CMS
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  CMS Routes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$TOKEN" ]; then
  test_endpoint "CMS pages list" "GET" "/api/pages/list" \
    "-H 'Authorization: Bearer $TOKEN'"
  
  test_endpoint "Get home page (FR)" "GET" "/api/pages/home?language=fr" \
    "-H 'Authorization: Bearer $TOKEN'"
  
  test_endpoint "Get home page (EN)" "GET" "/api/pages/home?language=en" \
    "-H 'Authorization: Bearer $TOKEN'"
  
  test_endpoint "Get home page (HE)" "GET" "/api/pages/home?language=he" \
    "-H 'Authorization: Bearer $TOKEN'"
else
  echo "⚠️  Skipping CMS routes (no token)"
  FAILED=$((FAILED + 4))
fi

# 6. Test Routes Deprecated (doivent rediriger)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  Deprecated Routes (Redirection Check)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo -n "Testing /api/leads redirect... "
redirect_response=$(curl -s -i "$API_URL/api/leads" 2>&1 | grep -E "HTTP/.* (308|301|302)")
if [ -n "$redirect_response" ]; then
  echo "✅ OK (Redirect detected)"
  PASSED=$((PASSED + 1))
else
  echo "⚠️  Warning (No redirect detected)"
  FAILED=$((FAILED + 1))
fi

echo -n "Testing /api/contacts redirect... "
redirect_response=$(curl -s -i "$API_URL/api/contacts" 2>&1 | grep -E "HTTP/.* (308|301|302)")
if [ -n "$redirect_response" ]; then
  echo "✅ OK (Redirect detected)"
  PASSED=$((PASSED + 1))
else
  echo "⚠️  Warning (No redirect detected)"
  FAILED=$((FAILED + 1))
fi

# Résumé Final
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║               📊 RÉSULTATS DES TESTS                 ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  ✅ Tests réussis  : $PASSED                              ║"
echo "║  ❌ Tests échoués  : $FAILED                               ║"
echo "║                                                      ║"

if [ $FAILED -eq 0 ]; then
  echo "║  🎉 Status: ALL TESTS PASSING                       ║"
  echo "║                                                      ║"
  echo "╚══════════════════════════════════════════════════════╝"
  exit 0
else
  echo "║  ⚠️  Status: SOME TESTS FAILED                       ║"
  echo "║                                                      ║"
  echo "╚══════════════════════════════════════════════════════╝"
  exit 1
fi
