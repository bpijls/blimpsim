# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Digital twin of a person-tracking camera blimp: a simulated hall, crowd and blimp whose camera feed drives and trains a tracking controller.

```
frontend (Vite+React, :3000) ──/api──▶ api (FastAPI, :8000) ──▶ postgres (pgvector)
                                              └──▶ vonk (LiteLLM, :4000)
```

## Running the stack

`./setup.sh` is the one-command bootstrap: creates `.env` from `.env.example`,
checks the required values are filled in and the Caddy network exists, then
brings the stack up. Or run it manually:

```bash
docker compose up -d --build     # first run / after dependency changes
docker compose up -d --build api # rebuild one service
docker compose logs -f api       # follow logs
docker compose exec api python -c "..."   # one-off in the container
docker compose down
```

`backend/app/` and `frontend/src/` are volume-mounted with hot reload. Anything
outside them — `requirements.txt`, `vite.config.js`, Dockerfiles — needs a
rebuild to take effect.

## Tests

Backend (pytest-asyncio against SQLite in memory — no Docker, no postgres, no vonk):
```bash
cd backend && ../.venv/bin/pytest tests/
cd backend && ../.venv/bin/pytest tests/test_api.py::test_health   # one test
cd backend && ../.venv/bin/ruff check app tests
```
`tests/conftest.py` sets `DATABASE_URL` and `VONK_KEY` before any app import and
overrides the `get_db` dependency; fixtures are `db_session` and `client`.

Frontend (Vitest + Testing Library):
```bash
cd frontend && npm test
cd frontend && npm run lint
```

## Architecture

```
backend/
  app/
    main.py        FastAPI app, CORS, lifespan (create_all on startup), router registration
    config.py      Pydantic Settings — the only place .env is read; vonk_key is required
    database.py    Async engine, SessionLocal, Base, get_db dependency
    models.py      SQLAlchemy ORM models
    schemas.py     Pydantic request/response schemas
    routers/       One file per resource group; mounted under /api
    services/
      ai.py        Shared AsyncVonk client — import `ai`, don't build your own
  tests/           conftest.py (SQLite + dependency override) + test_api.py

frontend/src/
  main.jsx         ReactDOM root
  App.jsx          Shell
  api.js           All fetch() wrappers — components never call fetch directly
  styles.css       All CSS

nginx/default.conf Production build only (SPA fallback + /api proxy)
```

## Key constraints

- **`VONK_KEY` has no default.** A missing key raises at startup rather than on
  the first LLM call. Never add a fallback value in code.
- **LLM access goes through the `vonk` package** (`app/services/ai.py`). Don't
  hand-roll an httpx or OpenAI client — fence/`<think>` stripping, retries and
  the 32K input+output ceiling are handled there.
- **Schema is created with `create_all` on startup.** Fine while prototyping;
  switch to Alembic once the schema starts changing under real data.
- The frontend dev server proxies `/api` to `http://api:8000` by Docker service
  name, so it only works from inside the compose network unless you set
  `VITE_API_BASE`.
