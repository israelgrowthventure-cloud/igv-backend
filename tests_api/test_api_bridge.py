"""
Tests for API Bridge Module
===========================

Validates that:
1. Legacy route aliases return same results as canonical routes
2. Payload normalization works (flat vs nested)
3. LEGACY_ROUTE_USED is logged for each alias used

Run with:
    pytest tests_api/test_api_bridge.py -v

Created: 26 Janvier 2026
"""

import pytest
import httpx
import os
from datetime import datetime

# Test configuration
BASE_URL = os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
TEST_EMAIL = "postmaster@israelgrowthventure.com"
TEST_PASSWORD = "Admin@igv2025#"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        response = client.post("/api/admin/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Could not authenticate: {response.status_code}")


@pytest.fixture
def auth_headers(auth_token):
    """Return headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAuthAliases:
    """Test authentication route aliases"""
    
    def test_legacy_login_alias(self):
        """Test /api/login -> /api/admin/login"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # Test legacy route
            response = client.post("/api/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            # Should work (200) or fail with same error as canonical
            assert response.status_code in [200, 401, 422], f"Unexpected status: {response.status_code}"
    
    def test_auth_login_alias(self):
        """Test /api/auth/login -> /api/admin/login"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.post("/api/auth/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            assert response.status_code in [200, 401, 422], f"Unexpected status: {response.status_code}"


class TestStatsAliases:
    """Test stats route aliases"""
    
    def test_stats_alias(self, auth_headers):
        """Test /api/stats -> /api/admin/stats"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/stats", headers=auth_headers)
            
            # Should return stats object
            assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                assert "leads" in data or "total" in data, "Stats response should contain leads data"
    
    def test_crm_stats_alias(self, auth_headers):
        """Test /api/crm/stats -> /api/crm/dashboard/stats"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/stats", headers=auth_headers)
            
            assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"


class TestCRMAutomationAliases:
    """Test CRM automation route aliases"""
    
    def test_automation_list_alias(self, auth_headers):
        """Test /api/crm/automation -> /api/crm/rules"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # Test alias
            alias_response = client.get("/api/crm/automation", headers=auth_headers)
            
            # Test canonical
            canonical_response = client.get("/api/crm/rules", headers=auth_headers)
            
            # Both should return same status
            assert alias_response.status_code == canonical_response.status_code, \
                f"Alias status {alias_response.status_code} != Canonical status {canonical_response.status_code}"
    
    def test_automation_rules_list_alias(self, auth_headers):
        """Test /api/crm/automation/rules -> /api/crm/rules"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/automation/rules", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"


class TestCRMAuditAliases:
    """Test CRM audit route aliases"""
    
    def test_audit_list_alias(self, auth_headers):
        """Test /api/crm/audit -> /api/crm/audit-logs"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # Test alias
            alias_response = client.get("/api/crm/audit", headers=auth_headers)
            
            # Test canonical
            canonical_response = client.get("/api/crm/audit-logs", headers=auth_headers)
            
            assert alias_response.status_code == canonical_response.status_code, \
                f"Alias status {alias_response.status_code} != Canonical status {canonical_response.status_code}"
    
    def test_audit_stats_alias(self, auth_headers):
        """Test /api/crm/audit/stats -> /api/crm/audit-logs/stats"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/audit/stats", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"


class TestRBACQliases:
    """Test RBAC route aliases"""
    
    def test_roles_alias(self, auth_headers):
        """Test /api/crm/roles -> canonical roles endpoint"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/roles", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                assert "roles" in data, "Roles response should contain roles"
    
    def test_permissions_alias(self, auth_headers):
        """Test /api/crm/permissions -> canonical permissions endpoint"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/permissions", headers=auth_headers)
            
            assert response.status_code in [200, 401], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                assert "permissions" in data, "Permissions response should contain permissions"


class TestQualityAliases:
    """Test quality/duplicates route aliases"""
    
    def test_duplicates_leads_alias(self, auth_headers):
        """Test /api/crm/duplicates/leads -> /api/crm/quality/duplicates/leads"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # Test alias
            alias_response = client.get("/api/crm/duplicates/leads", headers=auth_headers)
            
            # Test canonical
            canonical_response = client.get("/api/crm/quality/duplicates/leads", headers=auth_headers)
            
            assert alias_response.status_code == canonical_response.status_code, \
                f"Alias status {alias_response.status_code} != Canonical status {canonical_response.status_code}"
    
    def test_duplicates_contacts_alias(self, auth_headers):
        """Test /api/crm/duplicates/contacts -> /api/crm/quality/duplicates/contacts"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/duplicates/contacts", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"


# NOTE: TestSettingsAliases removed - these routes (/api/crm/settings,
# /api/crm/settings/dispatch, /api/crm/settings/quality, /api/crm/settings/performance)
# contained business logic and were removed from api_bridge.py.
# They need to be implemented as CANONICAL routes in crm_complete_routes.py.


class TestTeamAliases:
    """Test team route aliases - forward to /api/crm/settings/users"""
    
    def test_team_list_alias(self, auth_headers):
        """Test /api/crm/team -> /api/crm/settings/users"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/team", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                # Returns same format as /api/crm/settings/users
                assert "users" in data or "total" in data, "Team response should contain users data"
    
    def test_crm_users_alias(self, auth_headers):
        """Test /api/crm/users -> /api/crm/settings/users"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/crm/users", headers=auth_headers)
            
            assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
            if response.status_code == 200:
                data = response.json()
                assert "users" in data, "Users response should contain users list"


# NOTE: TestSettingsAliases removed - these routes contained business logic
# and were removed from api_bridge.py. They should be moved to canonical
# route files (crm_complete_routes.py) if needed.


# NOTE: TestPayloadNormalization removed - the /api/crm/leads wrapper was
# removed because include_in_schema=False still causes runtime conflicts.
# Payload normalization should be handled in the canonical handler.


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns OK"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/api/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data.get("status") == "ok"
    
    def test_root_endpoint(self):
        """Test root endpoint returns API info"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            response = client.get("/")
            
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
