"""
Tests Minimaux API Bridge - Vérification routes non-404
========================================================

Test que les routes legacy ne retournent pas 404 (routing OK).

Run avec:
    pytest tests_api/test_api_bridge_minimal.py -v

Created: 26 Janvier 2026
"""

import pytest
import httpx
import os

# Test configuration
BASE_URL = os.getenv("TEST_BACKEND_URL", "https://igv-cms-backend.onrender.com")
TEST_EMAIL = "postmaster@israelgrowthventure.com"
TEST_PASSWORD = "Admin@igv2025#"


class TestBridgeRoutesNotFound:
    """Test que les routes legacy existent (pas 404)"""
    
    def test_api_login_not_404(self):
        """Test /api/login route existe"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # On s'attend à 200 ou 401/422 (validation), mais PAS 404
            response = client.post("/api/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            assert response.status_code != 404, \
                f"/api/login returned 404 - route not registered"
            # Vérifie que c'est soit success, soit auth error, soit validation error
            assert response.status_code in [200, 401, 422, 500], \
                f"Unexpected status: {response.status_code}"
    
    def test_api_stats_not_404(self):
        """Test /api/stats route existe"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # D'abord on login pour avoir un token
            login_resp = client.post("/api/admin/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if login_resp.status_code != 200:
                pytest.skip(f"Could not login: {login_resp.status_code}")
            
            token = login_resp.json().get("access_token") or login_resp.json().get("token")
            if not token:
                pytest.skip("No token in login response")
            
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/stats", headers=headers)
            
            assert response.status_code != 404, \
                f"/api/stats returned 404 - route not registered"
            assert response.status_code in [200, 401, 403, 500], \
                f"Unexpected status: {response.status_code}"
    
    def test_api_crm_stats_not_404(self):
        """Test /api/crm/stats route existe"""
        with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
            # D'abord on login pour avoir un token
            login_resp = client.post("/api/admin/login", json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            })
            
            if login_resp.status_code != 200:
                pytest.skip(f"Could not login: {login_resp.status_code}")
            
            token = login_resp.json().get("access_token") or login_resp.json().get("token")
            if not token:
                pytest.skip("No token in login response")
            
            headers = {"Authorization": f"Bearer {token}"}
            response = client.get("/api/crm/stats", headers=headers)
            
            assert response.status_code != 404, \
                f"/api/crm/stats returned 404 - route not registered"
            assert response.status_code in [200, 401, 403, 500], \
                f"Unexpected status: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
