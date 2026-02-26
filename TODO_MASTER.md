# TODO MASTER — FIX GOOGLE CALENDAR OAUTH + 3 CORRECTIONS SITE
**Date:** 2026-02-26

## MISSION COURANTE — GOOGLE CALENDAR RE-AUTH

- [ ] **G1** — Commit app/services/google_calendar_client.py (fix get_connection_status)
- [ ] **G2** — Commit app/routers/google_oauth_routes.py (temp-connect endpoint)
- [ ] **G3** — Push backend main → Render deploy
- [ ] **G4** — Calculer token TOTP + visiter temp-connect URL en navigateur
- [ ] **G5** — Autoriser israel.growth.venture@gmail.com dans OAuth Google
- [ ] **G6** — Vérifier /api/booking/version → googleConnected:true
- [ ] **G7** — Vérifier /api/booking/availability?days=14 → slots non vides
- [ ] **G8** — Tester /audit sur prod → créneaux visibles

---

# TODO MASTER — FLOW USER COMPLET (CREATE → ASSIGN → LOGIN → DELETE)
**Date début**: 2026-01-29



---

## CHECKPOINT 0 — DÉCOUVERTE INCONTESTABLE DES ENDPOINTS (OPENAPI)

- [x] **CP0.1** - URL backend PROD utilisée par frontend
  - Fichier: `igv-frontend/render.yaml` ligne 16
  - Preuve: `REACT_APP_API_URL: https://igv-cms-backend.onrender.com`

- [x] **CP0.2** - Spec OpenAPI live
  - `curl.exe -i https://igv-cms-backend.onrender.com/health` → HTTP 200 OK
  - `curl.exe https://igv-cms-backend.onrender.com/openapi.json` → 165k downloaded
  - Parser: 196 paths total
  - Endpoints users: `POST /api/crm/settings/users`, `GET /api/crm/settings/users`, `DELETE /api/crm/settings/users/{user_id}`
  - Endpoints auth: `POST /api/admin/login`
  - Endpoints assign: `PUT /api/crm/users/{user_id}/permissions`
  - Preuve: Output brut dans terminal

---

## CHECKPOINT 1 — AUTH ADMIN (OBTENIR UN TOKEN)

- [x] **CP1.1** - Créer `payload_admin.json`
  - Email: `postmaster@israelgrowthventure.com`
  - Password: `Admin@igv2025#`
  - Fichier: `C:\Users\PC\Desktop\IGV\repare\payload_admin.json`

- [x] **CP1.2** - Login admin via endpoint OpenAPI
  - `curl.exe -i -X POST https://igv-cms-backend.onrender.com/api/admin/login --data-binary "@payload_admin.json"`
  - Preuve: **HTTP 200 OK**

- [x] **CP1.3** - Extraire token admin
  - Token: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InBvc3RtYXN0ZXJAaXNyYWVsZ3Jvd3RodmVudHVyZS5jb20iLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3Njk3MzIwMDEsImlhdCI6MTc2OTY0NTYwMX0.NRt2Ld8K33ZAFKFy8bGEo0g_ZiFQkeiJIWt_8al6RF0`
  - Role: `admin`

---

## CHECKPOINT 2 — CREATE USER (API + UI + SCREENSHOT)

- [x] **CP2.1** - User test unique défini
  - Email: `test.user+igv.20260129-021501@example.com`
  - Password: `Test#2026!IgV`
  - Role: `commercial`

- [x] **CP2.2** - Créer `payload_create_user.json` conforme OpenAPI
  - Fichier: `C:\Users\PC\Desktop\IGV\repare\payload_create_user.json`

- [x] **CP2.3** - API create user
  - `curl.exe -X POST https://igv-cms-backend.onrender.com/api/crm/settings/users -H "Authorization: Bearer <TOKEN>" --data-binary "@payload_create_user.json"`
  - Preuve: **HTTP 200** (après correction duplicate → nouveau timestamp)
  - user_id: `697aa696b4c6cd1a04aa414f`

- [x] **CP2.4** - Preuve API existence
  - `curl.exe https://igv-cms-backend.onrender.com/api/crm/settings/users -H "Authorization: Bearer <TOKEN>"`
  - Preuve: User `test.user+igv.20260129-021501@example.com` visible dans JSON response avec `"_id":"697aa696b4c6cd1a04aa414f"`, `"role":"commercial"`, `"is_active":true`

- [x] **CP2.5** - Preuve UI Playwright
  - Script: `igv-frontend/cp2_ui_screenshot.cjs`
  - Login admin réussi → Accès page CRM Settings Users
  - Screenshot: `C:\Users\PC\Desktop\IGV\repare\verification_preuves\screenshots\CP2_CREATEUSER_2026-01-29T00-19-06_PROD.png`
  - **⚠️ ATTENTION**: User test NON visible dans table UI (problème frontend UsersTab chargement possible)

---

## CHECKPOINT 3 — ASSIGN ROLE/PERMISSIONS (API + UI + SCREENSHOT)

- [x] **CP3.1** - Identifier endpoint assignation via OpenAPI
  - Endpoint: `PUT /api/crm/users/{user_id}/permissions`
  - Payload attendu: `{"permissions": [...]}` (array d'objets `{resource, actions}`)

- [x] **CP3.2** - API assign permissions
  - Payload: `payload_assign_permissions_fixed.json` (5 resources: leads, contacts, opportunities, activities, emails)
  - `curl.exe -i -X PUT https://igv-cms-backend.onrender.com/api/crm/users/697aa696b4c6cd1a04aa414f/permissions -H "Authorization: Bearer <TOKEN>" --data-binary "@payload_assign_permissions_fixed.json"`
  - Preuve: **HTTP 200 OK**, `{"success":true,"message":"Permissions updated"}`
  - GET user confirme: `"custom_permissions":[{"resource":"leads","actions":["create","read","update","delete","assign"]}, ...]` (5 ressources total)

- [ ] **CP3.3** - Preuve UI Playwright
  - Script: À créer
  - Screenshot: `verification_preuves/screenshots/CP3_ASSIGN_<timestamp>_PROD.png`
  - Preuve: Permissions visibles dans fiche user

---

## CHECKPOINT 4 — LOGIN USER TEST (API + UI + SCREENSHOT)

- [x] **CP4.1** - Créer `payload_login_test.json`
  - Fichier: `C:\Users\PC\Desktop\IGV\repare\payload_login_test.json`

- [x] **CP4.2** - API login user test
  - `curl.exe -i -X POST https://igv-cms-backend.onrender.com/api/admin/login --data-binary "@payload_login_test.json"`
  - Preuve: **HTTP 200 OK**
  - Token user test: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InRlc3QudXNlcitpZ3YuMjAyNjAxMjktMDIxNTAxQGV4YW1wbGUuY29tIiwicm9sZSI6ImNvbW1lcmNpYWwiLCJleHAiOjE3Njk3MzI1MTUsImlhdCI6MTc2OTY0NjExNX0.xkj040x7jJluGKmjwkBIMmAA5kZHnMFiFhTiQetXD18`
  - Role: `commercial`
  - Vérifier endpoint protégé: `curl.exe https://igv-cms-backend.onrender.com/api/crm/opportunities?limit=5 -H "Authorization: Bearer <TOKEN_TEST>"` → **HTTP 200 OK**

- [ ] **CP4.3** - Preuve UI Playwright
  - Script: À créer
  - Screenshot: `verification_preuves/screenshots/CP4_LOGINTEST_<timestamp>_PROD.png`
  - Preuve: User test connecté, dashboard ou page autorisée charge

---

## CHECKPOINT 5 — DELETE USER (API + UI + SCREENSHOT)

- [x] **CP5.1** - API delete user
  - `curl.exe -i -X DELETE https://igv-cms-backend.onrender.com/api/crm/settings/users/697aa696b4c6cd1a04aa414f -H "Authorization: Bearer <TOKEN>"`
  - Preuve: **HTTP 200 OK**

- [x] **CP5.2** - Preuve disparition API
  - `curl.exe https://igv-cms-backend.onrender.com/api/crm/settings/users -H "Authorization: Bearer <TOKEN>" | Select-String "697aa696b4c6cd1a04aa414f"`
  - Preuve: **Aucun match** (user absent de la liste)

- [ ] **CP5.3** - Preuve UI Playwright
  - Script: À créer
  - Screenshot: `verification_preuves/screenshots/CP5_DELETE_<timestamp>_PROD.png`
  - Preuve: User absent de la table UI

- [x] **CP5.4** - Login user supprimé impossible
  - `curl.exe -i -X POST https://igv-cms-backend.onrender.com/api/admin/login --data-binary "@payload_login_test.json"`
  - Preuve: **HTTP 401 Unauthorized**, `{"detail":"Invalid credentials"}`

---

## PUSH / DEPLOY / PREUVES FINALES

- [ ] **Push commits**
  - SHA backend collé
  - SHA frontend collé
  - Fichiers modifiés listés

- [ ] **Render deploy**
  - Service backend: URL + statut
  - Service frontend: URL + statut

- [ ] **Relancer CP1→CP5 en PROD**
  - Mêmes commandes curl
  - Mêmes screenshots Playwright
  - Tous les checkpoints revalidés
