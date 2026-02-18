# ============================================================
# MISSION MASTER - PAYMENT INIT / AUDIT FUNNEL
# ============================================================
# Date debut: 18 Fevrier 2026
# Statut: RESOLU - Pret pour config Monetico (TPE/KEY)
# ============================================================

## OBJECTIF

Corriger l'erreur 422 sur POST /api/monetico/init-payment quand pack=audit
afin que le tunnel audit.israelgrowthventure.com -> /payment?pack=audit fonctionne end-to-end.

---

## URLS

| Service | URL |
|---------|-----|
| Frontend prod | https://israelgrowthventure.com |
| Audit subdomain | https://audit.israelgrowthventure.com |
| Backend prod | https://igv-cms-backend.onrender.com |
| Endpoint paiement | POST /api/monetico/init-payment |

---

## DIAGNOSTIC - CAUSE RACINE (identifiee le 18/02/2026)

Le backend Render tournait sur un deploiement perime (build anterieur au commit 34ec0b6).
Ce vieux build avait une version de PaymentInitRequest avec 3 champs REQUIS absents du payload frontend :

- pack_type      : str (requis)     -> Non envoye du frontend
- customer_email : EmailStr (requis) -> Non envoye du frontend
- customer_name  : str (requis)     -> Envoye comme None -> refuse

Reponse Pydantic exacte recue :
  {"detail":[{"type":"missing","loc":["body","pack_type"],...},
             {"type":"missing","loc":["body","customer_email"],...},
             {"type":"missing","loc":["body","customer_name"],...}]}

Probleme secondaire : packPrice.currency = undefined -> envoi de symbole ('euro') au lieu du code ISO ('EUR')

---

## CORRECTIONS APPLIQUEES

### Backend - monetico_routes.py (commit 33eb7b6)
PaymentInitRequest mis a jour :
  - customer_email : Optional[EmailStr] = None  (etait requis)
  - customer_name  : Optional[str] = None       (etait requis)
  - pack_type      : Optional[str] = None       (etait requis)

### Frontend - src/utils/pricing.js (commit 56b5131)
  - Ajout de currencyCode ISO 4217 sur tous les packs de toutes les regions
  - audit: { ..., currencyCode: 'EUR' }

### Frontend - src/pages/Payment.js (commit 56b5131)
  - currency: packPrice.currencyCode || 'EUR'
  - Envoi de pack_type, customer_name, customer_email avec valeurs par defaut

---

## COMMITS

| SHA      | Repo         | Message                                             | Statut |
|----------|--------------|-----------------------------------------------------|--------|
| 33eb7b6  | igv-backend  | fix(payment): make pack_type, customer_email optional | OK    |
| 56b5131  | igv-frontend | fix(payment): send pack_type + ISO currency codes   | OK     |

---

## VALIDATION

Avant correction :
  POST -> 422 Unprocessable Entity (pack_type, customer_email, customer_name manquants)

Apres correction (avec payload complet) :
  POST -> 500 Internal Server Error
  detail: "Le paiement Monetico n'est pas encore configure..."

422 RESOLU. Le 500 est attendu : MONETICO_TPE et MONETICO_KEY non configures dans Render.

---

## PROCHAINE ETAPE (action humaine requise)

Configurer dans le dashboard Render du service igv-cms-backend :

  MONETICO_TPE        = Numero TPE (contrat CIC/CM)
  MONETICO_KEY        = Cle securite (contrat CIC/CM)
  MONETICO_VERSION    = 3.0
  MONETICO_RETURN_URL = https://israelgrowthventure.com/payment/return
  MONETICO_NOTIFY_URL = https://igv-cms-backend.onrender.com/api/monetico/notify

---

## STATUT FINAL

  [x] Diagnostic 422
  [x] Fix backend PaymentInitRequest
  [x] Fix frontend payload + ISO currency
  [x] Push + Render redeploy declenche
  [ ] Monetico TPE/KEY configures        <- ACTION HUMAINE
  [ ] Test paiement end-to-end           <- Apres config Monetico

Derniere mise a jour: 18/02/2026
