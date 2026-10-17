"""GET /audit/v1/standings/{league_id}"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import League, Sport, Match, MatchEvent
from app.api.events import _compute_score_from_events
from app.services.standings import compute_standings

router = APIRouter()


@router.get("/audit/v1/standings/{league_id}")
async def get_standings(league_id: str, db: AsyncSession = Depends(get_db)):
    league = await db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail={"error": {
            "code": "LEAGUE_NOT_FOUND", "message": f"League {league_id} not found", "details": {}
        }})

    sport = await db.get(Sport, league.sport_id)

    # Get all fixtures for this league
    matches_result = await db.execute(
        select(Match).where(Match.league_id == league_id)
    )
    matches = matches_result.scalars().all()

    # Build score projections for all matches
    match_scores = {}
    fixtures_list = []
    for m in matches:
        ev_result = await db.execute(
            select(MatchEvent).where(MatchEvent.match_id == m.match_id).order_by(MatchEvent.sequence)
        )
        events = ev_result.scalars().all()
        proj = _compute_score_from_events(sport, m, events)
        match_scores[m.match_id] = proj
        fixtures_list.append({"match_id": m.match_id, "home": m.home_team_id, "away": m.away_team_id})

    league_data = {
        "league_id": league.league_id,
        "sport_id": league.sport_id,
        "teams": league.teams,
        "fixtures": fixtures_list,
        "points_win": league.points_win,
        "points_draw": league.points_draw,
        "points_loss": league.points_loss,
        "tie_break_order": league.tie_break_order,
        "qualification_spots": league.qualification_spots,
        "lots_seed": league.lots_seed,
        "sport_config": {
            "scoring_model": sport.scoring_model,
            "periods": sport.periods
        }
    }

    return compute_standings(league_data, match_scores)
