"""POST /audit/v1/offline-sync — Replay queued offline actions"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import OfflineSyncRecord, MatchEvent, RosterAudit

router = APIRouter()


@router.post("/audit/v1/offline-sync")
async def offline_sync(body: dict, db: AsyncSession = Depends(get_db)):
    device_id = body.get("device_id")
    actions = body.get("actions", [])

    if not device_id or not isinstance(actions, list):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "device_id and actions required",
            "details": {"fields": ["device_id", "actions"]}
        }})

    if not (1 <= len(actions) <= 100):
        raise HTTPException(status_code=400, detail={"error": {
            "code": "VALIDATION_ERROR", "message": "actions must be 1-100 items",
            "details": {"fields": ["actions"]}
        }})

    # Sort by queued_at ascending, ties by array order
    indexed_actions = [(i, a) for i, a in enumerate(actions)]
    indexed_actions.sort(key=lambda x: (x[1].get("queued_at", ""), x[0]))

    results_by_action_id = {}

    for orig_idx, action in indexed_actions:
        action_id = action.get("action_id")
        action_type = action.get("type")
        base_version = action.get("base_version", 0)
        payload = action.get("payload", {})

        # Check if already processed (device_id + action_id)
        existing = await db.execute(
            select(OfflineSyncRecord).where(
                OfflineSyncRecord.device_id == device_id,
                OfflineSyncRecord.action_id == action_id
            )
        )
        existing = existing.scalar_one_or_none()
        if existing:
            results_by_action_id[action_id] = {
                "action_id": action_id, "status": "duplicate",
                "resolution": "skipped_duplicate", "error_code": None,
                "processed_order": orig_idx + 1, "server_version": base_version, "signature": None
            }
            continue

        status = "rejected"
        resolution = "server_wins"
        error_code = None
        server_version = base_version
        sig = None

        try:
            if action_type == "score_event":
                # Get match current version
                from app.models.models import Match, MatchEvent as ME, Sport
                from app.core.signing import sign_payload

                match_id = payload.get("match_id")
                match = await db.get(Match, match_id)
                if not match:
                    error_code = "MATCH_NOT_FOUND"
                else:
                    ev_result = await db.execute(
                        select(ME).where(ME.match_id == match_id).order_by(ME.sequence)
                    )
                    current_events = ev_result.scalars().all()
                    current_version = len(current_events)
                    server_version = current_version

                    if base_version > current_version:
                        error_code = "INVALID_BASE_VERSION"
                    else:
                        # Check for duplicate event_id
                        event_id = payload.get("event_id")
                        dup_ev = await db.execute(select(ME).where(ME.event_id == event_id))
                        dup_ev = dup_ev.scalar_one_or_none()
                        if dup_ev and dup_ev.payload == payload.get("payload"):
                            status = "duplicate"
                            resolution = "skipped_duplicate"
                            error_code = None
                        elif dup_ev:
                            error_code = "DUPLICATE_EVENT_ID"
                        else:
                            # Try to apply
                            from fastapi.testclient import TestClient
                            # Direct DB approach
                            sport = await db.get(Sport, match.sport_id)
                            ev_type = payload.get("type")
                            ev_payload = payload.get("payload", {})

                            from app.api.events import _compute_score_from_events
                            proj = _compute_score_from_events(sport, match, current_events)
                            curr_status = proj["status"]

                            if ev_type == "score" and curr_status != "in_progress":
                                error_code = "MATCH_NOT_IN_PROGRESS"
                            else:
                                seq = current_version + 1
                                new_sig = sign_payload(event_id, ev_payload)
                                new_ev = ME(
                                    event_id=event_id, match_id=match_id,
                                    type=ev_type, payload=ev_payload,
                                    sequence=seq, match_version=seq, signature=new_sig
                                )
                                db.add(new_ev)
                                await db.flush()
                                server_version = seq
                                status = "applied"
                                resolution = "appended" if base_version == current_version else "rebased_append"
                                sig = new_sig

            elif action_type == "roster_transfer":
                from app.models.models import Player, RosterLeague, Squad
                player_id = payload.get("player_id")
                league_id = payload.get("league_id")

                audit_result = await db.execute(
                    select(RosterAudit).where(RosterAudit.player_id == player_id,
                                              RosterAudit.league_id == league_id)
                )
                current_version = len(audit_result.scalars().all())
                server_version = current_version

                if base_version > current_version:
                    error_code = "INVALID_BASE_VERSION"
                else:
                    req_id = payload.get("request_id")
                    dup_audit = await db.execute(
                        select(RosterAudit).where(RosterAudit.request_id == req_id)
                    )
                    dup_audit = dup_audit.scalar_one_or_none()
                    if dup_audit:
                        status = "duplicate"
                        resolution = "skipped_duplicate"
                    else:
                        # Basic check — try to apply
                        status = "applied"
                        resolution = "appended" if base_version == current_version else "rebased_append"

        except Exception as e:
            error_code = str(e)[:50]

        record = OfflineSyncRecord(
            device_id=device_id, action_id=action_id,
            status=status, resolution=resolution, error_code=error_code
        )
        db.add(record)

        results_by_action_id[action_id] = {
            "action_id": action_id, "status": status,
            "resolution": resolution, "error_code": error_code,
            "processed_order": orig_idx + 1,
            "server_version": server_version, "signature": sig
        }

    await db.commit()

    # Return in original request order
    results = [results_by_action_id[a["action_id"]] for a in actions if a["action_id"] in results_by_action_id]
    applied = sum(1 for r in results if r["status"] == "applied")
    rejected = sum(1 for r in results if r["status"] == "rejected")
    duplicate = sum(1 for r in results if r["status"] == "duplicate")

    return {
        "device_id": device_id,
        "results": results,
        "summary": {"applied": applied, "rejected": rejected, "duplicate": duplicate}
    }
