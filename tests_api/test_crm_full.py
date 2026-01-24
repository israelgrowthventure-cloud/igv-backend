#!/usr/bin/env python3
"""
IGV CRM API Tests - Full Test Suite
Tests all critical CRM functionality against production backend

Usage:
    python test_crm_full.py [--base-url URL] [--email EMAIL] [--password PASSWORD]
    
Environment variables:
    TEST_ADMIN_EMAIL - Admin email for login
    TEST_ADMIN_PASSWORD - Admin password
    BACKEND_URL - Backend URL (default: https://igv-cms-backend.onrender.com)
"""

import requests
import json
import time
import uuid
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "https://igv-cms-backend.onrender.com")
ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "")

# Test state
class TestState:
    token: Optional[str] = None
    test_lead_id: Optional[str] = None
    test_note_id: Optional[str] = None
    results: list = []

state = TestState()

# Colors for output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

def log_result(test_name: str, passed: bool, details: str = "", response_data: Any = None):
    """Log test result with formatting"""
    status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
    print(f"\n{Colors.BOLD}[{test_name}]{Colors.RESET} {status}")
    if details:
        print(f"  Details: {details}")
    if response_data and not passed:
        print(f"  Response: {json.dumps(response_data, indent=2, default=str)[:500]}")
    
    state.results.append({
        "test": test_name,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    })

def make_request(method: str, endpoint: str, data: Dict = None, auth: bool = True) -> Tuple[int, Any]:
    """Make HTTP request with optional auth"""
    headers = {"Content-Type": "application/json"}
    if auth and state.token:
        headers["Authorization"] = f"Bearer {state.token}"
    
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            resp = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, json=data, headers=headers, timeout=30)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers, timeout=30)
        elif method == "PATCH":
            resp = requests.patch(url, json=data, headers=headers, timeout=30)
        else:
            return 0, {"error": f"Unknown method: {method}"}
        
        try:
            return resp.status_code, resp.json()
        except:
            return resp.status_code, {"raw": resp.text[:500]}
    except requests.exceptions.Timeout:
        return 0, {"error": "Request timeout"}
    except requests.exceptions.RequestException as e:
        return 0, {"error": str(e)}

# ==========================================
# TEST FUNCTIONS
# ==========================================

def test_health():
    """T00: Health check"""
    status, data = make_request("GET", "/api/health", auth=False)
    passed = status == 200 and data.get("status") == "ok"
    log_result("T00_Health", passed, f"Status={status}, MongoDB={data.get('mongodb')}", data)
    return passed

def test_login():
    """T01: Admin login"""
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        log_result("T01_Login", False, "Missing credentials. Set TEST_ADMIN_EMAIL and TEST_ADMIN_PASSWORD")
        return False
    
    status, data = make_request("POST", "/api/admin/login", {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }, auth=False)
    
    passed = status == 200 and "access_token" in data
    if passed:
        state.token = data["access_token"]
        log_result("T01_Login", True, f"Role={data.get('role')}, Email={data.get('email')}")
    else:
        log_result("T01_Login", False, f"Status={status}", data)
    return passed

def test_verify_token():
    """T01b: Verify token"""
    status, data = make_request("GET", "/api/admin/verify")
    passed = status == 200 and "email" in data
    log_result("T01b_VerifyToken", passed, f"Email={data.get('email')}, Role={data.get('role')}", data)
    return passed

def test_get_leads():
    """T02: Get leads list"""
    status, data = make_request("GET", "/api/crm/leads")
    passed = status == 200 and "leads" in data
    total = data.get("total", 0) if isinstance(data, dict) else 0
    leads = data.get("leads", []) if isinstance(data, dict) else []
    
    # Store first lead ID for later tests
    if leads and len(leads) > 0:
        state.test_lead_id = leads[0].get("_id") or leads[0].get("lead_id")
    
    log_result("T02_GetLeads", passed, f"Total={total}, FirstLeadID={state.test_lead_id}", 
               data if not passed else None)
    return passed

def test_get_lead_detail():
    """T03: Get lead detail"""
    if not state.test_lead_id:
        log_result("T03_GetLeadDetail", False, "No lead ID available from previous test")
        return False
    
    status, data = make_request("GET", f"/api/crm/leads/{state.test_lead_id}")
    passed = status == 200 and ("_id" in data or "lead_id" in data)
    
    notes_count = len(data.get("notes", [])) if isinstance(data, dict) else 0
    activities_count = len(data.get("activities", [])) if isinstance(data, dict) else 0
    
    log_result("T03_GetLeadDetail", passed, 
               f"Lead={data.get('email', 'N/A')}, Notes={notes_count}, Activities={activities_count}",
               data if not passed else None)
    return passed

def test_add_note():
    """T04a: Add note to lead"""
    if not state.test_lead_id:
        log_result("T04a_AddNote", False, "No lead ID available")
        return False
    
    test_note_content = f"Test note from automated API test - {datetime.now().isoformat()}"
    
    status, data = make_request("POST", f"/api/crm/leads/{state.test_lead_id}/notes", {
        "note_text": test_note_content,
        "content": test_note_content
    })
    
    passed = status in [200, 201] and "message" in data
    log_result("T04a_AddNote", passed, f"Status={status}, Response={data.get('message', 'N/A')}", 
               data if not passed else None)
    return passed

def test_get_notes_persistence():
    """T04b: Verify note persistence - GET notes and check last note exists"""
    if not state.test_lead_id:
        log_result("T04b_NotesPersistence", False, "No lead ID available")
        return False
    
    # Wait a bit for DB write
    time.sleep(1)
    
    status, data = make_request("GET", f"/api/crm/leads/{state.test_lead_id}/notes")
    
    if status != 200:
        log_result("T04b_NotesPersistence", False, f"Failed to fetch notes, status={status}", data)
        return False
    
    notes = data.get("notes", []) if isinstance(data, dict) else data if isinstance(data, list) else []
    
    # Check if we have any notes with "automated API test" in content
    found = False
    for note in notes:
        note_text = note.get("note_text") or note.get("content") or note.get("details") or ""
        if "automated API test" in note_text:
            found = True
            state.test_note_id = note.get("id") or note.get("_id")
            break
    
    log_result("T04b_NotesPersistence", found, 
               f"Notes count={len(notes)}, Test note found={found}",
               data if not found else None)
    return found

def test_lead_detail_includes_notes():
    """T04c: Verify lead detail includes notes array"""
    if not state.test_lead_id:
        log_result("T04c_LeadDetailNotes", False, "No lead ID available")
        return False
    
    status, data = make_request("GET", f"/api/crm/leads/{state.test_lead_id}")
    
    if status != 200:
        log_result("T04c_LeadDetailNotes", False, f"Failed to fetch lead, status={status}", data)
        return False
    
    notes = data.get("notes", [])
    
    # Check if notes array exists and has our test note
    found = False
    for note in notes:
        note_text = note.get("note_text") or note.get("content") or note.get("details") or ""
        if "automated API test" in note_text:
            found = True
            break
    
    log_result("T04c_LeadDetailNotes", found, 
               f"Notes in lead detail={len(notes)}, Test note found={found}",
               {"notes_sample": notes[:2] if notes else []} if not found else None)
    return found

def test_update_lead():
    """T05: Update lead status"""
    if not state.test_lead_id:
        log_result("T05_UpdateLead", False, "No lead ID available")
        return False
    
    # First get current status
    status, lead_data = make_request("GET", f"/api/crm/leads/{state.test_lead_id}")
    current_status = lead_data.get("status", "NEW") if status == 200 else "NEW"
    
    # Toggle status
    new_status = "CONTACTED" if current_status == "NEW" else "NEW"
    
    status, data = make_request("PUT", f"/api/crm/leads/{state.test_lead_id}", {
        "status": new_status
    })
    
    passed = status == 200 and "message" in data
    
    # Verify update persisted
    if passed:
        time.sleep(0.5)
        status2, lead_data2 = make_request("GET", f"/api/crm/leads/{state.test_lead_id}")
        actual_status = lead_data2.get("status") if status2 == 200 else None
        passed = actual_status == new_status
        log_result("T05_UpdateLead", passed, 
                   f"Changed {current_status} → {new_status}, Verified={actual_status}",
                   lead_data2 if not passed else None)
    else:
        log_result("T05_UpdateLead", False, f"Update failed, status={status}", data)
    
    return passed

def test_dashboard_stats():
    """T12: Dashboard stats"""
    status, data = make_request("GET", "/api/crm/dashboard/stats")
    passed = status == 200 and "leads" in data
    
    leads_stats = data.get("leads", {}) if isinstance(data, dict) else {}
    log_result("T12_DashboardStats", passed, 
               f"Leads today={leads_stats.get('today')}, total={leads_stats.get('total')}",
               data if not passed else None)
    return passed

def test_get_users():
    """T10: Get CRM users list"""
    status, data = make_request("GET", "/api/admin/users")
    passed = status == 200 and "users" in data
    
    users = data.get("users", []) if isinstance(data, dict) else []
    log_result("T10_GetUsers", passed, f"Users count={len(users)}", data if not passed else None)
    return passed

def test_get_contacts():
    """T09: Get contacts list"""
    status, data = make_request("GET", "/api/crm/contacts")
    passed = status == 200 and "contacts" in data
    
    contacts = data.get("contacts", []) if isinstance(data, dict) else []
    log_result("T09_GetContacts", passed, f"Contacts count={len(contacts)}", data if not passed else None)
    return passed

def test_get_opportunities():
    """T08: Get opportunities list"""
    status, data = make_request("GET", "/api/crm/opportunities")
    passed = status == 200 and "opportunities" in data
    
    opps = data.get("opportunities", []) if isinstance(data, dict) else []
    log_result("T08_GetOpportunities", passed, f"Opportunities count={len(opps)}", data if not passed else None)
    return passed

def test_get_activities():
    """T13: Get activities list"""
    status, data = make_request("GET", "/api/crm/activities")
    passed = status == 200 and "activities" in data
    
    activities = data.get("activities", []) if isinstance(data, dict) else []
    log_result("T13_GetActivities", passed, f"Activities count={len(activities)}", data if not passed else None)
    return passed

def test_crm_debug():
    """Debug: CRM auth and DB status"""
    status, data = make_request("GET", "/api/crm/debug")
    passed = status == 200 and "db_status" in data
    
    log_result("Debug_CRM", passed, 
               f"DB={data.get('db_status')}, Role={data.get('jwt_role')}, CRM_user={data.get('crm_user_found')}",
               data if not passed else None)
    return passed

# ==========================================
# MAIN
# ==========================================

def run_all_tests():
    """Run all tests and generate report"""
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"IGV CRM API Test Suite")
    print(f"{'='*60}{Colors.RESET}")
    print(f"Backend: {BASE_URL}")
    print(f"Admin Email: {ADMIN_EMAIL or 'NOT SET'}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    # Run tests in order
    tests = [
        test_health,
        test_login,
        test_verify_token,
        test_crm_debug,
        test_get_leads,
        test_get_lead_detail,
        test_add_note,
        test_get_notes_persistence,
        test_lead_detail_includes_notes,
        test_update_lead,
        test_dashboard_stats,
        test_get_users,
        test_get_contacts,
        test_get_opportunities,
        test_get_activities,
    ]
    
    for test_func in tests:
        try:
            test_func()
        except Exception as e:
            log_result(test_func.__name__, False, f"Exception: {str(e)}")
    
    # Summary
    passed = sum(1 for r in state.results if r["passed"])
    failed = sum(1 for r in state.results if not r["passed"])
    total = len(state.results)
    
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}{Colors.RESET}")
    print(f"Total: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
    print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "N/A")
    
    # List failures
    if failed > 0:
        print(f"\n{Colors.RED}Failed tests:{Colors.RESET}")
        for r in state.results:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['details']}")
    
    # Save results to file
    results_file = "test_results.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "backend_url": BASE_URL,
            "summary": {"total": total, "passed": passed, "failed": failed},
            "tests": state.results
        }, f, indent=2)
    print(f"\nResults saved to: {results_file}")
    
    return failed == 0

if __name__ == "__main__":
    # Parse command line args
    import argparse
    parser = argparse.ArgumentParser(description="IGV CRM API Tests")
    parser.add_argument("--base-url", default=BASE_URL, help="Backend URL")
    parser.add_argument("--email", default=ADMIN_EMAIL, help="Admin email")
    parser.add_argument("--password", default=ADMIN_PASSWORD, help="Admin password")
    args = parser.parse_args()
    
    BASE_URL = args.base_url
    ADMIN_EMAIL = args.email
    ADMIN_PASSWORD = args.password
    
    success = run_all_tests()
    sys.exit(0 if success else 1)
