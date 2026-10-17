"""POST /audit/v1/fixtures — Schedule generation"""
import math
from fastapi import APIRouter, HTTPException

from app.services.fixtures import (
    generate_round_robin, generate_swiss,
    generate_single_elim, generate_double_elim
)

router = APIRouter()


def _400(msg, fields=None):
    detail = {"error": {"code": "VALIDATION_ERROR", "message": msg,
                        "details": {"fields": fields or []}}}
    raise HTTPException(status_code=400, detail=detail)


@router.post("/audit/v1/fixtures")
async def generate_fixtures(body: dict):
    fmt = body.get("format")
    teams = body.get("teams", [])
    params = body.get("params", {})

    if not isinstance(teams, list) or len(teams) == 0:
        _400("teams required", ["teams"])

    # Uniqueness check
    if len(set(teams)) != len(teams):
        _400("Duplicate team ids", ["teams"])

    n = len(teams)

    if fmt == "round_robin":
        if not (2 <= n <= 40):
            _400(f"round_robin requires 2-40 teams, got {n}", ["teams"])
        legs = params.get("legs", 1)
        if legs not in (1, 2):
            _400("legs must be 1 or 2", ["legs"])

        withdrawals = params.get("withdrawals", [])
        withdrawal_policy = params.get("withdrawal_policy", "forfeit_remaining")

        # Validate withdrawals
        team_set = set(teams)
        odd = n % 2 == 1
        working = list(teams) + (["__BYE__"] if odd else [])
        n_w = len(working)
        rounds_per_leg = n_w - 1
        total_rounds = rounds_per_leg * legs

        for w in withdrawals:
            if w.get("team_id") not in team_set:
                _400(f"Unknown team in withdrawal: {w.get('team_id')}", ["withdrawals"])
            ar = w.get("after_round", -1)
            if not isinstance(ar, int) or ar < 0 or ar > total_rounds:
                _400(f"after_round out of range 0..{total_rounds}", ["withdrawals"])

        return generate_round_robin(teams, legs=legs, withdrawals=withdrawals,
                                    withdrawal_policy=withdrawal_policy)

    elif fmt == "swiss":
        if not (2 <= n <= 64):
            _400(f"swiss requires 2-64 teams, got {n}", ["teams"])
        default_rounds = math.ceil(math.log2(n)) if n > 1 else 1
        total_rounds = params.get("total_rounds", default_rounds)
        round_num = params.get("round", 1)
        history = params.get("history", [])

        if not (1 <= total_rounds <= n - 1):
            _400("total_rounds must be 1..n-1", ["total_rounds"])
        if not (1 <= round_num <= total_rounds):
            _400("round out of range", ["round"])

        # Validate history has exactly rounds 1..round-1
        expected = set(range(1, round_num))
        got = {r.get("round") for r in history}
        if got != expected:
            _400(f"history must contain rounds 1..{round_num-1}", ["history"])

        result = generate_swiss(teams, total_rounds, round_num, history)
        if result is None:
            raise HTTPException(status_code=409, detail={"error": {
                "code": "NO_VALID_PAIRING",
                "message": f"No valid rematch-free pairing for round {round_num}",
                "details": {"round": round_num}
            }})
        return result

    elif fmt == "single_elim":
        if not (2 <= n <= 128):
            _400(f"single_elim requires 2-128 teams, got {n}", ["teams"])
        third_place = params.get("third_place_match", False)
        results = params.get("results", [])

        try:
            return generate_single_elim(teams, third_place_match=third_place, results=results)
        except ValueError as e:
            msg = str(e)
            if "UNKNOWN_MATCH" in msg:
                raise HTTPException(status_code=400, detail={"error": {
                    "code": "VALIDATION_ERROR", "message": msg,
                    "details": {"fields": ["results"]}
                }})
            elif "INVALID_WINNER" in msg:
                raise HTTPException(status_code=400, detail={"error": {
                    "code": "VALIDATION_ERROR", "message": msg,
                    "details": {"fields": ["results"]}
                }})
            raise HTTPException(status_code=400, detail={"error": {
                "code": "VALIDATION_ERROR", "message": str(e), "details": {}
            }})

    elif fmt == "double_elim":
        if not (3 <= n <= 128):
            _400(f"double_elim requires 3-128 teams, got {n}", ["teams"])
        bracket_reset = params.get("bracket_reset", True)
        results = params.get("results", [])

        try:
            return generate_double_elim(teams, bracket_reset=bracket_reset, results=results)
        except ValueError as e:
            msg = str(e)
            if "UNKNOWN_MATCH" in msg:
                raise HTTPException(status_code=400, detail={"error": {
                    "code": "VALIDATION_ERROR", "message": msg,
                    "details": {"fields": ["results"]}
                }})
            raise HTTPException(status_code=400, detail={"error": {
                "code": "VALIDATION_ERROR", "message": str(e), "details": {}
            }})

    else:
        _400(f"Unknown format: {fmt}", ["format"])
