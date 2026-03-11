# MISSION MASTER — Architecture IGV Backend

> Dernière mise à jour : 2026-03-11
> Objectif : Structuration claire par domaine métier — SITE / BLOG / CMS / CRM / SHARED

---

## Structure `app/routers/`

```
igv-backend/
├── server.py                     # Entrée FastAPI — importe tous les routers
├── auth_middleware.py             # SHARED — JWT, get_current_user, require_admin, get_db
├── api_bridge.py                  # SHARED — Compatibilité routes legacy
├── canonical_handlers.py          # SHARED — Ré-export handlers (utilisé par api_bridge)
├── email_templates_seed.py        # SHARED — Seed templates email CRM
│
└── app/routers/
    ├── admin/                     # ADMIN
    │   ├── admin_routes.py            Stats, settings, media upload
    │   └── admin_user_routes.py       Gestion utilisateurs admin
    ├── ai/                        # AI / ANALYSE
    │   ├── ai_routes.py               Routes Gemini AI
    │   ├── mini_analysis_routes.py    Mini-analyses publiques
    │   └── quota_queue_routes.py      File d'attente et quotas AI
    ├── blog/                      # BLOG
    │   └── blog_routes.py             CRUD articles blog
    ├── cms/                       # CMS
    │   └── cms_routes.py              CMS pages, media library, à propos
    ├── crm/                       # CRM
    │   ├── main.py                    Router CRM unifié
    │   ├── companies_routes.py        Entreprises B2B
    │   ├── quality_routes.py          Qualité données, déduplication
    │   ├── automation_kpi_routes.py   Automatisation, KPIs, sources
    │   ├── search_rbac_routes.py      Recherche globale, RBAC
    │   ├── email_export_routes.py     Emails, exports CSV
    │   ├── mini_analysis_audit_routes.py  Audit mini-analyses
    │   └── tasks_routes.py            Tâches CRM
    ├── payments/                  # PAIEMENTS
    │   ├── payment_routes.py          Paiements génériques
    │   ├── monetico_routes.py         Intégration Monetico
    │   ├── invoice_routes.py          Facturation
    │   └── client_routes.py           Portail client
    ├── site/                      # SITE PUBLIC
    │   ├── tracking_routes.py         Tracking visiteurs
    │   ├── extended_routes.py         Contact expert, PDF, email PDF, Google Cal
    │   └── gdpr_routes.py             Consentement GDPR / cookies
    ├── booking_routes.py          # Booking (rdv)
    └── google_oauth_routes.py     # OAuth Google
```

---

## Checklist restructuration backend

- [x] app/routers/admin/ créé — admin_routes.py, admin_user_routes.py
- [x] app/routers/ai/ créé — ai_routes.py, mini_analysis_routes.py, quota_queue_routes.py
- [x] app/routers/blog/ créé — blog_routes.py
- [x] app/routers/cms/ créé — cms_routes.py
- [x] app/routers/crm/ étendu — +7 fichiers
- [x] app/routers/payments/ créé — payment_routes.py, monetico_routes.py, invoice_routes.py, client_routes.py
- [x] app/routers/site/ créé — tracking_routes.py, extended_routes.py, gdpr_routes.py
- [x] server.py mis à jour — tous les imports via app.routers.<domaine>.<fichier>
- [x] Syntaxe server.py vérifiée (ast.parse OK)

## Règles architecturales

1. auth_middleware.py reste à la racine (partagé par tous les routers)
2. Les imports Python utilisent des chemins absolus depuis la racine (uvicorn CWD = igv-backend/)
3. Tout nouveau router → app/routers/<domaine>/<nom>_routes.py
4. Aucune modification visuelle ou fonctionnelle
