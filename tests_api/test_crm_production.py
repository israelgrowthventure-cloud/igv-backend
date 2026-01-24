#!/usr/bin/env python3
"""
IGV CRM - Tests de Production Complets
Date: 2026-01-24
Objectif: Tester tous les chemins CRM en production et documenter OK/KO

ATTENTION: Ce script teste la PRODUCTION
"""

import requests
import json
import sys
from datetime import datetime

# Configuration Production
BASE_URL = "https://igv-cms-backend.onrender.com"
ADMIN_EMAIL = "postmaster@israelgrowthventure.com"
ADMIN_PASSWORD = "Admin@igv2025#"

# Résultats
results = []

def log_result(path, method, status, ok, proof, cause=""):
    """Enregistre un résultat de test"""
    result = {
        "path": path,
        "method": method,
        "status": status,
        "ok": "✅ OK" if ok else "❌ KO",
        "proof": proof[:200] if len(proof) > 200 else proof,
        "cause": cause
    }
    results.append(result)
    symbol = "✅" if ok else "❌"
    print(f"{symbol} [{method}] {path} → {status}")
    if not ok:
        print(f"   Cause: {cause}")
    return result

def test_health():
    """Test /api/health"""
    print("\n" + "="*60)
    print("TEST: Health Check")
    print("="*60)
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=30)
        data = r.json() if r.status_code == 200 else r.text
        ok = r.status_code == 200 and data.get("status") == "ok"
        log_result("/api/health", "GET", r.status_code, ok, json.dumps(data))
        return ok
    except Exception as e:
        log_result("/api/health", "GET", 0, False, str(e), f"Exception: {e}")
        return False

def test_login():
    """Test /api/admin/login"""
    print("\n" + "="*60)
    print("TEST: Admin Login")
    print("="*60)
    try:
        r = requests.post(f"{BASE_URL}/api/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        }, timeout=30)
        
        print(f"   → Status: {r.status_code}")
        print(f"   → Response: {r.text[:300]}")
        
        if r.status_code == 200:
            data = r.json()
            # Le backend peut retourner "token" ou "access_token"
            token = data.get("token") or data.get("access_token")
            user = data.get("user") or {}
            # Le role peut être dans user.role ou directement dans data.role
            role = data.get("role") or user.get("role", "unknown") if user else data.get("role", "unknown")
            ok = bool(token)
            proof = f"token={token[:20] if token else 'None'}..., role={role}"
            log_result("/api/admin/login", "POST", r.status_code, ok, proof)
            if ok:
                print(f"   ✅ Token obtenu, role={role}")
            return token if ok else None
        else:
            log_result("/api/admin/login", "POST", r.status_code, False, r.text[:200], "Login failed")
            return None
    except Exception as e:
        log_result("/api/admin/login", "POST", 0, False, str(e), f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_verify(token):
    """Test /api/admin/verify"""
    print("\n" + "="*60)
    print("TEST: Verify Token")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/verify", headers=headers, timeout=30)
        ok = r.status_code == 200
        log_result("/api/admin/verify", "GET", r.status_code, ok, r.text[:200])
        return ok
    except Exception as e:
        log_result("/api/admin/verify", "GET", 0, False, str(e), f"Exception: {e}")
        return False

def test_crm_dashboard_stats(token):
    """Test /api/crm/dashboard/stats"""
    print("\n" + "="*60)
    print("TEST: CRM Dashboard Stats")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/dashboard/stats", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            ok = "total_leads" in data or "leads" in data or isinstance(data, dict)
            log_result("/api/crm/dashboard/stats", "GET", r.status_code, ok, json.dumps(data)[:200])
            return data
        else:
            log_result("/api/crm/dashboard/stats", "GET", r.status_code, False, r.text[:200], "Non-200 response")
            return None
    except Exception as e:
        log_result("/api/crm/dashboard/stats", "GET", 0, False, str(e), f"Exception: {e}")
        return None

def test_crm_leads_list(token):
    """Test /api/crm/leads - Liste des leads"""
    print("\n" + "="*60)
    print("TEST: CRM Leads List")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/leads", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            leads = data if isinstance(data, list) else data.get("leads", [])
            ok = isinstance(leads, list)
            log_result("/api/crm/leads", "GET", r.status_code, ok, f"count={len(leads)}")
            print(f"   → {len(leads)} leads trouvés")
            return leads
        else:
            log_result("/api/crm/leads", "GET", r.status_code, False, r.text[:200], "Non-200 response")
            return []
    except Exception as e:
        log_result("/api/crm/leads", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_lead_detail(token, lead_id):
    """Test /api/crm/leads/:id - Détail d'un lead"""
    print("\n" + "="*60)
    print(f"TEST: CRM Lead Detail (ID: {lead_id})")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/leads/{lead_id}", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            has_notes = "notes" in data
            log_result(f"/api/crm/leads/{lead_id}", "GET", r.status_code, True, 
                      f"email={data.get('email','N/A')}, notes={len(data.get('notes', []))}")
            print(f"   → Lead: {data.get('email', 'N/A')}")
            print(f"   → Notes: {len(data.get('notes', []))}")
            return data
        else:
            log_result(f"/api/crm/leads/{lead_id}", "GET", r.status_code, False, r.text[:200])
            return None
    except Exception as e:
        log_result(f"/api/crm/leads/{lead_id}", "GET", 0, False, str(e), f"Exception: {e}")
        return None

def test_crm_lead_notes_add(token, lead_id):
    """Test POST /api/crm/leads/:id/notes - Ajout de note"""
    print("\n" + "="*60)
    print(f"TEST: Add Note to Lead (ID: {lead_id})")
    print("="*60)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_text = f"[TEST AUTOMATIQUE] Note de test - {timestamp}"
    
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.post(f"{BASE_URL}/api/crm/leads/{lead_id}/notes", 
                         headers=headers, 
                         json={"note_text": note_text},
                         timeout=30)
        if r.status_code in [200, 201]:
            log_result(f"/api/crm/leads/{lead_id}/notes", "POST", r.status_code, True, 
                      f"note_text={note_text[:50]}...")
            print(f"   ✅ Note ajoutée: {note_text[:50]}...")
            return note_text
        else:
            log_result(f"/api/crm/leads/{lead_id}/notes", "POST", r.status_code, False, 
                      r.text[:200], "Failed to add note")
            return None
    except Exception as e:
        log_result(f"/api/crm/leads/{lead_id}/notes", "POST", 0, False, str(e), f"Exception: {e}")
        return None

def test_crm_lead_notes_get(token, lead_id, expected_note=None):
    """Test GET /api/crm/leads/:id/notes - Récupération des notes"""
    print("\n" + "="*60)
    print(f"TEST: Get Notes for Lead (ID: {lead_id})")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/leads/{lead_id}/notes", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            notes = data if isinstance(data, list) else data.get("notes", [])
            
            # Vérifier si la note attendue est présente
            note_found = False
            if expected_note:
                for note in notes:
                    note_content = note.get("note_text", "") or note.get("content", "") or note.get("text", "")
                    if expected_note in note_content:
                        note_found = True
                        break
            
            ok = len(notes) >= 0  # La requête a réussi
            proof = f"count={len(notes)}"
            if expected_note:
                proof += f", expected_note_found={note_found}"
                ok = note_found
            
            log_result(f"/api/crm/leads/{lead_id}/notes", "GET", r.status_code, ok, proof)
            print(f"   → {len(notes)} notes trouvées")
            if expected_note:
                print(f"   → Note attendue présente: {'✅ OUI' if note_found else '❌ NON'}")
            return notes, note_found
        else:
            log_result(f"/api/crm/leads/{lead_id}/notes", "GET", r.status_code, False, r.text[:200])
            return [], False
    except Exception as e:
        log_result(f"/api/crm/leads/{lead_id}/notes", "GET", 0, False, str(e), f"Exception: {e}")
        return [], False

def test_crm_contacts_list(token):
    """Test /api/crm/contacts"""
    print("\n" + "="*60)
    print("TEST: CRM Contacts List")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/contacts", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            contacts = data if isinstance(data, list) else data.get("contacts", [])
            log_result("/api/crm/contacts", "GET", r.status_code, True, f"count={len(contacts)}")
            print(f"   → {len(contacts)} contacts trouvés")
            return contacts
        else:
            log_result("/api/crm/contacts", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/contacts", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_opportunities_list(token):
    """Test /api/crm/opportunities"""
    print("\n" + "="*60)
    print("TEST: CRM Opportunities List")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/opportunities", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            opps = data if isinstance(data, list) else data.get("opportunities", [])
            log_result("/api/crm/opportunities", "GET", r.status_code, True, f"count={len(opps)}")
            print(f"   → {len(opps)} opportunités trouvées")
            return opps
        else:
            log_result("/api/crm/opportunities", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/opportunities", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_pipeline(token):
    """Test /api/crm/pipeline"""
    print("\n" + "="*60)
    print("TEST: CRM Pipeline")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/pipeline", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            log_result("/api/crm/pipeline", "GET", r.status_code, True, json.dumps(data)[:200])
            return data
        else:
            log_result("/api/crm/pipeline", "GET", r.status_code, False, r.text[:200])
            return None
    except Exception as e:
        log_result("/api/crm/pipeline", "GET", 0, False, str(e), f"Exception: {e}")
        return None

def test_crm_activities(token):
    """Test /api/crm/activities"""
    print("\n" + "="*60)
    print("TEST: CRM Activities")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/activities", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            activities = data if isinstance(data, list) else data.get("activities", [])
            log_result("/api/crm/activities", "GET", r.status_code, True, f"count={len(activities)}")
            print(f"   → {len(activities)} activités trouvées")
            return activities
        else:
            log_result("/api/crm/activities", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/activities", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_tasks(token):
    """Test /api/crm/tasks"""
    print("\n" + "="*60)
    print("TEST: CRM Tasks")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/tasks", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            tasks = data if isinstance(data, list) else data.get("tasks", [])
            log_result("/api/crm/tasks", "GET", r.status_code, True, f"count={len(tasks)}")
            print(f"   → {len(tasks)} tâches trouvées")
            return tasks
        else:
            log_result("/api/crm/tasks", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/tasks", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_users(token):
    """Test /api/crm/settings/users"""
    print("\n" + "="*60)
    print("TEST: CRM Users (Settings)")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/settings/users", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            users = data if isinstance(data, list) else data.get("users", [])
            log_result("/api/crm/settings/users", "GET", r.status_code, True, f"count={len(users)}")
            print(f"   → {len(users)} utilisateurs CRM")
            return users
        else:
            log_result("/api/crm/settings/users", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/settings/users", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_email_templates(token):
    """Test /api/crm/emails/templates"""
    print("\n" + "="*60)
    print("TEST: CRM Email Templates")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/emails/templates", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            templates = data if isinstance(data, list) else data.get("templates", [])
            log_result("/api/crm/emails/templates", "GET", r.status_code, True, f"count={len(templates)}")
            print(f"   → {len(templates)} templates email")
            return templates
        else:
            log_result("/api/crm/emails/templates", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/emails/templates", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_email_history(token):
    """Test /api/crm/emails/history"""
    print("\n" + "="*60)
    print("TEST: CRM Email History")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/emails/history", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            emails = data if isinstance(data, list) else data.get("emails", [])
            log_result("/api/crm/emails/history", "GET", r.status_code, True, f"count={len(emails)}")
            print(f"   → {len(emails)} emails dans l'historique")
            return emails
        else:
            log_result("/api/crm/emails/history", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/emails/history", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_pipeline_stages(token):
    """Test /api/crm/settings/pipeline-stages"""
    print("\n" + "="*60)
    print("TEST: CRM Pipeline Stages")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/settings/pipeline-stages", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            stages = data if isinstance(data, list) else data.get("stages", [])
            log_result("/api/crm/settings/pipeline-stages", "GET", r.status_code, True, f"count={len(stages)}")
            print(f"   → {len(stages)} stages pipeline")
            return stages
        else:
            log_result("/api/crm/settings/pipeline-stages", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/settings/pipeline-stages", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_tags(token):
    """Test /api/crm/settings/tags"""
    print("\n" + "="*60)
    print("TEST: CRM Tags")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/settings/tags", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            tags = data if isinstance(data, list) else data.get("tags", [])
            log_result("/api/crm/settings/tags", "GET", r.status_code, True, f"count={len(tags)}")
            print(f"   → {len(tags)} tags")
            return tags
        else:
            log_result("/api/crm/settings/tags", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/crm/settings/tags", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_admin_users(token):
    """Test /api/admin/users"""
    print("\n" + "="*60)
    print("TEST: Admin Users")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/admin/users", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            users = data if isinstance(data, list) else data.get("users", [])
            log_result("/api/admin/users", "GET", r.status_code, True, f"count={len(users)}")
            print(f"   → {len(users)} admin users")
            return users
        else:
            log_result("/api/admin/users", "GET", r.status_code, False, r.text[:200])
            return []
    except Exception as e:
        log_result("/api/admin/users", "GET", 0, False, str(e), f"Exception: {e}")
        return []

def test_crm_debug(token):
    """Test /api/crm/debug"""
    print("\n" + "="*60)
    print("TEST: CRM Debug")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/debug", headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            log_result("/api/crm/debug", "GET", r.status_code, True, json.dumps(data)[:200])
            return data
        else:
            log_result("/api/crm/debug", "GET", r.status_code, False, r.text[:200])
            return None
    except Exception as e:
        log_result("/api/crm/debug", "GET", 0, False, str(e), f"Exception: {e}")
        return None

def test_export_csv(token):
    """Test /api/crm/leads/export/csv"""
    print("\n" + "="*60)
    print("TEST: Export Leads CSV")
    print("="*60)
    try:
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BASE_URL}/api/crm/leads/export/csv", headers=headers, timeout=30)
        if r.status_code == 200:
            content_type = r.headers.get("Content-Type", "")
            is_csv = "csv" in content_type or "text" in content_type or len(r.content) > 0
            log_result("/api/crm/leads/export/csv", "GET", r.status_code, is_csv, 
                      f"Content-Type={content_type}, size={len(r.content)} bytes")
            print(f"   → Export: {len(r.content)} bytes")
            return True
        else:
            log_result("/api/crm/leads/export/csv", "GET", r.status_code, False, r.text[:200])
            return False
    except Exception as e:
        log_result("/api/crm/leads/export/csv", "GET", 0, False, str(e), f"Exception: {e}")
        return False

def print_summary():
    """Affiche le résumé des tests"""
    print("\n" + "="*80)
    print("RÉSUMÉ DES TESTS")
    print("="*80)
    
    ok_count = sum(1 for r in results if "✅" in r["ok"])
    ko_count = sum(1 for r in results if "❌" in r["ok"])
    
    print(f"\nTotal: {len(results)} tests | ✅ OK: {ok_count} | ❌ KO: {ko_count}")
    print("\n" + "-"*80)
    print(f"{'Path':<45} {'Method':<8} {'Status':<8} {'Result'}")
    print("-"*80)
    
    for r in results:
        print(f"{r['path']:<45} {r['method']:<8} {r['status']:<8} {r['ok']}")
    
    print("\n" + "="*80)
    print("DÉTAIL DES ÉCHECS:")
    print("="*80)
    for r in results:
        if "❌" in r["ok"]:
            print(f"\n❌ {r['method']} {r['path']}")
            print(f"   Status: {r['status']}")
            print(f"   Cause: {r['cause']}")
            print(f"   Proof: {r['proof']}")
    
    # Générer le markdown pour MISSION_MASTER.md
    print("\n" + "="*80)
    print("TABLEAU MARKDOWN POUR MISSION_MASTER.md:")
    print("="*80)
    print("\n| Chemin | Méthode | Status | Résultat | Preuve |")
    print("|--------|---------|--------|----------|--------|")
    for r in results:
        proof_short = r['proof'][:60] + "..." if len(r['proof']) > 60 else r['proof']
        print(f"| `{r['path']}` | {r['method']} | {r['status']} | {r['ok']} | {proof_short} |")

def main():
    """Exécution principale des tests"""
    print("\n" + "#"*80)
    print("# IGV CRM - TESTS DE PRODUCTION COMPLETS")
    print(f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Backend: {BASE_URL}")
    print("#"*80)
    
    # 1. Health check
    if not test_health():
        print("\n❌ ABORT: Backend non accessible")
        print_summary()
        return 1
    
    # 2. Login
    token = test_login()
    if not token:
        print("\n❌ ABORT: Login échoué, impossible de continuer")
        print_summary()
        return 1
    
    # 3. Verify token
    test_verify(token)
    
    # 4. CRM Debug
    test_crm_debug(token)
    
    # 5. Dashboard stats
    test_crm_dashboard_stats(token)
    
    # 6. Leads
    leads = test_crm_leads_list(token)
    lead_id = None
    if leads and len(leads) > 0:
        lead_id = leads[0].get("_id") or leads[0].get("id")
        if lead_id:
            test_crm_lead_detail(token, lead_id)
            
            # Test notes persistence - CRITIQUE
            added_note = test_crm_lead_notes_add(token, lead_id)
            if added_note:
                # Vérifier que la note persiste
                notes, found = test_crm_lead_notes_get(token, lead_id, added_note)
                if not found:
                    print("\n⚠️ ALERTE P0: Note ajoutée mais non retrouvée!")
    
    # 7. Contacts
    contacts = test_crm_contacts_list(token)
    if contacts and len(contacts) > 0:
        contact_id = contacts[0].get("_id") or contacts[0].get("id")
        if contact_id:
            print(f"\n   → Premier contact ID: {contact_id}")
    
    # 8. Opportunities
    test_crm_opportunities_list(token)
    
    # 9. Pipeline
    test_crm_pipeline(token)
    
    # 10. Pipeline stages
    test_crm_pipeline_stages(token)
    
    # 11. Activities
    test_crm_activities(token)
    
    # 12. Tasks
    test_crm_tasks(token)
    
    # 13. Users
    test_crm_users(token)
    test_admin_users(token)
    
    # 14. Email templates & history
    test_crm_email_templates(token)
    test_crm_email_history(token)
    
    # 15. Tags
    test_crm_tags(token)
    
    # 16. Export CSV
    test_export_csv(token)
    
    # Résumé final
    print_summary()
    
    ko_count = sum(1 for r in results if "❌" in r["ok"])
    return 1 if ko_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
