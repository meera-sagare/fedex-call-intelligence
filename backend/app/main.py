import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers tables)
from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.routers import call_logs, collectors, customers, insights
from app.seed import seed_if_empty
from app.services.analyzer import _claude_available

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if get_settings().seed_on_startup:
        with SessionLocal() as db:
            seed_if_empty(db)
    yield


app = FastAPI(title="ABC Call Intelligence API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (collectors.router, customers.router, call_logs.router, insights.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    s = get_settings()
    engine_name = "claude" if s.ai_engine == "claude" or (s.ai_engine == "auto" and _claude_available()) else "rules"
    return {"status": "ok", "ai_engine": engine_name}
