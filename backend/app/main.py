from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import blimp, datasets, runs, scenarios


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fine for a prototype; swap for Alembic once the schema starts moving.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="blimpsim", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router)
app.include_router(runs.router)
app.include_router(blimp.router)
app.include_router(datasets.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
