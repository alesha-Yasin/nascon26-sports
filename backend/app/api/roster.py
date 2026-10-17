"""
POST /audit/v1/roster/setup
POST /audit/v1/roster/transfer
GET  /audit/v1/roster/history/{player_id}
"""
import uuid
from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import RosterLeague, Squad, Player, RosterAudit, Sport

router = APIRouter()


def _404(code, msg):
    raise HTTPException(status_code=404, detail={"error": {"code": code, "message": msg, "details": {}}})


def _409(code, msg, details=None):
    raise HTTPException(status_code=409, detail={"error": {"code": code, "message": msg, "details": details or {}}})


def _400(msg, fields=None):
    raise HTTPException(status_code=400, detail={"error": {
        "code": "VALIDATION_ERROR", "message": msg, "details": {"fields": fields or []}
    }})


@router.post("/audit/v1/roster/setup", status_code=201)
async def roster_setup(body: dict, db: AsyncSession = Depends(get_db)):
    league_data = body.get("league", {})
    squads_data = body.get("squads", [])
    players_data = body.get("players", [])
    matches_in_progress = body.get("matches_in_progress", [])

    league_id = league_data.get("league_id")
    if not league_id:
        _400("league.league_id required", ["league_id"])

    tenant_id = league_data.get("tenant_id", "tenant-alpha")
    sport_id = league_data.get("sport_id", "football")
    sport = await db.get(Sport, sport_id)
    roster_defaults = sport.roster_config if sport else {}

    max_squad_size = league_data.get("max_squad_size", roster_defaults.get("max_squad_size", 25))
    required_positions = league_data.get("required_positions", roster_defaults.get("required_positions", {}))

    tw = league_data.get("transfer_window", {})
    tw_open = tw.get("open")
    tw_close = tw.get("close")

    # Delete existing roster league data
    existing_rl = await db.get(RosterLeague, league_id)
    if existing_rl:
        await db.delete(existing_rl)
        # Delete squads and players for this league
        sq_result = await db.execute(select(Squad).where(Squad.league_id == league_id))
        for sq in sq_result.scalars().all():
            await db.delete(sq)
        pl_result = await db.execute(select(Player).where(Player.league_id == league_id))
        for pl in pl_result.scalars().all():
            await db.delete(pl)
        au_result = await db.execute(select(RosterAudit).where(RosterAudit.league_id == league_id))
        for au in au_result.scalars().all():
            await db.delete(au)

    rl = RosterLeague(
        league_id=league_id, tenant_id=tenant_id, sport_id=sport_id,
        transfer_window_open=tw_open, transfer_window_close=tw_close,
        max_squad_size=max_squad_size, required_positions=required_positions,
        matches_in_progress=[{"match_id": m["match_id"],
                               "home_squad_id": m["home_squad_id"],
                               "away_squad_id": m["away_squad_id"]}
                              for m in matches_in_progress]
    )
    db.add(rl)

    squad_counts = {}
    for sq_data in squads_data:
        sq = Squad(
            squad_id=sq_data["squad_id"], league_id=league_id,
            club_id=sq_data.get("club_id", ""), tenant_id=sq_data.get("tenant_id", tenant_id),
            name=sq_data.get("name", "")
        )
        db.add(sq)
        squad_counts[sq_data["squad_id"]] = 0

    for pl_data in players_data:
        pl = Player(
            player_id=pl_data["player_id"], name=pl_data.get("name", ""),
            position=pl_data.get("position", ""), league_id=league_id,
            current_squad_id=pl_data.get("squad_id"),
            role=pl_data.get("role", "substitute"),
            registration_type="transfer", is_released=False, on_loan=False
        )
        db.add(pl)
        if pl_data.get("squad_id") in squad_counts:
            squad_counts[pl_data["squad_id"]] = squad_counts.get(pl_data["squad_id"], 0) + 1

    await db.commit()
    return {"league_id": league_id, "status": "configured", "squad_counts": squad_counts}


@router.post("/audit/v1/roster/transfer")
async def roster_transfer(body: dict, db: AsyncSession = Depends(get_db)):
    request_id = body.get("request_id")
    league_id = body.get("league_id")
    player_id = body.get("player_id")
    transfer_type = body.get("type")
    from_squad_id = body.get("from_squad_id")
    to_squad_id = body.get("to_squad_id")
    effective_date_str = body.get("effective_date")
    loan_end_date_str = body.get("loan_end_date")
    reason = body.get("reason")
    requested_by = body.get("requested_by", "system")

    # 1. Schema validation
    if not all([request_id, league_id, player_id, transfer_type, from_squad_id, effective_date_str]):
        _400("Required fields missing", ["request_id", "league_id", "player_id", "type", "from_squad_id", "effective_date"])

    if transfer_type not in ("transfer", "loan", "release"):
        _400("type must be transfer, loan, or release", ["type"])
    if transfer_type != "release" and not to_squad_id:
        _400("to_squad_id required for transfer/loan", ["to_squad_id"])
    if transfer_type == "loan":
        if not loan_end_date_str:
            _400("loan_end_date required for loan", ["loan_end_date"])

    try:
        effective_date = date.fromisoformat(effective_date_str)
        loan_end_date = date.fromisoformat(loan_end_date_str) if loan_end_date_str else None
    except ValueError:
        _400("Invalid date format", ["effective_date", "loan_end_date"])

    if transfer_type == "loan" and loan_end_date and loan_end_date <= effective_date:
        _400("loan_end_date must be > effective_date", ["loan_end_date"])

    # Idempotency
    existing_audit = await db.execute(select(RosterAudit).where(RosterAudit.request_id == request_id))
    existing_audit = existing_audit.scalar_one_or_none()
    if existing_audit:
        if existing_audit.stored_response:
            return existing_audit.stored_response
        return {"request_id": request_id, "status": "accepted"}

    # 2. Existence checks
    rl = await db.get(RosterLeague, league_id)
    if not rl:
        _404("LEAGUE_NOT_FOUND", f"League {league_id} not found")

    player = await db.execute(
        select(Player).where(Player.player_id == player_id, Player.league_id == league_id)
    )
    player = player.scalar_one_or_none()
    if not player:
        _404("PLAYER_NOT_FOUND", f"Player {player_id} not found")

    from_squad = await db.get(Squad, from_squad_id)
    if not from_squad:
        _404("SQUAD_NOT_FOUND", f"Squad {from_squad_id} not found")

    to_squad = None
    if to_squad_id:
        to_squad = await db.get(Squad, to_squad_id)
        if not to_squad:
            _404("SQUAD_NOT_FOUND", f"Squad {to_squad_id} not found")

    # 3. Cross-tenant check
    if to_squad and to_squad.tenant_id != rl.tenant_id:
        _409("CROSS_TENANT_TRANSFER", "Cannot transfer across tenants")

    # 4. Player in from_squad
    if player.current_squad_id != from_squad_id:
        _409("NOT_IN_SQUAD", f"Player {player_id} is not in squad {from_squad_id}")

    # 5. Transfer window (release is always allowed)
    if transfer_type in ("transfer", "loan"):
        if rl.transfer_window_open and rl.transfer_window_close:
            tw_open = date.fromisoformat(rl.transfer_window_open)
            tw_close = date.fromisoformat(rl.transfer_window_close)
            if not (tw_open <= effective_date <= tw_close):
                _409("TRANSFER_WINDOW_CLOSED", "Transfer date is outside the transfer window")

    # 6. Player on loan
    if player.on_loan:
        _409("PLAYER_ON_LOAN", f"Player {player_id} is currently on loan")

    # 7. Squad full
    if transfer_type in ("transfer", "loan") and to_squad:
        to_players_result = await db.execute(
            select(Player).where(Player.current_squad_id == to_squad_id, Player.league_id == league_id, Player.is_released == False)
        )
        to_count = len(to_players_result.scalars().all())
        if to_count + 1 > rl.max_squad_size:
            _409("SQUAD_FULL", f"Squad {to_squad_id} is full ({rl.max_squad_size})")

    # 8. Min position violation
    if required_pos := rl.required_positions:
        player_pos = player.position
        if player_pos in required_pos:
            from_players_result = await db.execute(
                select(Player).where(Player.current_squad_id == from_squad_id,
                                     Player.league_id == league_id, Player.is_released == False)
            )
            from_players = from_players_result.scalars().all()
            pos_count = sum(1 for p in from_players
                            if p.position == player_pos and p.player_id != player_id)
            min_req = required_pos.get(player_pos, 0)
            if pos_count < min_req:
                _409("MIN_POSITION_VIOLATION",
                     f"Cannot remove player: would violate min {player_pos} requirement")

    # Check if in-progress match
    mip = rl.matches_in_progress or []
    in_progress_match = None
    for m in mip:
        if from_squad_id in (m.get("home_squad_id"), m.get("away_squad_id")):
            in_progress_match = m["match_id"]
            break

    state = "deferred_until_match_end" if in_progress_match else "active"
    blocking_match_id = in_progress_match

    # Apply effects
    now = datetime.now(timezone.utc)
    audit_id = f"au-{uuid.uuid4().hex[:8]}"
    action = transfer_type

    if state == "active":
        if transfer_type == "transfer":
            player.current_squad_id = to_squad_id
            player.role = "substitute"
            player.registration_type = "transfer"
            player.parent_squad_id = None
            player.on_loan = False
        elif transfer_type == "loan":
            player.parent_squad_id = from_squad_id
            player.current_squad_id = to_squad_id
            player.registration_type = "loan"
            player.loan_end_date = loan_end_date_str
            player.on_loan = True
        elif transfer_type == "release":
            player.is_released = True
            player.current_squad_id = None

    registration = None
    if transfer_type != "release":
        registration = {
            "player_id": player_id,
            "league_id": league_id,
            "squad_id": player.current_squad_id,
            "parent_squad_id": player.parent_squad_id,
            "registration_type": player.registration_type,
            "start_date": effective_date_str,
            "loan_end_date": loan_end_date_str,
            "role": player.role
        }

    audit_entry = {
        "audit_id": audit_id,
        "action": action,
        "player_id": player_id,
        "league_id": league_id,
        "from_squad_id": from_squad_id,
        "to_squad_id": to_squad_id,
        "effective_date": effective_date_str,
        "state": state,
        "who": requested_by,
        "when": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": reason
    }

    response = {
        "request_id": request_id,
        "status": "accepted",
        "state": state,
        "blocking_match_id": blocking_match_id,
        "registration": registration,
        "audit_entry": audit_entry
    }

    audit = RosterAudit(
        audit_id=audit_id, request_id=request_id, action=action,
        player_id=player_id, league_id=league_id,
        from_squad_id=from_squad_id, to_squad_id=to_squad_id,
        effective_date=effective_date_str, state=state,
        blocking_match_id=blocking_match_id,
        who=requested_by, when_ts=now, why=reason,
        stored_response=response
    )
    db.add(audit)
    await db.commit()

    return response


@router.get("/audit/v1/roster/history/{player_id}")
async def roster_history(player_id: str, as_of: str = None, db: AsyncSession = Depends(get_db)):
    # Find player across all leagues
    player_result = await db.execute(select(Player).where(Player.player_id == player_id))
    player = player_result.scalar_one_or_none()
    if not player:
        _404("PLAYER_NOT_FOUND", f"Player {player_id} not found")

    today = date.today().isoformat()
    as_of_date = as_of or today

    # Get all audit entries
    audit_result = await db.execute(
        select(RosterAudit).where(RosterAudit.player_id == player_id).order_by(RosterAudit.when_ts)
    )
    audits = audit_result.scalars().all()

    # Check for auto loan_return
    loan_return_entries = []
    for audit in audits:
        if audit.action == "loan":
            loan_end = audit.stored_response.get("registration", {}).get("loan_end_date") if audit.stored_response else None
            if loan_end and as_of_date > loan_end:
                # Check if already have a loan_return
                already_returned = any(
                    a.action == "loan_return" and a.league_id == audit.league_id
                    for a in audits
                )
                if not already_returned:
                    lr_id = f"au-lr-{audit.audit_id}"
                    lr_entry = {
                        "audit_id": lr_id,
                        "action": "loan_return",
                        "player_id": player_id,
                        "league_id": audit.league_id,
                        "from_squad_id": audit.to_squad_id,
                        "to_squad_id": audit.from_squad_id,
                        "effective_date": loan_end,
                        "state": "active",
                        "who": "system",
                        "when": f"{loan_end}T00:00:00Z",
                        "why": "Automatic loan return"
                    }
                    loan_return_entries.append(lr_entry)

    history = []
    for a in audits:
        entry = {
            "audit_id": a.audit_id,
            "action": a.action,
            "player_id": player_id,
            "league_id": a.league_id,
            "from_squad_id": a.from_squad_id,
            "to_squad_id": a.to_squad_id,
            "effective_date": a.effective_date,
            "state": a.state,
            "who": a.who,
            "when": a.when_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "why": a.why
        }
        history.append(entry)

    history.extend(loan_return_entries)
    history.sort(key=lambda x: x["when"])

    # Determine current squad as of date
    current_squad_id = player.current_squad_id
    for lr in loan_return_entries:
        current_squad_id = lr.get("to_squad_id")

    return {
        "player_id": player_id,
        "as_of": as_of_date,
        "league_id": player.league_id,
        "current_squad_id": current_squad_id,
        "parent_squad_id": player.parent_squad_id,
        "history": history
    }
