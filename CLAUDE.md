# CLAUDE.md — Israel Growth Venture (israelgrowthventure.com)
# Fichier de mémoire projet — lire EN PREMIER à chaque session.

---

## 1. REPOS & BRANCHES DE TRAVAIL

| Repo | URL | Branche active |
|------|-----|----------------|
| Frontend | `israelgrowthventure-cloud/igv-frontend` | `claude/fix-article-photo-layout-9858M` |
| Backend  | `israelgrowthventure-cloud/igv-backend`  | `claude/fix-article-photo-layout-9858M` |

- Toujours développer sur la branche `claude/` correspondant à la session.
- Ne jamais push sur `main` directement.
- Format push : `git push -u origin claude/<nom>-<sessionId>`

---

## 2. STACK TECHNIQUE

### Frontend — `/home/user/igv-frontend`
- **Framework** : Next.js 16 (`output: 'export'`, `distDir: 'build'`, `trailingSlash: true`)
- **React** : 18.3 — pas de TypeScript, fichiers `.js` / `.jsx`
- **CSS** : Tailwind CSS + Radix UI (`@radix-ui/react-*`)
- **CMS éditeur** : React Quill 2 (sauvegarde HTML dans MongoDB)
- **API calls** : Axios via `src/api/client.js` (instance unique `apiClient`)
- **Env var frontend** : `NEXT_PUBLIC_BACKEND_URL` ou `REACT_APP_BACKEND_URL`
- **Build** : `npm run build` → dossier `/build/` → Render static site

**Architecture source :**
```
src/views/          # Composants React métier (BlogArticle.js, Home.js, etc.)
app/                # Next.js App Router (wrappers, layouts, routes)
app/lib/            # Shims : router-shim.jsx, helmet-shim.js, router-context.js
src/api/            # client.js, routes.js, index.js
src/i18n/           # config.js + locales/{fr,en,he}.json
```

**Alias webpack/Turbopack (ne pas importer directement) :**
- `react-router-dom` → `app/lib/router-shim.jsx`
- `react-helmet-async` → `app/lib/helmet-shim.js`

**Pattern pages dynamiques (ex. articles de blog) :**
- `app/future-commerce/[slug]/page.js` → Server component (generateStaticParams)
- `app/future-commerce/[slug]/BlogArticleClient.jsx` → Client component, fournit `RouterParamsContext`
- `src/views/BlogArticle.js` → Composant métier, lit `useParams()` via shim

### Backend — `/home/user/igv-backend`
- **Framework** : FastAPI 0.110 + Uvicorn
- **DB** : MongoDB via Motor 3.3 (async)
- **Auth** : JWT (PyJWT) + bcrypt
- **Email** : aiosmtplib
- **AI** : OpenAI + Google Gemini (`google-genai`)
- **Markdown → HTML** : `markdown-it-py==4.0.0` (import : `from markdown_it import MarkdownIt`)
- **PDF** : ReportLab + python-bidi (RTL), arabic-reshaper
- **Env var backend** : `MONGODB_URL`, `JWT_SECRET`, `OPENAI_API_KEY`

**Structure backend :**
```
server.py                          # Point d'entrée FastAPI, startup hooks, seeds
app/routers/blog/blog_routes.py    # CRUD articles (/api/blog/*)
articles/{fr,en,he}/{slug}.md      # Contenu des articles en markdown
```

---

## ENVIRONMENT VARIABLES — SOURCE OF TRUTH

Les variables d'environnement utilisées en production sont celles définies sur Render.
**Aucun autre nom de variable ne doit être utilisé dans le code.**

### Règle obligatoire

Avant toute correction liée à une API, base de données ou service externe,
vérifier que la variable d'environnement utilisée correspond exactement à celle définie sur Render.

### Variables backend autorisées (Render → igv-cms-backend)

```
MONGODB_URI
DB_NAME
GEMINI_API_KEY
SMTP_HOST
SMTP_PORT
SMTP_USER
SMTP_PASSWORD
SMTP_FROM
JWT_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES
ENVIRONMENT
PORT
```

### Variables frontend autorisées (Render → igv-frontend)

```
NEXT_PUBLIC_BACKEND_URL
```

### Interdits absolus

| Variable interdite | Raison |
|--------------------|--------|
| `MONGO_URL` | Alias non canonique — utiliser `MONGODB_URI` |
| `MONGODB_URL` | Alias non canonique — utiliser `MONGODB_URI` |
| `REACT_APP_API_URL` | Variable CRA obsolète — utiliser `NEXT_PUBLIC_BACKEND_URL` |
| `REACT_APP_AUDIT_BOOKING_URL` | Variable CRA obsolète — non définie sur Render |
| `REACT_APP_AUDIT_PAYMENT_URL` | Variable CRA obsolète — non définie sur Render |
| Tout autre alias | Non défini sur Render → non supporté |

### Comportement en cas d'absence

- Le code doit **échouer explicitement** avec un message d'erreur clair.
- **Interdit** : fallback silencieux (`or 'valeur'`, `|| 'valeur'`) pour les variables critiques.
- Les tests locaux peuvent utiliser des valeurs simulées, mais ces valeurs ne valident **jamais** un comportement de production.

---

## 3. DÉPLOIEMENT

| Service | URL | Plateforme |
|---------|-----|------------|
| Frontend | https://israelgrowthventure.com | Render — Static Site |
| Backend  | https://igv-cms-backend.onrender.com | Render — Web Service |

- Frontend build path Render : `build/`
- Backend démarre avec `uvicorn server:app`
- Après tout push backend : redémarrage automatique sur Render → seeds idempotents s'exécutent

---

## 4. INTERNATIONALISATION (i18n)

### Langues
| Code | Langue | Direction | Défaut |
|------|--------|-----------|--------|
| `fr` | Français | LTR | ✅ `fallbackLng` |
| `en` | Anglais  | LTR | — |
| `he` | Hébreu   | **RTL** | — |

### Règles i18n obligatoires
- **Toute nouvelle clé** → ajouter dans les 3 fichiers : `src/i18n/locales/fr.json`, `en.json`, `he.json`
- **Fallback** : si clé manquante en EN ou HE, i18next affiche le FR
- **Ne jamais hardcoder du texte visible** en dehors des fichiers de traduction
- Les traductions auto du backend (`simple_translate`) ne remplacent pas une vraie traduction HE

### RTL — Hébreu
- Le `<html dir>` est basculé automatiquement par `src/i18n/config.js` via `i18n.on('languageChanged')`
- **Règles RTL dans le code :**
  - Utiliser `dir="rtl"` sur les conteneurs HE isolés (ex. CTA, divs inline)
  - Tailwind : utiliser `rtl:` variants ou `[dir='rtl']:` pour les marges/paddings directionnels
  - PDF HE : utiliser `python-bidi` + `arabic-reshaper` (déjà en requirements.txt)
  - Ne jamais utiliser `text-align: left` hardcodé — utiliser `text-start` (Tailwind) ou `text-align: start`
  - Ne jamais utiliser `margin-left`/`padding-left` hardcodé — utiliser `ms-*` / `ps-*` (Tailwind)

---

## 5. BLOG / ARTICLES

### Modèle MongoDB (`blog_articles`)
```
slug           : string   — ex. "expansion-israel-5-erreurs" (même pour toutes langues)
language       : "fr"|"en"|"he"
group_slug     : string   — identifiant cross-langue (= slug FR en général)
title          : string
excerpt        : string   — première phrase / résumé (max 500 chars)
content        : string   — HTML complet (rendu par dangerouslySetInnerHTML)
category       : string   — ex. "Future Commerce"
image_url      : string
published      : bool
tags           : string[]
views          : int
```

### Règle critique : `content` vs `excerpt`
- L'API liste (`GET /api/blog/articles`) EXCLUT `content` (projection `{"content": 0}`) → normal
- L'API détail (`GET /api/blog/articles/{slug}`) retourne le `content` complet → c'est ce que le renderer affiche
- **Si la page n'affiche que la première phrase** → le champ `content` en DB est vide ou incomplet
- **Ne jamais corriger le renderer** pour ce symptôme — vérifier d'abord le contenu en DB

### Pattern articles : fichiers `.md` → seed idempotent
1. Créer `articles/{fr,en,he}/{slug}.md` avec le contenu complet
2. Le seed lit le `.md`, convertit via `markdown-it-py` (html=True), met à jour le `content` en DB
3. Le seed ne met à jour QUE si `len(content) < 500` (idempotent)
4. **FAQ en accordéon** : utiliser `<details>/<summary>` HTML directement dans le `.md`

### Articles existants (ne pas supprimer)
| Slug | group_slug | Langues |
|------|-----------|---------|
| `alyah-franchise-entrepreneur` | `alyah-franchise-entrepreneur` | fr, en, he |
| `expansion-israel-5-erreurs`   | `expansion-israel-5-erreurs`  | fr, en, he |

### Routes frontend blog
- Liste : `/future-commerce/`
- Article : `/future-commerce/{slug}/`
- Toujours utiliser `forcedLang='fr'` dans `BlogArticleClient` (la langue est gérée par i18n côté client)

---

## 6. ROUTES PRINCIPALES

| Route | Vue | Description |
|-------|-----|-------------|
| `/` | `NewHome.js` | Page d'accueil |
| `/future-commerce/` | `FutureCommerce.js` | Liste articles blog |
| `/future-commerce/{slug}/` | `BlogArticle.js` | Article détail |
| `/packs` | `Packs.js` | Offres / packs |
| `/alyah-pro` | `AlyahPro.js` | Service Alyah Pro |
| `/audit` | `Audit.js` | Audit commercial |
| `/mini-analyse` | `MiniAnalysis.js` | Analyse IA |
| `/contact` | `Contact.js` | Contact |
| `/admin/` | `AdminDashboard.js` + `BlogManager.js` | CMS admin |

---

## 7. RÈGLES DE DÉVELOPPEMENT

### Général
- **Pas de TypeScript** — tout en `.js` / `.jsx`
- **Pas de hardcoding HTML** dans les fichiers Python (server.py) — utiliser des fichiers `.md`
- **Pas de création de nouveaux fichiers** sauf si strictement nécessaire
- **Seeds idempotents** : toujours vérifier l'état avant d'écrire en DB

### Contenu article
- Le contenu complet va dans `articles/{lang}/{slug}.md`
- markdown-it-py rend le markdown + HTML passthrough (`html: True`)
- Le pack CTA doit pointer vers `/packs`
- La FAQ doit utiliser `<details>/<summary>` (accordéon natif HTML)

### Git
- Message de commit : format `fix(scope): description concise`
- Toujours committer avec `https://claude.ai/code/session_<id>` en footer
- Push : `git push -u origin claude/<nom>-<sessionId>`

### API appels côté frontend
- Utiliser `apiClient` depuis `src/api/client.js` (jamais `fetch` brut ou axios direct)
- Routes canoniques dans `src/api/routes.js`
- Timeout AI : 60s, Standard : 8s

### Images
- Stockées dans `public/images/`
- `next.config.js` : `images.unoptimized: true` (export statique)
- Format recommandé : `.webp`

---

## 8. POINTS D'ATTENTION CONNUS

1. **Export statique** : `output: 'export'` → pas de SSR dynamique, tout est client-side après hydratation
2. **`generateStaticParams`** : fonctionne à build time — si un article est ajouté après le dernier build, il faut rebuilder le frontend pour générer la page statique
3. **react-router-dom shimé** : `useParams()`, `useNavigate()`, etc. passent par `app/lib/router-shim.jsx` — ne pas importer react-router-dom directement dans les composants `app/`
4. **Quill + SSR** : React Quill ne supporte pas le SSR → utiliser `'use client'` + `dynamic(() => import('react-quill'), { ssr: false })`
5. **RTL Quill** : ajouter `dir="rtl"` sur le wrapper Quill pour les articles HE
6. **markdown-it-py** : installé sur Render mais pas forcément en local → le seed a un `try/except ImportError`
7. **CORS** : le backend autorise le frontend via CORSMiddleware — pas de proxy Next.js nécessaire
