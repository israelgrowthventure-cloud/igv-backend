# TODO_MASTER.md — Source de vérité

## CHECKLIST MISSION

- [x] Créer TODO_MASTER.md + REPORT_MIDWAY_CMD.md
- [x] Générer SITE_MAP.md (front + back) basé sur code réel
- [x] Localiser le système de templates emails
  - Backend: `crm_complete_routes.py` endpoints `/api/crm/emails/templates`
  - Stockage: MongoDB collection `email_templates`
  - Seed: `email_templates_seed.py` (4 templates × 3 langues = 12 docs)
  - Frontend: `src/pages/admin/EmailsPage.js` + `src/components/crm/EmailsTab.js`
- [x] Implémenter filtrage par langue (backend + frontend)
- [x] Ajouter 4 templates EN (dans email_templates_seed.py)
- [x] Ajouter 4 templates HE (RTL ok, dans email_templates_seed.py)
- [x] Police hébreu NotoSansHebrew ajoutée au repo
- [x] BiDi dépendances vérifiées dans requirements.txt
- [ ] Build frontend OK
- [ ] Déployer igv-backend (Render) + preuve SHA
- [ ] Déployer igv-frontend (Render) + preuve SHA
- [ ] Test prod : FR/EN/HE -> 4 templates visibles + preuve

---

## SUIVI DES COMMITS

| Repo | SHA | Date | Description |
|------|-----|------|-------------|
| igv-backend | En attente | - | BiDi + police + email templates filter |
| igv-frontend | En attente | - | Filtrage templates par langue UI |

---

## SUIVI DES DÉPLOIEMENTS RENDER

| Service | SHA déployé | Timestamp | Statut |
|---------|-------------|-----------|--------|
| igv-backend | - | - | En attente |
| igv-frontend | - | - | En attente |

---

## TESTS PROD

| Langue | Templates visibles | URL testée | Statut |
|--------|-------------------|------------|--------|
| FR | - | - | À tester |
| EN | - | - | À tester |
| HE | - | - | À tester |
