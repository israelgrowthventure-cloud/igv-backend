# ============================================================
# MISSION MASTER - CRM IGV RÉPARATION COMPLÈTE
# ============================================================
# Date début: 24 Janvier 2026
# Statut: 🔄 EN COURS
# ============================================================

## IDENTIFIANTS DE TEST

| Rôle | Email | Password |
|------|-------|----------|
| Admin | postmaster@israelgrowthventure.com | Admin@igv2025# |
| Commercial | commercial.test@igv.co.il | Commercial@igv2025# |

## URLS PRODUCTION

- Frontend: https://israelgrowthventure.com
- Backend: https://igv-cms-backend.onrender.com

---

## PHASE 1: INVENTAIRE & MAPPING

### A) ENDPOINTS AUTH
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/admin/login | POST | ✅ OK | ⏳ | - |
| /api/admin/verify | GET | ✅ OK | ⏳ | - |
| /api/admin/logout | POST | ❌ 404 | ⏳ | - |

### B) ENDPOINTS LEADS
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/leads | GET | ✅ OK | ⏳ | - |
| /api/crm/leads | POST | ✅ OK | ⏳ | - |
| /api/crm/leads/{id} | GET | ✅ OK | ⏳ | - |
| /api/crm/leads/{id} | PUT | ✅ OK | ⏳ | - |
| /api/crm/leads/{id} | PATCH | ❌ 405 | ⏳ | - |
| /api/crm/leads/{id}/notes | GET | ✅ OK | ⏳ | - |
| /api/crm/leads/{id}/notes | POST | ✅ OK | ⏳ | - |
| /api/crm/leads/{id}/activities | GET | ❌ 404 | ⏳ | - |
| /api/crm/leads/{id}/emails | GET | ❌ 404 | ⏳ | - |
| /api/crm/leads/{id}/emails/send | POST | ❌ 404 | ⏳ | - |
| /api/crm/leads/{id}/convert | POST | ❌ 404 | ⏳ | - |
| /api/crm/leads/{id}/convert-to-contact | POST | ✅ OK | ⏳ | - |
| /api/crm/leads/{id}/assign | POST | ✅ OK | ⏳ | - |

### C) ENDPOINTS CONTACTS
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/contacts | GET | ✅ OK | ⏳ | - |
| /api/crm/contacts/{id} | GET | ✅ OK | ⏳ | - |
| /api/crm/contacts/{id}/notes | GET | ❌ 404 | ⏳ | - |
| /api/crm/contacts/{id}/notes | POST | ❌ 404 | ⏳ | - |
| /api/crm/contacts/{id}/activities | GET | ❌ 404 | ⏳ | - |
| /api/crm/contacts/{id}/emails | GET | ❌ 404 | ⏳ | - |

### D) ENDPOINTS OPPORTUNITIES
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/opportunities | GET | ✅ OK | ⏳ | - |
| /api/crm/opportunities | POST | ✅ OK | ⏳ | - |
| /api/crm/opportunities/{id} | GET | ❌ 405 | ⏳ | - |
| /api/crm/opportunities/{id} | PUT | ✅ OK | ⏳ | - |
| /api/crm/opportunities/{id}/notes | GET | ❌ 404 | ⏳ | - |
| /api/crm/opportunities/{id}/notes | POST | ❌ 404 | ⏳ | - |
| /api/crm/opportunities/{id}/activities | GET | ❌ 404 | ⏳ | - |

### E) ENDPOINTS PIPELINE
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/pipeline | GET | ✅ OK | ⏳ | - |
| /api/crm/settings/pipeline-stages | GET | ✅ OK | ⏳ | - |

### F) ENDPOINTS EMAILS
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/emails/templates | GET | ✅ OK | ⏳ | - |
| /api/crm/emails/history | GET | ✅ OK | ⏳ | - |
| /api/crm/emails/send | POST | ✅ OK | ⏳ | - |
| /api/crm/emails/drafts | GET | ❌ 404 | ⏳ | - |
| /api/crm/emails/drafts | POST | ❌ 404 | ⏳ | - |

### G) ENDPOINTS SETTINGS ADMIN
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/crm/settings | GET | ❌ 404 | ⏳ | - |
| /api/crm/settings/users | GET | ✅ OK | ⏳ | - |
| /api/crm/settings/users | POST | ✅ OK | ⏳ | - |
| /api/crm/settings/tags | GET | ✅ OK | ⏳ | - |
| /api/crm/settings/dispatch | GET | ❌ 404 | ⏳ | - |
| /api/crm/settings/quality | GET | ❌ 404 | ⏳ | - |
| /api/crm/settings/performance | GET | ❌ 404 | ⏳ | - |

### H) ENDPOINTS MINI-ANALYSE
| Endpoint | Méthode | Statut Avant | Statut Après | Preuve |
|----------|---------|--------------|--------------|--------|
| /api/mini-analysis | POST | ✅ OK | ⏳ | - |
| /api/mini-analysis | GET | ❌ 405 | ⏳ | - |

---

## PHASE 2: FIX BACKEND

### Endpoints à implémenter:
- [ ] POST /api/admin/logout
- [ ] PATCH /api/crm/leads/{id}
- [ ] GET /api/crm/leads/{id}/activities
- [ ] GET /api/crm/leads/{id}/emails
- [ ] POST /api/crm/leads/{id}/emails/send
- [ ] POST /api/crm/leads/{id}/convert (alias)
- [ ] GET /api/crm/contacts/{id}/notes
- [ ] POST /api/crm/contacts/{id}/notes
- [ ] GET /api/crm/contacts/{id}/activities
- [ ] GET /api/crm/contacts/{id}/emails
- [ ] GET /api/crm/opportunities/{id}
- [ ] GET /api/crm/opportunities/{id}/notes
- [ ] POST /api/crm/opportunities/{id}/notes
- [ ] GET /api/crm/opportunities/{id}/activities
- [ ] GET /api/crm/emails/drafts
- [ ] POST /api/crm/emails/drafts
- [ ] GET /api/crm/settings
- [ ] GET /api/crm/settings/dispatch
- [ ] GET /api/crm/settings/quality
- [ ] GET /api/crm/settings/performance
- [ ] GET /api/mini-analysis

---

## PHASE 3: FIX FRONTEND

### Composants à modifier:
- [ ] LeadDetail.js - Bouton assignation commercial
- [ ] LeadDetail.js - Onglets Notes/Emails/Activités
- [ ] OpportunityDetail.js - Page à créer
- [ ] DashboardPage.js - Widgets Admin différenciés
- [ ] SettingsPage.js - Onglets Dispatch/Quality/Performance
- [ ] RBAC UI - Cacher éléments admin pour commercial

---

## PHASE 4: TESTS E2E

### Admin Journey
- [ ] Login admin
- [ ] Dashboard visible
- [ ] Users CRUD
- [ ] Leads: voir non assignés
- [ ] Lead: assigner à commercial
- [ ] Lead: changer statut/stage
- [ ] Lead: ajouter note
- [ ] Lead: envoyer email
- [ ] Lead: voir activités
- [ ] Lead: convertir en contact
- [ ] Contact: voir détail
- [ ] Opportunité: créer
- [ ] Pipeline: drag&drop
- [ ] Emails: templates CRUD
- [ ] Settings: accessible

### Commercial Journey
- [ ] Login commercial
- [ ] Dashboard visible (mes leads)
- [ ] Leads: voir seulement assignés
- [ ] Lead: modifier statut
- [ ] Lead: ajouter note
- [ ] Lead: envoyer email
- [ ] Users/Settings: accès bloqué
- [ ] Opportunités: CRUD
- [ ] Tâches: CRUD

---

## PHASE 5: DÉPLOIEMENT

- [ ] Commit backend
- [ ] Push GitHub
- [ ] Deploy Render backend
- [ ] Deploy Render frontend
- [ ] Tests production

---

## RÉSUMÉ FINAL

| Catégorie | Total | OK | KO |
|-----------|-------|----|----|
| Auth | 3 | ⏳ | ⏳ |
| Leads | 13 | ⏳ | ⏳ |
| Contacts | 6 | ⏳ | ⏳ |
| Opportunities | 7 | ⏳ | ⏳ |
| Pipeline | 2 | ⏳ | ⏳ |
| Emails | 5 | ⏳ | ⏳ |
| Settings | 7 | ⏳ | ⏳ |
| Mini-Analyse | 2 | ⏳ | ⏳ |
| **TOTAL** | **45** | ⏳ | ⏳ |

---

*Dernière mise à jour: 24/01/2026 22:30*
