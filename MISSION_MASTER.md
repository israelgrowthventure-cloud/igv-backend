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


---

# ============================================================
# MISSION: BLOCK_AUDIT_BOOKING_UNDER_48H
# ============================================================
# Date: 21 Fevrier 2026
# Statut: COMPLETE - 3 preuves validees en production
# ============================================================

## OBJECTIF

Enforcer une regle metier stricte : aucun audit ne peut etre reserve
avec un delai inferieur a 48h. Bloquage cote frontend ET backend.

---

## IMPLEMENTATION

### Backend - app/routers/booking_routes.py

1. Constante non-overridable : _HARD_MIN_NOTICE_HOURS = 48
2. GET /availability : start_search = now + timedelta(hours=max(12, 48))
3. POST /book - Execution order (final):
   - Step 1: Parse start/end ISO -> HTTP 422 si invalide
   - Step 2: 48h guard (AVANT Google Cal) -> HTTP 400 si start < NOW+48h
   - Step 3: Google Cal connectivity -> HTTP 503 si non connecte
   - Step 4: Freebusy re-verify -> HTTP 409 si creneau pris
   - Step 5: Create event + send email
4. Timezone: Asia/Jerusalem. Naive datetimes assumed Jerusalem + warning log.

### Frontend - src/pages/Appointment.js

- BOOKING_MIN_HOURS = 48, isWithin48h(isoStart) helper
- useState selectedSlot: URL-param bypass bloque
- slotsByDay: filtre .filter(slot => !isWithin48h(slot.start))
- handleConfirm: guard avant fetch -> setFormError si isWithin48h
- HTTP 400 handler dans catch chain
- Banniere bleue au-dessus de la liste des creneaux

### i18n - fr/en/he

  booking.minNotice48h + booking.error48h ajoutes dans les 3 langues

---

## COMMITS

| SHA      | Repo         | Message                                                     | Statut |
|----------|--------------|-------------------------------------------------------------|--------|
| ed9315b  | igv-backend  | feat(booking): enforce 48h minimum notice rule (round 1)   | OK     |
| 7d88e04  | igv-backend  | fix(booking): move 48h guard BEFORE Google Calendar check  | OK     |
| 450cf88  | igv-frontend | feat(booking): enforce 48h minimum - filter, banner, i18n  | OK     |

---

## PREUVES PRODUCTION (21/02/2026 ~20:50 +02:00)

PREUVE 1 - GET /api/booking/availability?days=14
  -> First slot: 2026-02-24T12:00:00+02:00 (~63h from now)
  -> PASS: aucun creneau dans les 48 prochaines heures

PREUVE 2 - POST /api/booking/book avec slot dans ~13h
  -> HTTP 400
  -> {"detail":"Ce creneau n'est pas reservable : delai minimum 48h."}
  -> PASS

PREUVE 3 - POST /api/booking/book avec slot dans +49h
  -> HTTP 200 (48h rule passed, Google Calendar processed)
  -> PASS: slot valide non bloque

---

## STATUT FINAL

  [x] _HARD_MIN_NOTICE_HOURS = 48 (non-overridable)
  [x] GET /availability filtre creneaux < NOW+48h
  [x] POST /book HTTP 400 si start < NOW+48h
  [x] 48h guard AVANT check Google Calendar
  [x] Frontend filtre slots
  [x] Frontend banniere minNotice48h
  [x] Frontend guard handleConfirm + HTTP 400 handler
  [x] i18n FR + EN + HE
  [x] 3 preuves production validees
  [x] Push git backend 7d88e04 + frontend 450cf88

Derniere mise a jour: 21/02/2026
