"""POST /audit/v1/sports — Mystery sport from JSON"""
import re
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import Sport

router = APIRouter()

SPORT_ID_RE = re.compile(r'^[a-z0-9_-]{2,40}$')
EVT_KEY_RE = re.compile(r'^[a-z0-9_]{1,40}$')

VALID_OVERTIME_POLICIES = {"none", "extra_time", "shootout", "golden_score", "super_over"}
VALID_TIE_BREAK = {"h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"}
DEFAULT_TIE_BREAK = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]


def _err(code, msg, details=None):
    from fastapi import HTTPException
    raise HTTPException(status_code=400 if code == "VALIDATION_ERROR" else 409,
                        detail={"error": {"code": code, "message": msg, "details": details or {}}})


@router.post("/audit/v1/sports", status_code=201)
async def create_sport(body: dict, db: AsyncSession = Depends(get_db)):
    bad_fields = []

    sport_id = body.get("sport_id", "")
    if not SPORT_ID_RE.match(sport_id):
        bad_fields.append("sport_id")

    name = body.get("name", "")
    if not isinstance(name, str) or not 1 <= len(name) <= 80:
        bad_fields.append("name")

    scoring_model = body.get("scoring_model")
    if scoring_model not in ("event", "innings", "round"):
        bad_fields.append("scoring_model")

    periods = body.get("periods")
    if not isinstance(periods, dict):
        bad_fields.append("periods")
    else:
        if scoring_model == "event":
            if not (isinstance(periods.get("count"), int) and periods["count"] >= 1 and
                    isinstance(periods.get("duration_minutes"), int) and periods["duration_minutes"] >= 1):
                bad_fields.append("periods")
        elif scoring_model == "innings":
            for k in ["innings_per_team", "overs_per_innings", "balls_per_over", "wickets_per_innings"]:
                if not isinstance(periods.get(k), int) or periods[k] < 1:
                    bad_fields.append("periods")
                    break
        elif scoring_model == "round":
            bo = periods.get("best_of")
            if not isinstance(bo, int) or bo < 1 or bo % 2 == 0:
                bad_fields.append("periods")

    scoring_events = body.get("scoring_events")
    if not isinstance(scoring_events, dict) or len(scoring_events) < 1:
        bad_fields.append("scoring_events")
    else:
        for k, v in scoring_events.items():
            if not EVT_KEY_RE.match(k):
                bad_fields.append("scoring_events")
                break
            if scoring_model == "event" and not isinstance(v.get("points"), int):
                bad_fields.append("scoring_events")
                break
            if scoring_model == "innings":
                if not isinstance(v.get("runs"), int) or not isinstance(v.get("legal_ball"), bool) or not isinstance(v.get("wicket"), bool):
                    bad_fields.append("scoring_events")
                    break
            if scoring_model == "round" and not isinstance(v.get("rounds"), int):
                bad_fields.append("scoring_events")
                break

    draw_allowed = body.get("draw_allowed")
    if not isinstance(draw_allowed, bool):
        bad_fields.append("draw_allowed")

    overtime = body.get("overtime")
    if not isinstance(overtime, dict) or overtime.get("policy") not in VALID_OVERTIME_POLICIES:
        bad_fields.append("overtime")

    tie_break_order = body.get("tie_break_order", DEFAULT_TIE_BREAK)
    if not isinstance(tie_break_order, list) or len(set(tie_break_order)) != len(tie_break_order):
        bad_fields.append("tie_break_order")
    for item in tie_break_order:
        if item not in VALID_TIE_BREAK:
            bad_fields.append("tie_break_order")
            break
    if "draw_lots" not in tie_break_order:
        tie_break_order = [x for x in tie_break_order if x != "draw_lots"] + ["draw_lots"]

    roster = body.get("roster")
    if not isinstance(roster, dict):
        bad_fields.append("roster")
    else:
        mn = roster.get("min_squad_size")
        mx = roster.get("max_squad_size")
        if not isinstance(mn, int) or not isinstance(mx, int) or mn < 1 or mx < mn:
            bad_fields.append("roster")

    if bad_fields:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR",
            "message": "Schema validation failed",
            "details": {"fields": list(set(bad_fields))}
        }})

    # Check duplicate
    existing = await db.get(Sport, sport_id)
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail={"error": {
            "code": "SPORT_EXISTS", "message": f"Sport {sport_id} already exists.", "details": {}
        }})

    config = {
        "sport_id": sport_id, "name": name, "scoring_model": scoring_model,
        "periods": periods, "scoring_events": scoring_events, "draw_allowed": draw_allowed,
        "overtime": overtime, "tie_break_order": tie_break_order, "roster": roster
    }

    sport = Sport(
        sport_id=sport_id, name=name, scoring_model=scoring_model,
        periods=periods, scoring_events=scoring_events, draw_allowed=draw_allowed,
        overtime=overtime, tie_break_order=tie_break_order, roster_config=roster
    )
    db.add(sport)
    await db.commit()

    return {"sport_id": sport_id, "status": "created", "config": config}
