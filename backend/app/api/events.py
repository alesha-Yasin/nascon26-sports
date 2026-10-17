"""
POST /audit/v1/events — Append match events (event-sourced scoring)
GET  /audit/v1/score/{match_id} — Score projection from event log
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.signing import sign_payload
from app.models.models import Match, MatchEvent, Sport, League

router = APIRouter()

VALID_TRANSITIONS = {
    "upcoming": {"match_start", "compensation", "match_init"},
    "in_progress": {"score", "discipline", "tiebreak_winner", "match_end", "compensation"},
    "completed": {"compensation"},
}


def _409(code, msg, details=None):
    raise HTTPException(status_code=409, detail={"error": {
        "code": code, "message": msg, "details": details or {}
    }})


def _400(msg, fields=None):
    raise HTTPException(status_code=400, detail={"error": {
        "code": "VALIDATION_ERROR", "message": msg,
        "details": {"fields": fields or []}
    }})


def _compute_score_from_events(sport: Sport, match: Match, events: list) -> dict:
    """Rebuild score projection from event log."""
    compensated_ids = set()
    for ev in events:
        if ev.type == "compensation":
            compensated_ids.add(ev.payload.get("compensates"))

    status = "upcoming"
    home_score = 0
    away_score = 0
    home_fp = 0
    away_fp = 0
    tiebreak_winner = None
    home_legal_balls = 0
    away_legal_balls = 0
    home_wickets = 0
    away_wickets = 0

    scoring_model = sport.scoring_model
    se_cfg = sport.scoring_events
    periods_cfg = sport.periods

    for ev in events:
        if ev.event_id in compensated_ids:
            continue
        if ev.type == "compensation":
            continue

        payload = ev.payload
        if ev.type == "match_start":
            status = "in_progress"
        elif ev.type == "match_end":
            status = "completed"
        elif ev.type == "score":
            team_id = payload.get("team_id")
            etype = payload.get("event_type")
            cfg = se_cfg.get(etype, {})
            is_home = (team_id == match.home_team_id)
            if scoring_model == "event":
                pts = cfg.get("points", 0)
                if is_home:
                    home_score += pts
                else:
                    away_score += pts
            elif scoring_model == "innings":
                runs = cfg.get("runs", 0)
                legal = cfg.get("legal_ball", False)
                wicket = cfg.get("wicket", False)
                if is_home:
                    home_score += runs
                    if legal: home_legal_balls += 1
                    if wicket: home_wickets += 1
                else:
                    away_score += runs
                    if legal: away_legal_balls += 1
                    if wicket: away_wickets += 1
            elif scoring_model == "round":
                rds = cfg.get("rounds", 0)
                if is_home:
                    home_score += rds
                else:
                    away_score += rds
        elif ev.type == "discipline":
            team_id = payload.get("team_id")
            pts = payload.get("points", 0)
            if team_id == match.home_team_id:
                home_fp += pts
            else:
                away_fp += pts
        elif ev.type == "tiebreak_winner":
            tiebreak_winner = payload.get("team_id")

    # Outcome
    outcome = "pending"
    winner_tid = None
    tw_team = None
    if status == "completed":
        if home_score > away_score:
            outcome = "home_win"
            winner_tid = match.home_team_id
        elif away_score > home_score:
            outcome = "away_win"
            winner_tid = match.away_team_id
        elif sport.draw_allowed:
            outcome = "draw"
        elif tiebreak_winner:
            tw_team = tiebreak_winner
            if tiebreak_winner == match.home_team_id:
                outcome = "home_win"
                winner_tid = match.home_team_id
            else:
                outcome = "away_win"
                winner_tid = match.away_team_id
        else:
            outcome = "undecided"

    # Overs string
    bpo = periods_cfg.get("balls_per_over", 6) if scoring_model == "innings" else 1

    def overs_str(balls):
        return f"{balls // bpo}.{balls % bpo}" if scoring_model == "innings" else None

    events_out = []
    for ev in events:
        is_compensated = ev.event_id in compensated_ids
        comp_by = None
        if is_compensated:
            for e2 in events:
                if e2.type == "compensation" and e2.payload.get("compensates") == ev.event_id:
                    comp_by = e2.event_id
                    break
        events_out.append({
            "sequence": ev.sequence,
            "event_id": ev.event_id,
            "type": ev.type,
            "payload": ev.payload,
            "signature": ev.signature,
            "compensated": is_compensated,
            "compensated_by": comp_by
        })

    return {
        "match_id": match.match_id,
        "sport_id": sport.sport_id,
        "league_id": match.league_id,
        "status": status,
        "outcome": outcome,
        "winner_team_id": winner_tid,
        "tiebreak_winner_team_id": tw_team,
        "home": {
            "team_id": match.home_team_id,
            "score": home_score,
            "wickets": home_wickets if scoring_model == "innings" else None,
            "balls": home_legal_balls if scoring_model == "innings" else None,
            "overs": overs_str(home_legal_balls) if scoring_model == "innings" else None,
            "fair_play": home_fp
        },
        "away": {
            "team_id": match.away_team_id,
            "score": away_score,
            "wickets": away_wickets if scoring_model == "innings" else None,
            "balls": away_legal_balls if scoring_model == "innings" else None,
            "overs": overs_str(away_legal_balls) if scoring_model == "innings" else None,
            "fair_play": away_fp
        },
        "version": len(events),
        "events": events_out
    }


@router.post("/audit/v1/events")
async def append_event(body: dict, db: AsyncSession = Depends(get_db)):
    event_id = body.get("event_id")
    match_id = body.get("match_id")
    ev_type = body.get("type")
    payload = body.get("payload", {})

    if not event_id or not match_id or not ev_type:
        _400("event_id, match_id, type required", ["event_id", "match_id", "type"])

    # Idempotency check
    existing_ev = await db.execute(select(MatchEvent).where(MatchEvent.event_id == event_id))
    existing_ev = existing_ev.scalar_one_or_none()
    if existing_ev:
        if (existing_ev.match_id == match_id and existing_ev.type == ev_type and
                existing_ev.payload == payload):
            return {
                "event_id": event_id, "match_id": match_id, "type": ev_type,
                "sequence": existing_ev.sequence, "match_version": existing_ev.match_version,
                "signature": existing_ev.signature
            }
        _409("DUPLICATE_EVENT_ID", f"event_id {event_id} reused with different body")

    # Get or create match stream
    match = await db.get(Match, match_id)

    if ev_type == "match_init":
        if match:
            _409("MATCH_EXISTS", f"Match {match_id} already exists")
        sport_id = payload.get("sport_id")
        sport = await db.get(Sport, sport_id)
        if not sport:
            raise HTTPException(status_code=404, detail={"error": {
                "code": "SPORT_NOT_FOUND", "message": f"Sport {sport_id} not found", "details": {}
            }})
        match = Match(
            match_id=match_id, sport_id=sport_id,
            home_team_id=payload.get("home_team_id"),
            away_team_id=payload.get("away_team_id"),
            league_id=payload.get("league_id"),
            status="upcoming"
        )
        db.add(match)
    else:
        if not match:
            raise HTTPException(status_code=404, detail={"error": {
                "code": "MATCH_NOT_FOUND", "message": f"Match {match_id} not found", "details": {}
            }})

    sport = await db.get(Sport, match.sport_id)

    # Get current events to determine status
    ev_result = await db.execute(
        select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.sequence)
    )
    current_events = ev_result.scalars().all()

    # Compute current status from log
    proj = _compute_score_from_events(sport, match, current_events)
    current_status = proj["status"]

    # State machine validation
    if ev_type == "match_init":
        pass  # already handled above
    elif ev_type == "match_start":
        if current_status != "upcoming":
            _409("ILLEGAL_TRANSITION", f"Cannot start match in status {current_status}")
    elif ev_type == "match_end":
        if current_status != "in_progress":
            _409("ILLEGAL_TRANSITION", f"Cannot end match in status {current_status}")
        # Check tie allowed
        hs = proj["home"]["score"]
        aws = proj["away"]["score"]
        if hs == aws and not sport.draw_allowed and not proj.get("tiebreak_winner_team_id"):
            _409("TIE_NOT_ALLOWED", "Score is level and draw is not allowed for this sport")
    elif ev_type == "score":
        if current_status != "in_progress":
            _409("MATCH_NOT_IN_PROGRESS", "Match must be in_progress to score")
        team_id = payload.get("team_id")
        if team_id not in (match.home_team_id, match.away_team_id):
            _400(f"team_id {team_id} is not part of this match", ["team_id"])
        event_type = payload.get("event_type")
        if event_type not in sport.scoring_events:
            raise HTTPException(status_code=400, detail={"error": {
                "code": "UNKNOWN_EVENT_TYPE",
                "message": f"Event type {event_type} not defined for sport {sport.sport_id}",
                "details": {}
            }})
        # Check innings/series limits
        side = "home" if team_id == match.home_team_id else "away"
        if sport.scoring_model == "innings":
            periods_cfg = sport.periods
            max_balls = periods_cfg.get("innings_per_team", 1) * periods_cfg.get("overs_per_innings", 20) * periods_cfg.get("balls_per_over", 6)
            max_wickets = periods_cfg.get("innings_per_team", 1) * periods_cfg.get("wickets_per_innings", 10)
            compensated = {ev.payload.get("compensates") for ev in current_events if ev.type == "compensation"}
            team_legal = sum(1 for ev in current_events
                             if ev.type == "score" and ev.event_id not in compensated
                             and ev.payload.get("team_id") == team_id
                             and sport.scoring_events.get(ev.payload.get("event_type"), {}).get("legal_ball", False))
            team_wickets = sum(1 for ev in current_events
                               if ev.type == "score" and ev.event_id not in compensated
                               and ev.payload.get("team_id") == team_id
                               and sport.scoring_events.get(ev.payload.get("event_type"), {}).get("wicket", False))
            if team_legal >= max_balls or team_wickets >= max_wickets:
                _409("INNINGS_COMPLETE", f"Innings complete for team {team_id}")
        elif sport.scoring_model == "round":
            best_of = sport.periods.get("best_of", 3)
            needed = (best_of + 1) // 2
            compensated = {ev.payload.get("compensates") for ev in current_events if ev.type == "compensation"}
            team_rounds = sum(
                sport.scoring_events.get(ev.payload.get("event_type"), {}).get("rounds", 0)
                for ev in current_events
                if ev.type == "score" and ev.event_id not in compensated
                and ev.payload.get("team_id") == team_id
            )
            if team_rounds >= needed:
                _409("SERIES_ALREADY_DECIDED", f"Series already decided for team {team_id}")

    elif ev_type == "discipline":
        if current_status != "in_progress":
            _409("MATCH_NOT_IN_PROGRESS", "Match must be in_progress for discipline events")
        team_id = payload.get("team_id")
        if team_id not in (match.home_team_id, match.away_team_id):
            _400("team_id not in match", ["team_id"])
    elif ev_type == "tiebreak_winner":
        if current_status != "in_progress":
            _409("MATCH_NOT_IN_PROGRESS", "Match must be in_progress")
    elif ev_type == "compensation":
        compensates_id = payload.get("compensates")
        if not compensates_id:
            _400("compensates field required", ["compensates"])
        # Find the target event
        target = next((ev for ev in current_events if ev.event_id == compensates_id), None)
        if not target:
            raise HTTPException(status_code=404, detail={"error": {
                "code": "EVENT_NOT_FOUND",
                "message": f"Event {compensates_id} not found",
                "details": {}
            }})
        if target.match_id != match_id:
            _409("INVALID_COMPENSATION", "Compensated event belongs to different match")
        if target.type not in ("score", "discipline", "tiebreak_winner"):
            _409("INVALID_COMPENSATION", "Can only compensate score/discipline/tiebreak_winner events")
        # Already compensated?
        already_comp = any(
            ev.type == "compensation" and ev.payload.get("compensates") == compensates_id
            for ev in current_events
        )
        if already_comp:
            _409("INVALID_COMPENSATION", f"Event {compensates_id} already compensated")
    else:
        _400(f"Unknown event type: {ev_type}", ["type"])

    # Compute sequence and version
    sequence = len(current_events) + 1
    match_version = len(current_events) + 1

    # Sign
    sig = sign_payload(event_id, payload)

    # Append event
    ev_obj = MatchEvent(
        event_id=event_id, match_id=match_id, type=ev_type,
        payload=payload, sequence=sequence, match_version=match_version,
        signature=sig
    )
    db.add(ev_obj)
    await db.commit()

    return {
        "event_id": event_id, "match_id": match_id, "type": ev_type,
        "sequence": sequence, "match_version": match_version, "signature": sig
    }


@router.get("/audit/v1/score/{match_id}")
async def get_score(match_id: str, db: AsyncSession = Depends(get_db)):
    match = await db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail={"error": {
            "code": "MATCH_NOT_FOUND", "message": f"Match {match_id} not found", "details": {}
        }})

    sport = await db.get(Sport, match.sport_id)

    ev_result = await db.execute(
        select(MatchEvent).where(MatchEvent.match_id == match_id).order_by(MatchEvent.sequence)
    )
    events = ev_result.scalars().all()

    return _compute_score_from_events(sport, match, events)
