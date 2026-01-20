# IGV Backend - Python FastAPI Application

Configuration pour le déploiement séparé du backend.

## Structure du repo

```
igv-backend/
├── .env
├── .env.example
├── .gitignore
├── admin_routes.py
├── admin_user_routes.py
├── ai_routes.py
├── assets/
├── auth_middleware.py
├── cms_routes.py
├── crm_complete_routes.py
├── crm_routes.py
├── download_fonts.sh
├── extended_routes.py
├── fonts/
├── gdpr_routes.py
├── igv_internal/
├── invoice_routes.py
├── mini_analysis_routes.py
├── models/
├── monetico_routes.py
├── prompts/
├── quota_queue_routes.py
├── README.md
├── render.yaml
├── requirements.txt
├── server.py
└── tracking_routes.py
```

## Variables d'environnement requises

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | URI de connexion MongoDB |
| `DB_NAME` | Nom de la base de données |
| `JWT_SECRET` | Secret pour les tokens JWT |
| `CMS_PASSWORD` | Mot de passe CMS séparé |
| `CORS_ALLOWED_ORIGINS` | `https://israelgrowthventure.com` |
| `GEMINI_API_KEY` | Clé API Google Gemini |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Config SMTP |

## Commandes

```bash
# Installation
pip install -r requirements.txt
bash download_fonts.sh

# Développement local
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn server:app --host 0.0.0.0 --port $PORT
```

## Endpoints principaux

- `GET /health` - Health check
- `GET /api/health` - Health check avec status MongoDB
- `POST /api/admin/login` - Login admin
- `POST /api/mini-analysis` - Mini-analyse Gemini
- `GET /api/crm/leads` - Liste des prospects
- `POST /api/contact` - Formulaire de contact

## Déploiement Render

Le service `igv-cms-backend` est configuré comme un Web Service Python.
Le déploiement est automatique à chaque push sur `main`.
