"""GET /health and POST /audit/v1/reset"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.seed import wipe_all, seed_baseline

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "error"})


@router.post("/audit/v1/reset")
async def reset(body: dict = None, db: AsyncSession = Depends(get_db)):
    if body is None:
        body = {}
    seed = body.get("seed", 42)
    stock = body.get("stock", {"var-jersey-001-M": 1, "var-jersey-001-L": 5})

    await wipe_all(db)
    await seed_baseline(db, seed=seed, stock=stock)

    return {
        "status": "reset_complete",
        "seed": seed,
        "sports": ["football", "basketball", "cricket", "esports"],
        "tenants": ["tenant-alpha", "tenant-beta"],
        "stock": stock
    }
