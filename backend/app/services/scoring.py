"""
Score projection engine.
Rebuilds match state from append-only event log on every read.
"""
from typing import Optional


def project_score(sport_cfg: dict, events: list) -> dict:
    """
    Compute match state from the event log.
    Returns a score projection dict.
    """
    scoring_model = sport_cfg.get("scoring_model", "event")
    periods_cfg = sport_cfg.get("periods", {})
    scoring_events_cfg = sport_cfg.get("scoring_events", {})
    draw_allowed = sport_cfg.get("draw_allowed", True)

    status = "upcoming"
    home_score = 0
    away_score = 0
    home_fair_play = 0
    away_fair_play = 0
    tiebreak_winner = None

    # Innings tracking
    home_legal_balls = 0
    away_legal_balls = 0
    home_wickets = 0
    away_wickets = 0

    # Round tracking
    home_rounds = 0
    away_rounds = 0

    compensated_ids = set()

    # First pass: find compensated events
    for ev in events:
        if ev["type"] == "compensation":
            compensated_ids.add(ev["payload"]["compensates"])

    # Second pass: apply active events
    for ev in events:
        eid = ev["event_id"]
        ev_type = ev["type"]
        payload = ev["payload"]

        # Skip compensated events and compensation events themselves
        if eid in compensated_ids:
            continue
        if ev_type == "compensation":
            continue

        if ev_type == "match_init":
            status = "upcoming"
        elif ev_type == "match_start":
            status = "in_progress"
        elif ev_type == "match_end":
            status = "completed"
        elif ev_type == "score":
            team_id = payload.get("team_id")
            event_type = payload.get("event_type")
            evt_cfg = scoring_events_cfg.get(event_type, {})

            if scoring_model == "event":
                pts = evt_cfg.get("points", 0)
                if team_id == payload.get("_home"):
                    home_score += pts
                else:
                    away_score += pts
            elif scoring_model == "innings":
                runs = evt_cfg.get("runs", 0)
                legal = evt_cfg.get("legal_ball", False)
                wicket = evt_cfg.get("wicket", False)
                if team_id == payload.get("_home"):
                    home_score += runs
                    if legal:
                        home_legal_balls += 1
                    if wicket:
                        home_wickets += 1
                else:
                    away_score += runs
                    if legal:
                        away_legal_balls += 1
                    if wicket:
                        away_wickets += 1
            elif scoring_model == "round":
                rds = evt_cfg.get("rounds", 0)
                if team_id == payload.get("_home"):
                    home_rounds += rds
                else:
                    away_rounds += rds

        elif ev_type == "discipline":
            team_id = payload.get("team_id")
            pts = payload.get("points", 0)
            if team_id == payload.get("_home"):
                home_fair_play += pts
            else:
                away_fair_play += pts
        elif ev_type == "tiebreak_winner":
            tiebreak_winner = payload.get("team_id")

    # Determine outcome
    if scoring_model == "round":
        hs = home_rounds
        as_ = away_rounds
    else:
        hs = home_score
        as_ = away_score

    outcome = "pending"
    winner_team_id = None
    if status == "completed":
        if hs > as_:
            outcome = "home_win"
            winner_team_id = None  # filled by caller with actual team ids
        elif as_ > hs:
            outcome = "away_win"
        elif draw_allowed:
            outcome = "draw"
        elif tiebreak_winner:
            if tiebreak_winner == "_home_placeholder":
                outcome = "home_win"
            else:
                outcome = "away_win"
            winner_team_id = tiebreak_winner
        else:
            outcome = "undecided"

    # Innings overs string
    def overs_str(balls, bpo):
        if balls is None:
            return None
        return f"{balls // bpo}.{balls % bpo}"

    bpo = periods_cfg.get("balls_per_over", 6) if scoring_model == "innings" else None

    return {
        "status": status,
        "outcome": outcome,
        "home_score": hs,
        "away_score": as_,
        "home_fair_play": home_fair_play,
        "away_fair_play": away_fair_play,
        "home_legal_balls": home_legal_balls if scoring_model == "innings" else None,
        "away_legal_balls": away_legal_balls if scoring_model == "innings" else None,
        "home_wickets": home_wickets if scoring_model == "innings" else None,
        "away_wickets": away_wickets if scoring_model == "innings" else None,
        "home_overs": overs_str(home_legal_balls, bpo) if scoring_model == "innings" else None,
        "away_overs": overs_str(away_legal_balls, bpo) if scoring_model == "innings" else None,
        "tiebreak_winner": tiebreak_winner,
        "compensated_ids": list(compensated_ids)
    }


def check_innings_complete(sport_cfg: dict, events: list, team_side: str) -> bool:
    """Check if innings is complete for a team (too many legal balls or wickets)."""
    periods_cfg = sport_cfg.get("periods", {})
    scoring_events_cfg = sport_cfg.get("scoring_events", {})
    overs = periods_cfg.get("overs_per_innings", 20)
    bpo = periods_cfg.get("balls_per_over", 6)
    max_wickets = periods_cfg.get("wickets_per_innings", 10)
    innings_count = periods_cfg.get("innings_per_team", 1)
    max_balls = innings_count * overs * bpo
    max_wkts = innings_count * max_wickets

    compensated_ids = {ev["payload"]["compensates"] for ev in events if ev["type"] == "compensation"}

    legal_balls = 0
    wickets = 0
    for ev in events:
        if ev["type"] != "score" or ev["event_id"] in compensated_ids:
            continue
        if ev["payload"].get("_side") != team_side:
            continue
        etype = ev["payload"].get("event_type")
        cfg = scoring_events_cfg.get(etype, {})
        if cfg.get("legal_ball", False):
            legal_balls += 1
        if cfg.get("wicket", False):
            wickets += 1

    return legal_balls >= max_balls or wickets >= max_wkts


def check_series_decided(sport_cfg: dict, events: list, team_side: str) -> bool:
    """Check if series is decided for a team (round model)."""
    periods_cfg = sport_cfg.get("periods", {})
    scoring_events_cfg = sport_cfg.get("scoring_events", {})
    best_of = periods_cfg.get("best_of", 3)
    needed = (best_of + 1) // 2

    compensated_ids = {ev["payload"]["compensates"] for ev in events if ev["type"] == "compensation"}

    rounds_won = 0
    for ev in events:
        if ev["type"] != "score" or ev["event_id"] in compensated_ids:
            continue
        if ev["payload"].get("_side") != team_side:
            continue
        etype = ev["payload"].get("event_type")
        cfg = scoring_events_cfg.get(etype, {})
        rounds_won += cfg.get("rounds", 0)

    return rounds_won >= needed
