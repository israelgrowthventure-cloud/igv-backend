# Tests d'integration complets - Backend IGV
# Date: 2026-01-27
# PowerShell version

$API_URL = "https://igv-backend.onrender.com"

Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "   Tests Backend IGV - Validation Complete" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""

$PASSED = 0
$FAILED = 0

# Fonction pour tester une route
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Endpoint,
        [hashtable]$Headers = @{},
        [string]$Body = $null
    )
    
    Write-Host -NoNewline "Testing $Name... "
    
    try {
        $params = @{
            Uri = "$API_URL$Endpoint"
            Method = $Method
            Headers = $Headers
            ErrorAction = 'Stop'
        }
        
        if ($Body) {
            $params['Body'] = $Body
            $params['ContentType'] = 'application/json'
        }
        
        $response = Invoke-WebRequest @params
        
        if ($response.StatusCode -in 200..299) {
            Write-Host "✅ OK ($($response.StatusCode))" -ForegroundColor Green
            return $true
        } else {
            Write-Host "❌ FAILED ($($response.StatusCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ FAILED ($($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

# 1. Health Check
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "1. Health and Status Checks" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

if (Test-Endpoint -Name "Health check" -Method "GET" -Endpoint "/health") {
    $PASSED++
} else {
    $FAILED++
}

# 2. Test Auth (Login Admin)
Write-Host ""
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "2. Authentication" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

Write-Host -NoNewline "Testing admin login... "

$loginBody = @{
    email = "postmaster@israelgrowthventure.com"
    password = "Admin@igv2025#"
} | ConvertTo-Json

try {
    $loginResponse = Invoke-RestMethod -Uri "$API_URL/api/auth/login" -Method POST -Body $loginBody -ContentType "application/json"
    $TOKEN = $loginResponse.access_token
    
    if ($TOKEN) {
        Write-Host "✅ OK (Token received)" -ForegroundColor Green
        $PASSED++
    } else {
        Write-Host "❌ FAILED (No token)" -ForegroundColor Red
        $FAILED++
    }
} catch {
    Write-Host "❌ FAILED ($($_.Exception.Message))" -ForegroundColor Red
    $TOKEN = $null
    $FAILED++
}

# 3. Test Routes CRM (Public - Creation lead)
Write-Host ""
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "3. CRM Routes (Public)" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

$leadBody = @{
    email = "test-validation@example.com"
    brand_name = "Test Validation Brand"
    name = "Test Contact"
    phone = "+33123456789"
    sector = "restauration"
    language = "fr"
} | ConvertTo-Json

Write-Host -NoNewline "Testing create lead... "
try {
    $response = Invoke-RestMethod -Uri "$API_URL/api/crm/leads" -Method POST -Body $leadBody -ContentType "application/json"
    Write-Host "✅ OK" -ForegroundColor Green
    $PASSED++
} catch {
    Write-Host "❌ FAILED ($($_.Exception.Message))" -ForegroundColor Red
    $FAILED++
}

# 4. Test Routes CRM (Protected)
Write-Host ""
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "4. CRM Routes (Protected)" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

if ($TOKEN) {
    $authHeaders = @{
        Authorization = "Bearer $TOKEN"
    }
    
    if (Test-Endpoint -Name "Get leads list" -Method "GET" -Endpoint "/api/crm/leads" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
    
    if (Test-Endpoint -Name "Get contacts list" -Method "GET" -Endpoint "/api/crm/contacts" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
    
    if (Test-Endpoint -Name "Get opportunities list" -Method "GET" -Endpoint "/api/crm/opportunities" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
} else {
    Write-Host "⚠️  Skipping protected routes (no token)" -ForegroundColor Yellow
    $FAILED += 3
}

# 5. Test Routes CMS
Write-Host ""
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "5. CMS Routes" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

if ($TOKEN) {
    $authHeaders = @{
        Authorization = "Bearer $TOKEN"
    }
    
    if (Test-Endpoint -Name "CMS pages list" -Method "GET" -Endpoint "/api/pages/list" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
    
    if (Test-Endpoint -Name "Get home page (FR)" -Method "GET" -Endpoint "/api/pages/home?language=fr" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
    
    if (Test-Endpoint -Name "Get home page (EN)" -Method "GET" -Endpoint "/api/pages/home?language=en" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
    
    if (Test-Endpoint -Name "Get home page (HE)" -Method "GET" -Endpoint "/api/pages/home?language=he" -Headers $authHeaders) {
        $PASSED++
    } else {
        $FAILED++
    }
} else {
    Write-Host "⚠️  Skipping CMS routes (no token)" -ForegroundColor Yellow
    $FAILED += 4
}

# 6. Test Routes Deprecated (doivent rediriger)
Write-Host ""
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow
Write-Host "6. Deprecated Routes (Redirection Check)" -ForegroundColor Yellow
Write-Host "---------------------------------------------------------------" -ForegroundColor Yellow

Write-Host -NoNewline "Testing /api/leads redirect... "
try {
    $response = Invoke-WebRequest -Uri "$API_URL/api/leads" -Method GET -MaximumRedirection 0 -ErrorAction SilentlyContinue
    if ($response.StatusCode -in 301, 302, 308) {
        Write-Host "✅ OK (Redirect detected: $($response.StatusCode))" -ForegroundColor Green
        $PASSED++
    } else {
        Write-Host "⚠️  Warning (Status: $($response.StatusCode))" -ForegroundColor Yellow
        $FAILED++
    }
} catch {
    if ($_.Exception.Response.StatusCode -in 301, 302, 308) {
        Write-Host "✅ OK (Redirect detected)" -ForegroundColor Green
        $PASSED++
    } else {
        Write-Host "⚠️  Warning (No redirect detected)" -ForegroundColor Yellow
        $FAILED++
    }
}

Write-Host -NoNewline "Testing /api/contacts redirect... "
try {
    $response = Invoke-WebRequest -Uri "$API_URL/api/contacts" -Method GET -MaximumRedirection 0 -ErrorAction SilentlyContinue
    if ($response.StatusCode -in 301, 302, 308) {
        Write-Host "✅ OK (Redirect detected: $($response.StatusCode))" -ForegroundColor Green
        $PASSED++
    } else {
        Write-Host "⚠️  Warning (Status: $($response.StatusCode))" -ForegroundColor Yellow
        $FAILED++
    }
} catch {
    if ($_.Exception.Response.StatusCode -in 301, 302, 308) {
        Write-Host "✅ OK (Redirect detected)" -ForegroundColor Green
        $PASSED++
    } else {
        Write-Host "⚠️  Warning (No redirect detected)" -ForegroundColor Yellow
        $FAILED++
    }
}

# Resume Final
Write-Host ""
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host "               RESULTATS DES TESTS" -ForegroundColor Cyan
Write-Host "===============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tests reussis  : $PASSED" -ForegroundColor Green
Write-Host "  Tests echoues  : $FAILED" -ForegroundColor Red
Write-Host ""

if ($FAILED -eq 0) {
    Write-Host "  Status: ALL TESTS PASSING" -ForegroundColor Green
    Write-Host ""
    Write-Host "===============================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "  Status: SOME TESTS FAILED" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "===============================================================" -ForegroundColor Cyan
    exit 1
}
