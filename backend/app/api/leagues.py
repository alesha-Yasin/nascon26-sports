"""POST /audit/v1/leagues — Register a league for standings"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import League, Sport, Match, AppState

router = APIRouter()

DEFAULT_TIE_BREAK = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]


@router.post("/audit/v1/leagues", status_code=201)
async def create_league(body: dict, db: AsyncSession = Depends(get_db)):
    league_id = body.get("league_id")
    sport_id = body.get("sport_id")
    teams = body.get("teams")
    fixtures = body.get("fixtures")

    if not league_id or not sport_id or not isinstance(teams, list) or not isinstance(fixtures, list):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "Missing required fields",
            "details": {"fields": ["league_id", "sport_id", "teams", "fixtures"]}
        }})

    if len(set(teams)) != len(teams) or not (2 <= len(teams) <= 40):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "teams must be unique 2-40",
            "details": {"fields": ["teams"]}
        }})

    # Sport must exist
    sport = await db.get(Sport, sport_id)
    if not sport:
        raise HTTPException(status_code=404, detail={"error": {
            "code": "SPORT_NOT_FOUND", "message": f"Sport {sport_id} not found", "details": {}
        }})

    # League id used?
    existing = await db.get(League, league_id)
    if existing:
        raise HTTPException(status_code=409, detail={"error": {
            "code": "LEAGUE_EXISTS", "message": f"League {league_id} already exists", "details": {}
        }})

    # Validate fixtures
    team_set = set(teams)
    existing_match_ids = set()
    for fx in fixtures:
        if fx.get("home") not in team_set or fx.get("away") not in team_set:
            raise HTTPException(status_code=400, detail={"error": {
                "code": "VALIDATION_ERROR",
                "message": f"Fixture team not in teams list",
                "details": {"fields": ["fixtures"]}
            }})
        if fx.get("home") == fx.get("away"):
            raise HTTPException(status_code=400, detail={"error": {
                "code": "VALIDATION_ERROR", "message": "home == away",
                "details": {"fields": ["fixtures"]}
            }})
        mid = fx.get("match_id")
        if mid in existing_match_ids:
            raise HTTPException(status_code=409, detail={"error": {
                "code": "MATCH_EXISTS", "message": f"Match {mid} already exists", "details": {}
            }})
        # Check globally
        existing_match = await db.get(Match, mid)
        if existing_match:
            raise HTTPException(status_code=409, detail={"error": {
                "code": "MATCH_EXISTS", "message": f"Match {mid} already exists", "details": {}
            }})
        existing_match_ids.add(mid)

    points = body.get("points", {})
    pw = points.get("win", 3)
    pd_ = points.get("draw", 1)
    pl = points.get("loss", 0)

    tbo = body.get("tie_break_order", sport.tie_break_order or DEFAULT_TIE_BREAK)
    if "draw_lots" not in tbo:
        tbo = [x for x in tbo if x != "draw_lots"] + ["draw_lots"]

    qual = body.get("qualification", {})
    spots = qual.get("spots")
    if spots is None or not (1 <= spots <= len(teams)):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "qualification.spots required 1..n",
            "details": {"fields": ["qualification"]}
        }})

    # Get default lots_seed from app state
    state = await db.get(AppState, "lots_seed")
    default_seed = int(state.value) if state else 42
    lots_seed = body.get("lots_seed", default_seed)

    # Create league
    league = League(
        league_id=league_id, tenant_id="tenant-alpha", sport_id=sport_id,
        teams=teams, points_win=pw, points_draw=pd_, points_loss=pl,
        tie_break_order=tbo, qualification_spots=spots, lots_seed=lots_seed
    )
    db.add(league)

    # Create match streams
    for fx in fixtures:
        match = Match(
            match_id=fx["match_id"], sport_id=sport_id, league_id=league_id,
            home_team_id=fx["home"], away_team_id=fx["away"], status="upcoming"
        )
        db.add(match)

    await db.commit()

    return {
        "league_id": league_id, "status": "created",
        "team_count": len(teams), "fixture_count": len(fixtures)
    }
