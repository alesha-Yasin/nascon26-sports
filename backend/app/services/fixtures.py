"""
Fixture scheduling algorithms.
Round-robin (circle method), Swiss system, Single and Double elimination.
All custom implementations — no third-party libraries.
"""
import math
from typing import Optional


# ─── ROUND ROBIN ──────────────────────────────────────────────────────────────

def _circle_method_rounds(teams: list) -> list:
    """
    Circle method for even number of teams.
    Returns list of rounds, each round is list of (home, away) tuples.
    """
    n = len(teams)
    fixed = teams[0]
    rotating = list(teams[1:])
    rounds = []
    for r in range(n - 1):
        pairs = []
        if r % 2 == 0:
            pairs.append((fixed, rotating[-1]))
        else:
            pairs.append((rotating[-1], fixed))
        for i in range(n // 2 - 1):
            home_idx = i
            away_idx = n - 2 - i
            if r % 2 == 0:
                pairs.append((rotating[home_idx], rotating[away_idx]))
            else:
                pairs.append((rotating[away_idx], rotating[home_idx]))
        rounds.append(pairs)
        rotating = [rotating[-1]] + rotating[:-1]
    return rounds


def generate_round_robin(teams: list, legs: int = 1, withdrawals: list = None, withdrawal_policy: str = "forfeit_remaining") -> dict:
    if withdrawals is None:
        withdrawals = []

    n = len(teams)
    odd = n % 2 == 1

    working_teams = list(teams)
    if odd:
        working_teams.append("__BYE__")

    n_working = len(working_teams)
    rounds_per_leg = n_working - 1
    total_rounds = rounds_per_leg * legs

    raw_rounds = _circle_method_rounds(working_teams)

    withdrawal_map = {w["team_id"]: w["after_round"] for w in withdrawals}
    withdrawn_teams = set(withdrawal_map.keys())

    result_rounds = []
    global_match_counter = {}

    for leg in range(1, legs + 1):
        for round_in_leg, pairs in enumerate(raw_rounds, start=1):
            global_round = (leg - 1) * rounds_per_leg + round_in_leg
            matches = []
            byes = []

            for home, away in pairs:
                if home == "__BYE__" or away == "__BYE__":
                    bye_team = away if home == "__BYE__" else home
                    byes.append(bye_team)
                    continue

                key = (leg, global_round)
                global_match_counter[key] = global_match_counter.get(key, 0) + 1
                idx = global_match_counter[key]
                match_id = f"RR-L{leg}-R{global_round}-M{idx}"

                home_withdrawn = home in withdrawn_teams
                away_withdrawn = away in withdrawn_teams
                home_after = withdrawal_map.get(home, total_rounds)
                away_after = withdrawal_map.get(away, total_rounds)

                status = "scheduled"
                awarded_to = None

                if home_withdrawn and away_withdrawn:
                    status = "voided"
                    awarded_to = None
                elif withdrawal_policy == "void_all" and (home_withdrawn or away_withdrawn):
                    status = "voided"
                    awarded_to = None
                elif withdrawal_policy == "forfeit_remaining":
                    home_forfeited = home_withdrawn and global_round > home_after
                    away_forfeited = away_withdrawn and global_round > away_after
                    if home_forfeited and away_forfeited:
                        status = "voided"
                    elif home_forfeited:
                        status = "forfeit"
                        awarded_to = away
                    elif away_forfeited:
                        status = "forfeit"
                        awarded_to = home

                matches.append({
                    "match_id": match_id,
                    "leg": leg,
                    "home": home,
                    "away": away,
                    "status": status,
                    "awarded_to": awarded_to
                })

            result_rounds.append({
                "round": global_round,
                "matches": matches,
                "byes": byes
            })

    total = sum(len(r["matches"]) for r in result_rounds)
    scheduled = sum(1 for r in result_rounds for m in r["matches"] if m["status"] == "scheduled")
    forfeit = sum(1 for r in result_rounds for m in r["matches"] if m["status"] == "forfeit")
    voided = sum(1 for r in result_rounds for m in r["matches"] if m["status"] == "voided")

    return {
        "format": "round_robin",
        "legs": legs,
        "team_count": n,
        "round_count": total_rounds,
        "rounds": result_rounds,
        "summary": {"total": total, "scheduled": scheduled, "forfeit": forfeit, "voided": voided}
    }


# ─── SWISS SYSTEM ─────────────────────────────────────────────────────────────

def _compute_swiss_standings(teams: list, history: list):
    scores = {t: 0.0 for t in teams}
    opponents = {t: [] for t in teams}
    byes_given = set()

    for round_data in history:
        bye = round_data.get("bye")
        if bye:
            scores[bye] += 1.0
            byes_given.add(bye)
        for m in round_data.get("matches", []):
            h, a, result = m["home"], m["away"], m["result"]
            opponents[h].append(a)
            opponents[a].append(h)
            if result == "home":
                scores[h] += 1.0
            elif result == "away":
                scores[a] += 1.0
            else:
                scores[h] += 0.5
                scores[a] += 0.5

    buchholz = {t: sum(scores[o] for o in opponents[t]) for t in teams}
    seed_order = {t: i for i, t in enumerate(teams)}

    standings = sorted(teams, key=lambda t: (-scores[t], -buchholz[t], seed_order[t]))
    result = [{"rank": i+1, "team_id": t, "score": scores[t], "buchholz": buchholz[t]}
              for i, t in enumerate(standings)]
    return result, scores, buchholz, opponents, byes_given, seed_order


def _backtrack_pair(remaining: list, already_played: set):
    if not remaining:
        return []
    t = remaining[0]
    rest = remaining[1:]
    for i, opp in enumerate(rest):
        if (t, opp) not in already_played and (opp, t) not in already_played:
            result = _backtrack_pair(rest[:i] + rest[i+1:], already_played)
            if result is not None:
                return [(t, opp)] + result
    return None


def generate_swiss(teams: list, total_rounds: int, round_num: int, history: list) -> Optional[dict]:
    n = len(teams)
    standings_list, scores, buchholz, opponents, byes_given, seed_order = _compute_swiss_standings(teams, history)
    standings_sorted = [s["team_id"] for s in standings_list]

    already_played = set()
    for rd in history:
        for m in rd.get("matches", []):
            already_played.add((m["home"], m["away"]))
            already_played.add((m["away"], m["home"]))

    if round_num == 1:
        m = n // 2
        bye = teams[n - 1] if n % 2 == 1 else None
        pairings = [{"match_id": f"SW-R1-M{i+1}", "home": teams[i], "away": teams[i + m]}
                    for i in range(m)]
        return {
            "format": "swiss", "round": round_num, "total_rounds": total_rounds,
            "pairings": pairings, "bye": bye, "standings": standings_list
        }

    # Round >= 2
    n_odd = n % 2 == 1
    bye = None
    pairings = None

    if n_odd:
        bye_candidates = sorted(
            [t for t in teams if t not in byes_given],
            key=lambda t: (scores[t], buchholz[t], -seed_order[t])
        )
        for candidate in bye_candidates:
            remaining = [t for t in standings_sorted if t != candidate]
            result = _backtrack_pair(remaining, already_played)
            if result is not None:
                bye = candidate
                pairings = result
                break
        if pairings is None:
            return None  # NO_VALID_PAIRING
    else:
        pairings = _backtrack_pair(standings_sorted, already_played)
        if pairings is None:
            return None

    formatted = [{"match_id": f"SW-R{round_num}-M{i+1}", "home": h, "away": a}
                 for i, (h, a) in enumerate(pairings)]
    return {
        "format": "swiss", "round": round_num, "total_rounds": total_rounds,
        "pairings": formatted, "bye": bye, "standings": standings_list
    }


# ─── SINGLE ELIMINATION ───────────────────────────────────────────────────────

def _seed_order(b: int) -> list:
    if b == 2:
        return [1, 2]
    half = _seed_order(b // 2)
    result = []
    for s in half:
        result.append(s)
        result.append(b + 1 - s)
    return result


def generate_single_elim(teams: list, third_place_match: bool = False, results: list = None) -> dict:
    if results is None:
        results = []
    n = len(teams)
    b = 1
    while b < n:
        b *= 2

    seed_list = _seed_order(b)
    team_by_seed = {i+1: (teams[i] if i < n else None) for i in range(b)}
    num_rounds = int(math.log2(b))

    # Build match lookup
    all_matches = {}

    # Round 1
    for i in range(b // 2):
        s1 = seed_list[2 * i]
        s2 = seed_list[2 * i + 1]
        t1 = team_by_seed[s1]
        t2 = team_by_seed[s2]
        is_bye = (t1 is None or t2 is None)
        if t1 is None:
            home, away, hs, as_ = t2, None, s2, s1
        elif t2 is None:
            home, away, hs, as_ = t1, None, s1, s2
        else:
            if s1 <= s2:
                home, away, hs, as_ = t1, t2, s1, s2
            else:
                home, away, hs, as_ = t2, t1, s2, s1

        next_match_i = (i // 2) + 1
        slot = "home" if i % 2 == 0 else "away"
        winner_to = {"match_id": f"R2M{next_match_i}", "slot": slot} if num_rounds > 1 else None

        mid = f"R1M{i+1}"
        all_matches[mid] = {
            "match_id": mid, "bracket": "main", "round": 1, "index": i+1,
            "home": home, "away": away, "home_seed": hs, "away_seed": as_,
            "bye": is_bye, "winner": home if is_bye else None, "loser": None,
            "winner_to": winner_to, "loser_to": None
        }

    # Rounds 2+
    for r in range(2, num_rounds + 1):
        prev_count = b // (2 ** (r-1))
        count = b // (2 ** r)
        for i in range(count):
            is_final = (r == num_rounds)
            next_i = (i // 2) + 1
            slot = "home" if i % 2 == 0 else "away"
            winner_to = None if is_final else {"match_id": f"R{r+1}M{next_i}", "slot": slot}
            mid = f"R{r}M{i+1}"
            all_matches[mid] = {
                "match_id": mid, "bracket": "main", "round": r, "index": i+1,
                "home": None, "away": None, "home_seed": None, "away_seed": None,
                "bye": False, "winner": None, "loser": None,
                "winner_to": winner_to, "loser_to": None
            }

    # Propagate R1 bye winners
    for i in range(b // 2):
        m = all_matches[f"R1M{i+1}"]
        if m["bye"] and m["winner"] and m["winner_to"]:
            wt = m["winner_to"]
            nm = all_matches[wt["match_id"]]
            if wt["slot"] == "home":
                nm["home"] = m["winner"]
            else:
                nm["away"] = m["winner"]

    # Apply results
    for res in results:
        mid = res["match_id"]
        if mid not in all_matches:
            raise ValueError(f"UNKNOWN_MATCH:{mid}")
        m = all_matches[mid]
        winner_id = res["winner"]
        participants = [x for x in [m["home"], m["away"]] if x is not None]
        if winner_id not in participants:
            raise ValueError(f"INVALID_WINNER:{winner_id}:{mid}")
        loser_list = [p for p in participants if p != winner_id]
        m["winner"] = winner_id
        m["loser"] = loser_list[0] if loser_list else None
        if m["winner_to"]:
            wt = m["winner_to"]
            nm = all_matches[wt["match_id"]]
            if wt["slot"] == "home":
                nm["home"] = winner_id
            else:
                nm["away"] = winner_id

    # Third place
    if third_place_match and num_rounds >= 2:
        sf_round_matches = [m for m in all_matches.values() if m["round"] == num_rounds - 1 and m["bracket"] == "main"]
        sf_round_matches.sort(key=lambda m: m["index"])
        if len(sf_round_matches) >= 2:
            tp_mid = "TP"
            all_matches[tp_mid] = {
                "match_id": tp_mid, "bracket": "third_place", "round": num_rounds,
                "index": 1, "home": sf_round_matches[0].get("loser"),
                "away": sf_round_matches[1].get("loser") if len(sf_round_matches) > 1 else None,
                "bye": False, "winner": None, "loser": None,
                "winner_to": None, "loser_to": None
            }
            sf_round_matches[0]["loser_to"] = {"match_id": tp_mid, "slot": "home"}
            sf_round_matches[1]["loser_to"] = {"match_id": tp_mid, "slot": "away"}

    # Build output rounds
    rounds_out = []
    for r in range(1, num_rounds + 1):
        matches_in_r = sorted([m for m in all_matches.values() if m["round"] == r and m["bracket"] == "main"],
                              key=lambda m: m["index"])
        rounds_out.append({"round": r, "matches": matches_in_r})
    # Third place
    if third_place_match and "TP" in all_matches:
        rounds_out.append({"round": num_rounds, "matches": [all_matches["TP"]]})

    return {"format": "single_elim", "bracket_size": b, "rounds": rounds_out}


# ─── DOUBLE ELIMINATION ───────────────────────────────────────────────────────

def generate_double_elim(teams: list, bracket_reset: bool = True, results: list = None) -> dict:
    if results is None:
        results = []
    n = len(teams)
    b = 1
    while b < n:
        b *= 2
    k = int(math.log2(b))

    seed_list = _seed_order(b)
    team_by_seed = {i+1: (teams[i] if i < n else None) for i in range(b)}

    all_matches = {}

    # ── Winners bracket ──
    for r in range(1, k + 1):
        count = b // (2 ** r)
        for i in range(count):
            is_wr_final = (r == k)
            mid = f"WR{r}M{i+1}"

            next_wr_i = (i // 2) + 1
            slot = "home" if i % 2 == 0 else "away"
            winner_to = {"match_id": "GF1", "slot": "home"} if is_wr_final else \
                        {"match_id": f"WR{r+1}M{next_wr_i}", "slot": slot}

            # Loser routing
            if r == 1:
                lb_i = (i // 2) + 1
                lb_slot = "home" if i % 2 == 0 else "away"
                loser_to = {"match_id": f"LR1M{lb_i}", "slot": lb_slot}
            else:
                lb_round = 2 * r - 2
                lb_i = i + 1
                loser_to = {"match_id": f"LR{lb_round}M{lb_i}", "slot": "away"}

            if r == 1:
                s1 = seed_list[2 * i]
                s2 = seed_list[2 * i + 1]
                t1 = team_by_seed[s1]
                t2 = team_by_seed[s2]
                is_bye = (t1 is None or t2 is None)
                if t1 is None:
                    home, away, hs, as_ = t2, None, s2, s1
                elif t2 is None:
                    home, away, hs, as_ = t1, None, s1, s2
                else:
                    if s1 <= s2:
                        home, away, hs, as_ = t1, t2, s1, s2
                    else:
                        home, away, hs, as_ = t2, t1, s2, s1
                m = {
                    "match_id": mid, "bracket": "winners", "round": r, "index": i+1,
                    "home": home, "away": away, "home_seed": hs, "away_seed": as_,
                    "bye": is_bye, "winner": home if is_bye else None, "loser": None,
                    "winner_to": winner_to, "loser_to": loser_to
                }
            else:
                m = {
                    "match_id": mid, "bracket": "winners", "round": r, "index": i+1,
                    "home": None, "away": None, "home_seed": None, "away_seed": None,
                    "bye": False, "winner": None, "loser": None,
                    "winner_to": winner_to, "loser_to": loser_to
                }
            all_matches[mid] = m

    # ── Losers bracket ──
    # 2(k-1) LR rounds; round j-pair has B/2^(j+1) matches
    for j in range(1, k):
        num_lr_matches = b // (2 ** (j + 1))
        for sub in range(1, 3):  # LR round 2j-1 and 2j
            lr_r = 2 * j - 1 + (sub - 1)
            if lr_r > 2 * (k - 1):
                break
            for i in range(num_lr_matches):
                is_lb_final = (lr_r == 2 * (k - 1))
                mid = f"LR{lr_r}M{i+1}"
                if is_lb_final:
                    winner_to = {"match_id": "GF1", "slot": "away"}
                else:
                    next_lr = lr_r + 1
                    if sub == 1:  # going to next LR
                        next_i = (i // 2) + 1
                        next_slot = "home" if i % 2 == 0 else "away"
                    else:
                        next_i = i + 1
                        next_slot = "home"
                    winner_to = {"match_id": f"LR{next_lr}M{next_i}", "slot": next_slot}
                all_matches[mid] = {
                    "match_id": mid, "bracket": "losers", "round": lr_r, "index": i+1,
                    "home": None, "away": None, "bye": False,
                    "winner": None, "loser": None,
                    "winner_to": winner_to, "loser_to": None
                }

    # ── Grand Final ──
    gf1 = {"match_id": "GF1", "bracket": "grand_final", "round": 1, "index": 1,
            "home": None, "away": None, "bye": False,
            "winner": None, "loser": None, "winner_to": None, "loser_to": None}
    gf2 = {"match_id": "GF2", "bracket": "grand_final", "round": 2, "index": 2,
            "home": None, "away": None, "bye": False,
            "winner": None, "loser": None, "winner_to": None, "loser_to": None,
            "conditional": True, "required": None}
    all_matches["GF1"] = gf1
    all_matches["GF2"] = gf2

    # Propagate WR1 byes
    for i in range(b // 2):
        mid = f"WR1M{i+1}"
        if mid in all_matches:
            m = all_matches[mid]
            if m["bye"] and m["winner"] and m["winner_to"]:
                wt = m["winner_to"]
                if wt["match_id"] in all_matches:
                    nm = all_matches[wt["match_id"]]
                    if wt["slot"] == "home":
                        nm["home"] = m["winner"]
                    else:
                        nm["away"] = m["winner"]

    # Apply results
    lb_final_mid = f"LR{2*(k-1)}M1"
    for res in results:
        mid = res["match_id"]
        if mid not in all_matches:
            raise ValueError(f"UNKNOWN_MATCH:{mid}")
        m = all_matches[mid]
        winner_id = res["winner"]
        participants = [x for x in [m.get("home"), m.get("away")] if x is not None]
        if winner_id not in participants:
            raise ValueError(f"INVALID_WINNER:{winner_id}:{mid}")
        loser_list = [p for p in participants if p != winner_id]
        m["winner"] = winner_id
        m["loser"] = loser_list[0] if loser_list else None
        if m.get("winner_to") and m["winner_to"].get("match_id") in all_matches:
            wt = m["winner_to"]
            nm = all_matches[wt["match_id"]]
            if wt["slot"] == "home":
                nm["home"] = winner_id
            else:
                nm["away"] = winner_id
        if m.get("loser_to") and m["loser"] and m["loser_to"].get("match_id") in all_matches:
            lt = m["loser_to"]
            nm = all_matches[lt["match_id"]]
            if lt["slot"] == "home":
                nm["home"] = m["loser"]
            else:
                nm["away"] = m["loser"]
        # GF2 bracket reset
        if mid == "GF1" and bracket_reset:
            lb_winner = all_matches.get(lb_final_mid, {}).get("winner")
            if lb_winner and winner_id == lb_winner:
                gf2["required"] = True
                gf2["home"] = gf1.get("home")
                gf2["away"] = gf1.get("away")
            else:
                gf2["required"] = False

    wr_out = [{"round": r, "matches": sorted(
        [m for m in all_matches.values() if m["bracket"] == "winners" and m["round"] == r],
        key=lambda m: m["index"])} for r in range(1, k+1)]
    lr_out = [{"round": r, "matches": sorted(
        [m for m in all_matches.values() if m["bracket"] == "losers" and m["round"] == r],
        key=lambda m: m["index"])} for r in range(1, 2*k-1)]
    lr_out = [r for r in lr_out if r["matches"]]
    grand_final = [gf1, gf2] if bracket_reset else [gf1]

    return {
        "format": "double_elim", "bracket_size": b, "bracket_reset": bracket_reset,
        "winners": wr_out, "losers": lr_out, "grand_final": grand_final
    }
