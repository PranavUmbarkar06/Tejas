# Tejas

Warm, premium React + FastAPI banking experience backed by the local user profile store,
the ChromaDB policy index, and the Gemini orchestrator.

## Run locally

Start the API from the project root:

```powershell
py -m pip install -r backend/requirements.txt
py -m uvicorn api:app --app-dir backend --reload --port 8000
```

In a second terminal, start the React app:

```powershell
cd frontend/Tejas
npm install
npm run dev
```

The Tejas frontend uses `http://localhost:8000` by default. Override it with a
`VITE_API_URL` environment variable when needed.

## API routes

- `GET /api/health`
- `GET /api/users/{uid}`
- `POST /api/scenario`
- `POST /api/chat`
- `POST /api/onboarding/upload`

The Demo Bypass loads `U001` (Ananya Rao) from
`database/users/users.json`. Chat attempts the Gemini + ChromaDB orchestrator
and returns a profile-aware offline advisory prompt if those optional services
are not configured.
