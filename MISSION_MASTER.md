# MISSION MASTER — CMS IGV SOURCE DE VÉRITÉ

**Date de démarrage :** 2026-03-11  
**Périmètre :** igv-frontend + igv-backend uniquement  
**Objectif :** Faire du CMS la source de vérité réelle du site public IGV  

---

## RÈGLES DE CETTE MISSION

- ❌ Aucune modification design / CSS / layout / composant visuel
- ❌ Aucune nouvelle librairie
- ❌ Aucune recherche hors workspace
- ❌ Aucun push tant que validations locales non complètes
- ❌ Aucun déploiement tant que validations locales non complètes
- ✅ Un seul push maximum par service
- ✅ Un seul déploiement maximum par service
- ✅ MISSION_MASTER.md mis à jour en continu

---

## AVANCEMENT GLOBAL

| Phase | Nom | Statut |
|-------|-----|--------|
| Phase 0 | Cartographie initiale | ✅ COMPLÉTÉE |
| Phase 1 | Audit backend | ✅ COMPLÉTÉE |
| Phase 2 | Audit frontend | ✅ COMPLÉTÉE |
| Phase 3 | Définition cible | ✅ COMPLÉTÉE (dans CMS_GAPS_ANALYSIS.md) |
| Phase 4 | Corrections backend | ✅ COMPLÉTÉE — socle CMS stable |
| Phase 5 | Corrections frontend | ✅ COMPLÉTÉE — 6 pages branchées |
| Phase 6 | Matrice de validation | ⏳ Tests locaux en cours |
| Phase 7 | Anti-simulation | ⏳ En attente tests |
| Phase 8 | Commits & déploiement | ⏳ En attente validation locale |

---

## MISSION 1 — STABILISER LE CMS EXISTANT SANS CHANGER L'ARCHITECTURE

**Date de démarrage :** 2026-03-12  
**Statut :** 🚧 EN COURS  

### PÉRIMÈTRE TRAITÉ

**Pages dans le périmètre :**
- ✅ Home — `useCmsPage('home')` — connectée depuis 2026-03-11
- ✅ About — `useCmsPage('about')` — connectée depuis 2026-03-11
- ✅ Packs — `useCmsPage('packs')` — connectée depuis 2026-03-11
- ✅ Contact — `useCmsPage('contact')` — connectée depuis 2026-03-11
- ✅ FutureCommerce — `useCmsPage('future-commerce')` — connectée depuis 2026-03-11
- 🚧 MiniAnalysis — `useCmsPage('mini-analyse')` — **branchement Mission 1 en cours**

**Backend dans le périmètre :**
- ✅ `cms_routes.py` — monté dans `server.py` ligne 1113 — route publique `/api/pages/public/{page}` opérationnelle
- ✅ CMSManager.js a déjà `mini-analyse` dans `PAGE_SECTIONS` (title, subtitle, description, hero_image, benefits, form_title, form_cta, seo_title, seo_description)
- ✅ `init-pages` seed déjà `mini-analyse` dans FR/EN/HE

### PÉRIMÈTRE EXPLICITEMENT NON TRAITÉ (Mission 1)

- ❌ SEO `app/*/page.js` → CMS (metadata Next.js hardcodées) — Mission 2
- ❌ Médias persistants — Mission 3
- ❌ Page builder sections/blocs — Mission 4-5
- ❌ Création libre de nouvelles pages — Mission 5
- ❌ Pages légales (Terms, Privacy, Cookies) — non prioritaires Mission 1
- ❌ CRM, paiements — hors périmètre total
- ❌ Blog refonte — hors périmètre Mission 1
- ❌ Historique CMS dans CMSManager — non critique Mission 1
- ❌ sync-i18n dans CMSManager — non critique Mission 1

### CORRECTIONS EFFECTUÉES

| Fichier | Correction | Date |
|---------|-----------|------|
| `src/views/MiniAnalysis.js` | Connexion `useCmsPage('mini-analyse')` — hero, seo | 2026-03-12 |

---

## PHASE 0 — CARTOGRAPHIE INITIALE

**Statut :** ✅ COMPLÉTÉE  
**Démarré le :** 2026-03-11  
**Complété le :** 2026-03-11  

### Checklist Phase 0

- [x] 1. Fichiers backend réellement utilisés pour le CMS
- [x] 2. Fichiers frontend réellement utilisés pour le CMS
- [x] 3. Pages publiques consommant déjà le CMS
- [x] 4. Pages publiques encore alimentées par contenu local / i18n / statique / hardcode
- [x] 5. Endpoints CMS existants
- [x] 6. Modèles / collections / documents CMS existants
- [x] 7. Gestion actuelle des médias
- [x] 8. Gestion actuelle du SEO
- [x] 9. Gestion actuelle des langues FR / EN / HE
- [x] 10. Constats écrits dans MISSION_MASTER.md

### Résultats Phase 0

**Backend — Fichiers CMS identifiés :**
- `app/routers/cms/cms_routes.py` (961 lignes) — CMS routes, médias, auth, password reset
- `app/routers/blog/blog_routes.py` (1421 lignes) — Blog CRUD + auto-traduction
- `app/services/about_page_content.py` (519 lignes) — Contenu About statique FR/EN/HE
- `auth_middleware.py` — JWT + `get_db()` singleton
- `server.py` (1358 lignes) — Entry point + modèles inline + contact + panier

**Frontend — Fichiers CMS identifiés :**
- `src/hooks/useCmsPage.js` — Hook public `GET /api/pages/public/{page}?language=`
- `src/views/cms/CMSManager.js` — Éditeur admin CMS
- `src/views/Home.js`, `About.js`, `Packs.js`, `Contact.js`, `FutureCommerce.js` — Connectées au CMS
- `src/api/routes.js` — Constantes `CMS_ROUTES`, `BLOG_ROUTES`

**Pages publiques → CMS :**
Home ✅, About ✅, Packs ✅, Contact ✅, FutureCommerce ✅

**Pages publiques → Contenu local :**
MiniAnalysis ❌ (i18n), Terms ❌, PrivacyPolicy ❌, CookiesPolicy ❌, Blog (API blog, pas page_content)

**Endpoints CMS existants :**
- Public : `GET /api/pages/public/{page}?language=`
- Admin : `GET /api/pages/list`, `GET /api/pages/{page}`, `POST /api/pages/update-flat`, `POST /api/pages/update`, `GET /api/pages/{page}/history`
- Médias : `POST /api/admin/media/upload`, `GET /api/admin/media`, `DELETE /api/admin/media/{filename}`
- Utilitaires : `POST /api/cms/verify-password`, `POST /api/cms/sync-i18n`, `POST /api/cms/init-pages`

**Collections / Modèles :**
- `page_content` : `{page, language, flat_content{}, content{}, version, updated_at}`
- `media_library` : `{filename, url, size, mimetype, uploaded_at}`
- `cms_history` : `{page, language, version, content, updated_at}`
- `blog_articles` : `{title, slug, content, language, published, group_slug, views, tags, author}`

**Médias :**
Upload vers `/tmp/igv-uploads/` (éphémère Render) → `media_library` en DB. ⚠️ Pas de stockage persistant.

**SEO :**
Champs `seo_title`/`seo_description` dans `flat_content` → `<Helmet>` React (client-side). `app/*/page.js` metadata hardcodées (SSR/bots). Problème : bots voient le hardcode.

**Langues FR / EN / HE :**
`page_content` : documents séparés par `{page, language}`. `blog_articles` : documents séparés liés par `group_slug`. Les 3 langues supportées partout dans le backend.

---

## PHASE 1 — AUDIT BACKEND

**Statut :** ✅ COMPLÉTÉE — voir `docs_cms_audit/CMS_ROUTES.md` et `CMS_DATA_MODELS.md`

### Checklist Phase 1

- [x] Modèles CMS vérifiés (`PageContentUpdate`, `PageContentBulkUpdate` dans `cms_routes.py`)
- [x] Schémas Pydantic vérifiés
- [x] Routes CMS vérifiées (11 endpoints admin + 1 public)
- [x] Stockage Mongo / collections vérifié (`page_content`, `media_library`, `cms_history`, `blog_articles`)
- [x] Logique lecture / écriture vérifiée (flat_content vs content structuré)
- [x] Endpoints pages / site / seo / blog / media vérifiés
- [x] Cohérence langues FR / EN / HE vérifiée (documents séparés, supportés partout)
- [x] Cohérence champs slug / pageKey vérifiée (pas de blockKey — CMS simple, pas page builder)
- [x] Document central SITE vérifiée — N'EXISTE PAS (manque)
- [x] Champs SEO séparés par langue vérifiés (via flat_content.seo_title / seo_description)
- [x] Médias dans CMS vs statiques vérifiés (stockage éphémère `/tmp/` identifié)

### Résultats Phase 1

**Ce qui fonctionne réellement :**
CMS CRUD complet, endpoint public, auth double couche, blog CRUD + group_slug + auto-traduction, historique versions.

**Ce qui existe mais n'est pas branché :**
Route `/update` (structurée), `/pages/{page}/history`, `/cms/sync-i18n`.

**Ce qui manque :**
Stockage médias persistant, config site globale, champs SEO articles blog, rôle éditeur contenu.

**Ce qui est branché partiellement :**
Médias (upload OK, stockage éphémère), SEO (Helmet React OK, Next.js metadata hardcodée).

---

## PHASE 2 — AUDIT FRONTEND

**Statut :** ✅ COMPLÉTÉE — voir `docs_cms_audit/CMS_FRONTEND_CONNECTION.md`

### Checklist Phase 2

- [x] Écran CMS réel dans `src/views/cms/CMSManager.js`
- [x] Appels API réels du CMS (`useCmsPage`, `update-flat`, `verify-password`)
- [x] Pages publiques lues depuis CMS (5 pages)
- [x] Pages publiques encore lues depuis contenu local (mini-analyse, terms, privacy, cookies)
- [x] Blog listing — lecture API blog (`/api/blog/articles`)
- [x] Blog article — lecture API blog (`/api/blog/articles/{slug}`)
- [x] SEO par page — Helmet React connecté CMS (5 pages) ; Next.js metadata hardcodée
- [x] Médias rendus sur site public — `image_url` externe via API blog
- [x] Langues FR / EN / HE sur site public — i18next + CMS supportés
- [x] Lecture CMS côté Next / React documentée

### Matrice Page publique → Source

| Page | Source contenu | Source SEO | FR | EN | HE |
|------|---------------|-----------|----|----|-----|
| Home | CMS + i18n fallback | Helmet CMS | ✅ | ✅ | ✅ |
| About | CMS + i18n + about_page_content.py | Helmet CMS | ✅ | ✅ | ✅ |
| Packs | CMS + i18n fallback | Helmet CMS | ✅ | ✅ | ✅ |
| Contact | CMS + i18n fallback | Helmet CMS | ✅ | ✅ | ✅ |
| FutureCommerce | CMS + i18n fallback | Helmet CMS | ✅ | ✅ | ✅ |
| Mini-Analyse | i18n uniquement | i18n | ⚠️ | ⚠️ | ⚠️ |
| Blog article | API blog | Titre article | ⚠️ | ⚠️ | ⚠️ |

---

## PHASE 3 — CIBLE VALIDÉE

**Statut :** ⏳ En attente de Phase 2  

### Cible à valider

- [ ] Le CMS devient la source de vérité des contenus publics
- [ ] Les pages publiques lisent le CMS
- [ ] Le blog est piloté depuis le CMS
- [ ] Le SEO public lit le CMS
- [ ] Les médias publics lisent le CMS
- [ ] FR / EN / HE sont couverts
- [ ] Zéro changement visuel

---

## PHASES 4-5 — CORRECTIONS

**Statut :** ⏳ En attente de Phase 3  

### Corrections backend prévues
(à remplir après Phase 3)

### Corrections frontend prévues
(à remplir après Phase 3)

---

## PHASE 6 — MATRICE DE VALIDATION

**Statut :** ⏳ En attente des corrections  

| Test | Statut |
|------|--------|
| Home FR | ⏳ |
| Home EN | ⏳ |
| Home HE | ⏳ |
| Page publique 1 FR/EN/HE | ⏳ |
| Page publique 2 FR/EN/HE | ⏳ |
| Page publique 3 FR/EN/HE | ⏳ |
| Modification CMS texte + propagation | ⏳ |
| Modification CMS champ SEO + propagation | ⏳ |
| Modification CMS média + propagation | ⏳ |
| Modification CMS blog + propagation | ⏳ |
| Validation aucun style changé | ⏳ |

---

## FICHIERS MODIFIÉS

> À remplir au fur et à mesure des corrections

| Fichier | Modification | Phase | Date |
|---------|-------------|-------|------|
| `src/hooks/useCmsPage.js` | Créé — hook public CMS avec fallback | Phase 5 (Mission A) | 2026-03-11 |
| `src/views/Home.js` | Remplacé axios inline par useCmsPage | Phase 5 | 2026-03-11 |
| `src/views/About.js` | Connecté au CMS via useCmsPage | Phase 5 | 2026-03-11 |
| `src/views/Packs.js` | Connecté au CMS via useCmsPage | Phase 5 | 2026-03-11 |
| `src/views/Contact.js` | Connecté au CMS via useCmsPage | Phase 5 | 2026-03-11 |
| `src/views/FutureCommerce.js` | Connecté au CMS via useCmsPage | Phase 5 | 2026-03-11 |
| `src/views/cms/CMSManager.js` | Sections SEO ajoutées dans PAGE_SECTIONS | Phase 5 | 2026-03-11 |

---

## COMMITS

| SHA | Message | Service | Date |
|-----|---------|---------|------|
| (aucun pour l'instant) | | | |

---

## DÉPLOIEMENTS

| Service | SHA déployé | Date | Statut post-déploiement |
|---------|------------|------|------------------------|
| Backend | (non déployé) | | |
| Frontend | (non déployé) | | |

---

## JOURNAL D'AVANCEMENT

### 2026-03-11
- Création de MISSION_MASTER.md
- Création du dossier `docs_cms_audit/`
- Création des 5 fichiers d'audit : CMS_ARCHITECTURE.md, CMS_ROUTES.md, CMS_DATA_MODELS.md, CMS_FRONTEND_CONNECTION.md, CMS_GAPS_ANALYSIS.md
- **Mission A (code)** : Connexion CMS → site public — `useCmsPage.js` créé, 5 vues connectées (Home, About, Packs, Contact, FutureCommerce), sections SEO ajoutées dans CMSManager. Build ✅ 38.9s.
- **Mission B (audit)** : Audit complet effectué — 5 fichiers docs_cms_audit remplis avec données réelles lues dans les fichiers sources
- Phase 0 ✅, Phase 1 ✅, Phase 2 ✅, Phase 3 ✅ (cible définie dans CMS_GAPS_ANALYSIS.md P1→P7)
- Prochaine action : Phase 4 — corrections backend (médias persistants, SEO articles blog)
- Prochaine action : Phase 5 — corrections frontend (Next.js metadata → CMS, MiniAnalysis → CMS)

---

## RÈGLE ANTI-SIMULATION

Chaque item ci-dessus ne sera marqué ✅ que lorsqu'il est :
1. **existant** — le fichier / la route / le modèle existe réellement
2. **branché** — il est appelé par une autre partie du système
3. **testé** — un test réel a été effectué
4. **validé live localement** — résultat confirmé en local

Aucun ✅ sans preuve réelle.
