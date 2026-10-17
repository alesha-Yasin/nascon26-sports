"""Tests for fixture scheduling algorithms."""
import pytest
import math
from app.services.fixtures import (
    generate_round_robin, generate_swiss,
    generate_single_elim, generate_double_elim, _seed_order
)


class TestRoundRobin:
    def test_basic_even_teams(self):
        result = generate_round_robin(["t1","t2","t3","t4"])
        assert result["format"] == "round_robin"
        assert result["team_count"] == 4
        assert result["round_count"] == 3
        assert result["legs"] == 1

    def test_odd_teams_has_byes(self):
        result = generate_round_robin(["t1","t2","t3"])
        assert result["round_count"] == 3
        for r in result["rounds"]:
            assert len(r["byes"]) == 1

    def test_double_leg(self):
        result = generate_round_robin(["t1","t2","t3","t4"], legs=2)
        assert result["round_count"] == 6

    def test_forfeit_withdrawal(self):
        result = generate_round_robin(
            ["t1","t2","t3","t4"],
            withdrawals=[{"team_id": "t3", "after_round": 1}],
            withdrawal_policy="forfeit_remaining"
        )
        forfeits = [m for r in result["rounds"] for m in r["matches"] if m["status"] == "forfeit"]
        assert len(forfeits) > 0

    def test_void_withdrawal(self):
        result = generate_round_robin(
            ["t1","t2","t3","t4"],
            withdrawals=[{"team_id": "t3", "after_round": 0}],
            withdrawal_policy="void_all"
        )
        voided = [m for r in result["rounds"] for m in r["matches"] if m["status"] == "voided"]
        assert len(voided) > 0

    def test_summary_totals(self):
        result = generate_round_robin(["t1","t2","t3","t4"])
        s = result["summary"]
        assert s["total"] == s["scheduled"] + s["forfeit"] + s["voided"]

    def test_match_ids_unique(self):
        result = generate_round_robin(["t1","t2","t3","t4"])
        ids = [m["match_id"] for r in result["rounds"] for m in r["matches"]]
        assert len(ids) == len(set(ids))


class TestSwiss:
    def test_round1_exact_pairing(self):
        teams = ["t1","t2","t3","t4"]
        result = generate_swiss(teams, 3, 1, [])
        assert result["round"] == 1
        assert len(result["pairings"]) == 2
        assert result["bye"] is None

    def test_round1_odd_teams_bye(self):
        teams = ["t1","t2","t3","t4","t5"]
        result = generate_swiss(teams, 3, 1, [])
        assert result["bye"] == "t5"  # last seed gets bye
        assert len(result["pairings"]) == 2

    def test_round2_no_rematches(self):
        teams = ["t1","t2","t3","t4"]
        history = [{"round": 1, "bye": None,
                    "matches": [{"home":"t1","away":"t3","result":"home"},
                                {"home":"t2","away":"t4","result":"home"}]}]
        result = generate_swiss(teams, 3, 2, history)
        assert result is not None
        pairs = {(p["home"], p["away"]) for p in result["pairings"]}
        assert ("t1","t3") not in pairs and ("t3","t1") not in pairs
        assert ("t2","t4") not in pairs and ("t4","t2") not in pairs

    def test_standings_score(self):
        teams = ["t1","t2","t3","t4"]
        history = [{"round": 1, "bye": None,
                    "matches": [{"home":"t1","away":"t3","result":"home"},
                                {"home":"t2","away":"t4","result":"draw"}]}]
        result = generate_swiss(teams, 3, 2, history)
        t1_standing = next(s for s in result["standings"] if s["team_id"] == "t1")
        assert t1_standing["score"] == 1.0


class TestSingleElim:
    def test_seed_order_4(self):
        order = _seed_order(4)
        assert order == [1, 4, 2, 3]

    def test_seed_order_8(self):
        order = _seed_order(8)
        assert order == [1, 8, 4, 5, 2, 7, 3, 6]

    def test_basic_4_teams(self):
        result = generate_single_elim(["t1","t2","t3","t4"])
        assert result["bracket_size"] == 4
        assert len(result["rounds"]) == 2

    def test_6_teams_bracket_size_8(self):
        result = generate_single_elim(["t1","t2","t3","t4","t5","t6"])
        assert result["bracket_size"] == 8

    def test_byes_for_non_power_of_two(self):
        result = generate_single_elim(["t1","t2","t3","t4","t5","t6"])
        r1 = result["rounds"][0]["matches"]
        byes = [m for m in r1 if m["bye"]]
        assert len(byes) == 2  # 8-6=2 byes

    def test_winner_propagation(self):
        result = generate_single_elim(
            ["t1","t2","t3","t4"],
            results=[{"match_id": "R1M1", "winner": "t1"}]
        )
        r2 = result["rounds"][1]["matches"]
        assert r2[0]["home"] == "t1" or r2[0]["away"] == "t1"

    def test_third_place_match(self):
        result = generate_single_elim(["t1","t2","t3","t4"], third_place_match=True)
        all_matches = [m for r in result["rounds"] for m in r["matches"]]
        tp = next((m for m in all_matches if m["bracket"] == "third_place"), None)
        assert tp is not None


class TestDoubleElim:
    def test_basic_8_teams(self):
        result = generate_double_elim(["t1","t2","t3","t4","t5","t6","t7","t8"])
        assert result["bracket_size"] == 8
        assert len(result["winners"]) == 3  # k=3 rounds
        assert result["bracket_reset"] is True

    def test_grand_final_exists(self):
        result = generate_double_elim(["t1","t2","t3","t4"])
        gf = result["grand_final"]
        assert any(m["match_id"] == "GF1" for m in gf)
        assert any(m["match_id"] == "GF2" for m in gf)

    def test_gf2_conditional(self):
        result = generate_double_elim(["t1","t2","t3","t4"])
        gf2 = next(m for m in result["grand_final"] if m["match_id"] == "GF2")
        assert gf2["conditional"] is True
        assert gf2["required"] is None  # no result yet
