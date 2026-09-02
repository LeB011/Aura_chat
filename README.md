# Aura Hub

**Le centre de contrôle premium de vos agents IA.**

Aura Hub est une plateforme SaaS multi-tenant qui regroupe plusieurs agents IA
autour d'un dashboard unique. Le premier agent, **Prospect AI**, est un
assistant de prospection B2B avec analyse IA, scoring et génération de messages
gardant l'humain dans la boucle.

Les autres agents (Mail AI, Admin AI, Business AI, Content AI, Custom Agent)
sont visibles en "Coming soon" et l'architecture est prête pour les ajouter
sans refonte.

## Stack

- **Backend** : FastAPI (Python 3.11) — routes modulaires, providers échangeables,
  services isolés (`ai_service`, `prospect_provider`).
- **Frontend** : React 19 + Tailwind + shadcn/ui + recharts + framer-motion + sonner.
- **Base de données** : MongoDB (via Motor, async).
- **Auth** : JWT + bcrypt, multi-tenant strict via `organization_id`.
- **LLM** : OpenAI GPT-5.4 via la librairie interne `emergentintegrations` et
  la clé universelle Emergent (`EMERGENT_LLM_KEY`). Peut être remplacée par une
  clé OpenAI standard.

## Architecture

```
/app
├── backend/
│   ├── server.py                # Entrée FastAPI (mount /api)
│   ├── db.py                    # Connexion Mongo
│   ├── auth.py                  # JWT + bcrypt + get_current_user
│   ├── models.py                # Pydantic models
│   ├── providers/
│   │   └── prospect_provider.py # MockProvider + registry extensible
│   ├── services/
│   │   └── ai_service.py        # Analyse + génération de messages
│   └── routes/
│       ├── auth_routes.py
│       ├── agents_routes.py
│       ├── prospects_routes.py
│       ├── messages_routes.py
│       └── misc_routes.py       # activities, security, integrations, settings, analytics, demo
└── frontend/
    └── src/
        ├── App.js
        ├── context/AppContext.js    # auth + thème + langue + test mode
        ├── lib/api.js               # axios + token
        ├── lib/i18n.js              # dictionnaire FR/EN
        ├── components/layout/       # Sidebar, Topbar, AppShell
        └── pages/                   # Login, Dashboard, ProspectAI, ...
```

## Installation locale

### Prérequis
- Python 3.11+, Node 18+, yarn, MongoDB local

### Backend

```bash
cd backend
cp .env.example .env  # renseigner les variables
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
cp .env.example .env  # renseigner REACT_APP_BACKEND_URL
yarn install
yarn start
```

## Variables d'environnement

### `backend/.env`
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=aura_hub
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-...       # ou OPENAI_API_KEY
JWT_SECRET=change_me_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
```

### `frontend/.env`
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Providers échangeables

Aura Hub est conçu autour d'interfaces provider pour rester portable :
- `ProspectSearchProvider` (mock → Google Places → annuaires → CSV)
- `LlmChat` (OpenAI GPT-5.4, Claude Sonnet, Gemini — via emergentintegrations)
- Intégrations : SMTP, Gmail, Google Sheets, CRM, Make, Zapier, Webhook, CSV

## Test Mode / Sandbox

`Organization.test_mode = true` par défaut. Dans ce mode :
- Les analyses IA renvoient des données mock (aucune consommation LLM).
- Les envois sont **simulés** — aucun message réel n'est envoyé.
- Un bandeau orange le rappelle en permanence en haut de l'application.

## Kill switch

Le bouton "STOP AGENT" (Prospect AI) et le Security Center exposent un
kill switch qui bloque instantanément tout nouvel envoi tant qu'il est actif.

## Multi-tenant SaaS

Chaque document Mongo est scoping par `organization_id`. L'auth JWT porte
`organization_id` et `role` (`superadmin`/`owner`/`admin`/`member`). Prêt pour
inviter d'autres utilisateurs et ajouter Stripe plus tard sans refonte.

## Roadmap V2 (extraits)

- Real providers (Google Places, annuaires officiels)
- SMTP réel + tracking d'ouverture
- Stripe billing (Starter / Business / Pro)
- Password reset + invitations d'équipe
- Super Admin panel

## Licence

Propriétaire — © 2026 Aura Hub.
