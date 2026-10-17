"""
Standings computation engine.
Recomputed from scratch from match events on every call.
"""
import hashlib
from typing import Optional


def lots_key(seed: int, league_id: str, team_id: str) -> str:
    return hashlib.sha256(f"{seed}|{league_id}|{team_id}".encode("utf-8")).hexdigest()


def compute_standings(league_data: dict, match_scores: dict) -> dict:
    """
    league_data: {
        league_id, sport_id, teams, fixtures, points_win, points_draw, points_loss,
        tie_break_order, qualification_spots, lots_seed
    }
    match_scores: {match_id: score_projection_dict}  -- only completed, non-undecided
    """
    league_id = league_data["league_id"]
    sport_id = league_data["sport_id"]
    teams = league_data["teams"]
    fixtures = league_data["fixtures"]
    pw = league_data.get("points_win", 3)
    pd_ = league_data.get("points_draw", 1)
    pl = league_data.get("points_loss", 0)
    tbo = league_data.get("tie_break_order",
        ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"])
    spots = league_data.get("qualification_spots", 1)
    seed = league_data.get("lots_seed", 42)
    sport_cfg = league_data.get("sport_config", {})
    scoring_model = sport_cfg.get("scoring_model", "event")
    innings_cfg = sport_cfg.get("periods", {})

    # Init stats
    stats = {t: {"played": 0, "won": 0, "drawn": 0, "lost": 0,
                 "scored": 0, "conceded": 0, "points": 0, "fair_play": 0,
                 "legal_balls_scored": 0, "legal_balls_conceded": 0,
                 "wickets_used": 0, "wickets_conceded": 0}
             for t in teams}

    # H2H matrix
    h2h = {t: {o: {"played": 0, "points": 0, "scored": 0, "conceded": 0,
                   "legal_balls": 0, "opp_legal_balls": 0}
               for o in teams if o != t}
           for t in teams}

    # Count remaining fixtures
    remaining = {t: 0 for t in teams}
    for fx in fixtures:
        score = match_scores.get(fx["match_id"])
        if score is None or score.get("status") != "completed" or score.get("outcome") == "undecided":
            remaining[fx["home"]] = remaining.get(fx["home"], 0) + 1
            remaining[fx["away"]] = remaining.get(fx["away"], 0) + 1

    # Process completed matches
    for fx in fixtures:
        score = match_scores.get(fx["match_id"])
        if not score or score.get("status") != "completed" or score.get("outcome") == "undecided":
            continue

        home_id = fx["home"]
        away_id = fx["away"]
        outcome = score["outcome"]
        home_score = score["home"]["score"]
        away_score = score["away"]["score"]
        home_fp = score["home"].get("fair_play", 0)
        away_fp = score["away"].get("fair_play", 0)

        # Innings model extras
        home_balls = score["home"].get("balls") or 0
        away_balls = score["away"].get("balls") or 0
        home_wickets = score["home"].get("wickets") or 0
        away_wickets = score["away"].get("wickets") or 0

        for t in [home_id, away_id]:
            if t not in stats:
                continue
        
        stats[home_id]["played"] += 1
        stats[away_id]["played"] += 1
        stats[home_id]["scored"] += home_score
        stats[home_id]["conceded"] += away_score
        stats[away_id]["scored"] += away_score
        stats[away_id]["conceded"] += home_score
        stats[home_id]["fair_play"] += home_fp
        stats[away_id]["fair_play"] += away_fp
        stats[home_id]["legal_balls_scored"] += home_balls
        stats[away_id]["legal_balls_scored"] += away_balls
        stats[home_id]["legal_balls_conceded"] += away_balls
        stats[away_id]["legal_balls_conceded"] += home_balls
        stats[home_id]["wickets_used"] += home_wickets
        stats[away_id]["wickets_used"] += away_wickets

        if outcome == "home_win":
            stats[home_id]["won"] += 1
            stats[away_id]["lost"] += 1
            stats[home_id]["points"] += pw
            stats[away_id]["points"] += pl
            h2h[home_id][away_id]["points"] += pw
            h2h[away_id][home_id]["points"] += pl
        elif outcome == "away_win":
            stats[away_id]["won"] += 1
            stats[home_id]["lost"] += 1
            stats[away_id]["points"] += pw
            stats[home_id]["points"] += pl
            h2h[away_id][home_id]["points"] += pw
            h2h[home_id][away_id]["points"] += pl
        elif outcome == "draw":
            stats[home_id]["drawn"] += 1
            stats[away_id]["drawn"] += 1
            stats[home_id]["points"] += pd_
            stats[away_id]["points"] += pd_
            h2h[home_id][away_id]["points"] += pd_
            h2h[away_id][home_id]["points"] += pd_

        # H2H details
        for a, b_ in [(home_id, away_id), (away_id, home_id)]:
            if a in h2h and b_ in h2h[a]:
                h2h[a][b_]["played"] += 1
                if a == home_id:
                    h2h[a][b_]["scored"] += home_score
                    h2h[a][b_]["conceded"] += away_score
                    h2h[a][b_]["legal_balls"] += home_balls
                    h2h[a][b_]["opp_legal_balls"] += away_balls
                else:
                    h2h[a][b_]["scored"] += away_score
                    h2h[a][b_]["conceded"] += home_score
                    h2h[a][b_]["legal_balls"] += away_balls
                    h2h[a][b_]["opp_legal_balls"] += home_balls

    def _diff(team_id, subset=None, all_matches=True):
        """Compute differential (overall or h2h subset)."""
        if scoring_model == "innings":
            bpo = innings_cfg.get("balls_per_over", 6)
            full_overs = innings_cfg.get("overs_per_innings", 20)
            max_balls = innings_cfg.get("wickets_per_innings", 10)

            def nrr(runs_scored, balls_faced, runs_conceded, balls_bowled,
                    wickets_used, wickets_conceded_):
                if balls_bowled == 0 and balls_faced == 0:
                    return 0.0
                overs_faced = balls_faced / bpo
                overs_bowled = balls_bowled / bpo
                # Full innings if all wickets down
                if wickets_used >= max_balls:
                    overs_faced = full_overs
                if wickets_conceded_ >= max_balls:
                    overs_bowled = full_overs
                if overs_faced == 0 or overs_bowled == 0:
                    return 0.0
                return round(runs_scored / overs_faced - runs_conceded / overs_bowled, 3)

            if all_matches:
                s = stats[team_id]
                return nrr(s["scored"], s["legal_balls_scored"],
                           s["conceded"], s["legal_balls_conceded"],
                           s["wickets_used"], s.get("wickets_conceded", 0))
            else:
                # H2H subset
                scored = sum(h2h[team_id][o]["scored"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                conceded = sum(h2h[team_id][o]["conceded"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                balls_faced = sum(h2h[team_id][o]["legal_balls"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                balls_bowled = sum(h2h[team_id][o]["opp_legal_balls"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                return nrr(scored, balls_faced, conceded, balls_bowled, 0, 0)
        else:
            if all_matches:
                return stats[team_id]["scored"] - stats[team_id]["conceded"]
            else:
                scored = sum(h2h[team_id][o]["scored"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                conceded = sum(h2h[team_id][o]["conceded"] for o in subset if o != team_id and o in h2h.get(team_id, {}))
                return scored - conceded

    def h2h_points_in_group(team_id, group):
        return sum(h2h[team_id].get(o, {}).get("points", 0) for o in group if o != team_id)

    def resolve(group: list) -> list:
        """Recursively resolve a tied group. Returns ordered list of teams."""
        if len(group) == 1:
            return group
        
        criteria = list(tbo)
        if "draw_lots" not in criteria:
            criteria.append("draw_lots")
        else:
            criteria = [c for c in criteria if c != "draw_lots"] + ["draw_lots"]

        for criterion in criteria:
            values = {}
            for t in group:
                if criterion == "h2h_points":
                    values[t] = h2h_points_in_group(t, group)
                elif criterion == "h2h_diff":
                    values[t] = _diff(t, subset=group, all_matches=False)
                elif criterion == "overall_diff":
                    values[t] = _diff(t, all_matches=True)
                elif criterion == "scored":
                    values[t] = stats[t]["scored"]
                elif criterion == "fair_play":
                    values[t] = stats[t]["fair_play"]
                elif criterion == "draw_lots":
                    values[t] = lots_key(seed, league_id, t)

            if criterion == "draw_lots":
                # Ascending by hash value (first = best)
                sorted_group = sorted(group, key=lambda t: values[t])
                return sorted_group

            # Check if all equal
            unique_vals = set(values.values())
            if len(unique_vals) == 1:
                continue

            # Split into sub-groups by value (best first)
            if criterion in ["draw_lots"]:
                sorted_vals = sorted(unique_vals)
            else:
                sorted_vals = sorted(unique_vals, reverse=True)

            result = []
            for val in sorted_vals:
                subgroup = [t for t in group if values[t] == val]
                if len(subgroup) == 1:
                    result.extend(subgroup)
                else:
                    result.extend(resolve(subgroup))
            return result

        return group

    # Sort by points desc
    sorted_by_points = sorted(teams, key=lambda t: -stats[t]["points"])

    # Group by equal points
    groups = []
    i = 0
    while i < len(sorted_by_points):
        j = i
        while j < len(sorted_by_points) and stats[sorted_by_points[j]]["points"] == stats[sorted_by_points[i]]["points"]:
            j += 1
        groups.append(sorted_by_points[i:j])
        i = j

    # Resolve each group
    final_order = []
    for g in groups:
        final_order.extend(resolve(g))

    # Build resolved_by
    resolved_by = {t: None for t in teams}
    for idx, t in enumerate(final_order[:-1]):
        next_t = final_order[idx + 1]
        if stats[t]["points"] == stats[next_t]["points"]:
            # Find criterion that separates them
            criteria = list(tbo)
            if "draw_lots" not in criteria:
                criteria.append("draw_lots")
            else:
                criteria = [c for c in criteria if c != "draw_lots"] + ["draw_lots"]

            group_for_tiebreak = [t2 for t2 in teams if stats[t2]["points"] == stats[t]["points"]]
            for criterion in criteria:
                v1 = v2 = None
                if criterion == "h2h_points":
                    v1 = h2h_points_in_group(t, group_for_tiebreak)
                    v2 = h2h_points_in_group(next_t, group_for_tiebreak)
                elif criterion == "h2h_diff":
                    v1 = _diff(t, subset=group_for_tiebreak, all_matches=False)
                    v2 = _diff(next_t, subset=group_for_tiebreak, all_matches=False)
                elif criterion == "overall_diff":
                    v1 = _diff(t, all_matches=True)
                    v2 = _diff(next_t, all_matches=True)
                elif criterion == "scored":
                    v1 = stats[t]["scored"]; v2 = stats[next_t]["scored"]
                elif criterion == "fair_play":
                    v1 = stats[t]["fair_play"]; v2 = stats[next_t]["fair_play"]
                elif criterion == "draw_lots":
                    v1 = lots_key(seed, league_id, t)
                    v2 = lots_key(seed, league_id, next_t)
                    resolved_by[t] = "draw_lots"
                    break
                if v1 is not None and v1 != v2:
                    resolved_by[t] = criterion
                    break

    # Qualification status
    # clinched: < spots other teams have max_points >= points(T)
    # eliminated: >= spots other teams have points > max(T)
    def qual_status(t):
        rem = remaining.get(t, 0)
        my_pts = stats[t]["points"]
        my_max = my_pts + pw * rem
        others = [o for o in teams if o != t]
        clinch_count = sum(1 for o in others if stats[o]["points"] + pw * remaining.get(o, 0) >= my_pts)
        elim_count = sum(1 for o in others if stats[o]["points"] > my_max)
        if clinch_count < spots:
            return "clinched"
        if elim_count >= spots:
            return "eliminated"
        return "still_possible"

    # Build table
    table = []
    for rank, t in enumerate(final_order, 1):
        s = stats[t]
        diff = _diff(t, all_matches=True)
        table.append({
            "rank": rank,
            "team_id": t,
            "played": s["played"],
            "won": s["won"],
            "drawn": s["drawn"],
            "lost": s["lost"],
            "scored": s["scored"],
            "conceded": s["conceded"],
            "diff": diff,
            "points": s["points"],
            "fair_play": s["fair_play"],
            "status": qual_status(t),
            "resolved_by": resolved_by.get(t)
        })

    # H2H output (all ordered pairs)
    h2h_out = {}
    for t in teams:
        h2h_out[t] = {}
        for o in teams:
            if o == t:
                continue
            h2h_out[t][o] = {
                "played": h2h[t].get(o, {}).get("played", 0),
                "points": h2h[t].get(o, {}).get("points", 0),
                "scored": h2h[t].get(o, {}).get("scored", 0),
                "conceded": h2h[t].get(o, {}).get("conceded", 0)
            }

    return {
        "league_id": league_id,
        "sport_id": sport_id,
        "qualification_spots": spots,
        "table": table,
        "h2h": h2h_out
    }
