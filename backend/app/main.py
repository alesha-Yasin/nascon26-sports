"""
FastAPI main application entry point.
Brings up all routes, DB, middleware.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.database import engine, Base
from app.core.seed import wipe_all, seed_baseline
from app.core.database import AsyncSessionLocal

from app.api import health, sports, fixtures, leagues, events, standings, roster, checkout, rbac, offline_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed baseline data on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed if not already seeded
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text("SELECT COUNT(*) FROM sports"))
            count = result.scalar()
            if count == 0:
                await seed_baseline(db)
        except Exception:
            await seed_baseline(db)
    yield


app = FastAPI(title="NaSCon '26 Sports Platform", lifespan=lifespan)


# ── Body size limit middleware ─────────────────────────────────────────────
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_048_576:  # 1 MB
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "PAYLOAD_TOO_LARGE",
                               "message": "Request body exceeds 1 MB limit", "details": {}}}
        )
    return await call_next(request)


# ── Input validation: reject SQL injection / XSS in path params ────────────
# (handled by Pydantic and DB parameterization)

# ── Register all routers ──────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(sports.router)
app.include_router(fixtures.router)
app.include_router(leagues.router)
app.include_router(events.router)
app.include_router(standings.router)
app.include_router(roster.router)
app.include_router(checkout.router)
app.include_router(rbac.router)
app.include_router(offline_sync.router)
