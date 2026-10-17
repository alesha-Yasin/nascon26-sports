"""Tests for HMAC signing and standings engine."""
import hashlib
import pytest
from app.core.signing import sign_payload, canonical_json, lots_key
from app.services.standings import compute_standings


class TestSigning:
    def test_canonical_json_sorted_keys(self):
        obj = {"team_id": "t1", "event_type": "goal"}
        result = canonical_json(obj)
        assert result == '{"event_type":"goal","team_id":"t1"}'

    def test_canonical_json_no_whitespace(self):
        obj = {"a": 1, "b": 2}
        result = canonical_json(obj)
        assert " " not in result

    def test_sign_deterministic(self):
        s1 = sign_payload("evt-1", {"team_id": "t1", "event_type": "goal"})
        s2 = sign_payload("evt-1", {"team_id": "t1", "event_type": "goal"})
        assert s1 == s2

    def test_sign_lowercase_hex_64_chars(self):
        sig = sign_payload("evt-1", {"team_id": "t1"})
        assert len(sig) == 64
        assert sig == sig.lower()

    def test_lots_key_deterministic(self):
        k1 = lots_key(42, "lg-1", "t1")
        k2 = lots_key(42, "lg-1", "t1")
        assert k1 == k2
        assert len(k1) == 64

    def test_lots_key_test_vector(self):
        """Test vector from Appendix A."""
        k = lots_key(42, "lg-1", "t1")
        assert k == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"


class TestStandings:
    def _make_score(self, home_score, away_score, outcome, home_id, away_id):
        return {
            "status": "completed",
            "outcome": outcome,
            "home": {"team_id": home_id, "score": home_score, "fair_play": 0,
                     "balls": None, "wickets": None, "overs": None},
            "away": {"team_id": away_id, "score": away_score, "fair_play": 0,
                     "balls": None, "wickets": None, "overs": None}
        }

    def test_basic_standings(self):
        league = {
            "league_id": "lg-1", "sport_id": "football",
            "teams": ["t1","t2","t3","t4"],
            "fixtures": [
                {"match_id": "m1", "home": "t1", "away": "t2"},
                {"match_id": "m2", "home": "t3", "away": "t4"},
            ],
            "points_win": 3, "points_draw": 1, "points_loss": 0,
            "tie_break_order": ["h2h_points","h2h_diff","overall_diff","scored","fair_play","draw_lots"],
            "qualification_spots": 2, "lots_seed": 42,
            "sport_config": {"scoring_model": "event", "periods": {}}
        }
        scores = {
            "m1": self._make_score(2, 1, "home_win", "t1", "t2"),
            "m2": self._make_score(0, 1, "away_win", "t3", "t4"),
        }
        result = compute_standings(league, scores)
        assert result["table"][0]["team_id"] in ["t1","t4"]
        assert result["table"][0]["points"] == 3

    def test_clinched_status(self):
        league = {
            "league_id": "lg-1", "sport_id": "football",
            "teams": ["t1","t2"],
            "fixtures": [{"match_id": "m1", "home": "t1", "away": "t2"}],
            "points_win": 3, "points_draw": 1, "points_loss": 0,
            "tie_break_order": ["h2h_points","h2h_diff","overall_diff","scored","fair_play","draw_lots"],
            "qualification_spots": 1, "lots_seed": 42,
            "sport_config": {"scoring_model": "event", "periods": {}}
        }
        scores = {"m1": self._make_score(3, 0, "home_win", "t1", "t2")}
        result = compute_standings(league, scores)
        t1_row = next(r for r in result["table"] if r["team_id"] == "t1")
        t2_row = next(r for r in result["table"] if r["team_id"] == "t2")
        assert t1_row["status"] == "clinched"
        assert t2_row["status"] == "eliminated"

    def test_h2h_matrix_present(self):
        league = {
            "league_id": "lg-1", "sport_id": "football",
            "teams": ["t1","t2"],
            "fixtures": [{"match_id": "m1", "home": "t1", "away": "t2"}],
            "points_win": 3, "points_draw": 1, "points_loss": 0,
            "tie_break_order": ["h2h_points","h2h_diff","overall_diff","scored","fair_play","draw_lots"],
            "qualification_spots": 1, "lots_seed": 42,
            "sport_config": {"scoring_model": "event", "periods": {}}
        }
        scores = {"m1": self._make_score(2, 0, "home_win", "t1", "t2")}
        result = compute_standings(league, scores)
        assert "t1" in result["h2h"]
        assert "t2" in result["h2h"]["t1"]
        assert result["h2h"]["t1"]["t2"]["points"] == 3

    def test_draw_lots_ordering(self):
        """draw_lots must be deterministic per Section 5.10."""
        from app.core.signing import lots_key
        seed, lid = 42, "lg-1"
        t1_key = lots_key(seed, lid, "t1")
        t2_key = lots_key(seed, lid, "t2")
        t3_key = lots_key(seed, lid, "t3")
        # Verify test vectors from Appendix A
        assert t1_key == "0613316991ce0ac31e88d6003e3ff4d5e21bb072ac5f81b42c0cdc6598453293"
        assert t2_key == "e3e3a14e22727f936e1f288cf5d02a8a9362b1da13c5432725fc10b2c7955dd9"
        assert t3_key == "c8f28e3c2f1eb6c4f636b4f57050e3362a2b39c07fda9b61742a26dd20397028"
        # t1 < t3 < t2 ascending → t1 best
        assert t1_key < t3_key < t2_key
