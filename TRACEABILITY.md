# TRACEABILITY.md — FR/NFR to Source File Mapping

| ID | Requirement | Source Files | Tests |
|----|------------|--------------|-------|
| FR-1.1 | Multi-Sport Taxonomy & Event-Sourced Scoring | `backend/app/models/models.py` (Sport), `backend/app/api/sports.py`, `backend/app/api/events.py`, `backend/app/services/scoring.py` | `backend/tests/test_sports.py`, `backend/tests/test_events.py` |
| FR-1.2 | League and Tournament Setup | `backend/app/api/leagues.py`, `backend/app/models/models.py` (League) | `backend/tests/test_leagues.py` |
| FR-1.3 | Match and Fixture Scheduling | `backend/app/services/fixtures.py`, `backend/app/api/fixtures.py` | `backend/tests/test_fixtures.py` |
| FR-1.4 | Automated Standings and Tables | `backend/app/services/standings.py`, `backend/app/api/standings.py` | `backend/tests/test_standings.py` |
| FR-2.1 | Club Profiles and Tenant Isolation | `backend/app/models/models.py` (Club, Tenant) | `backend/tests/test_rbac.py` |
| FR-2.2 | Roster and Player Registry | `backend/app/api/roster.py`, `backend/app/models/models.py` (Player, Squad, RosterAudit) | `backend/tests/test_roster.py` |
| FR-2.3 | Integrated Club Merchandise Store | `backend/app/api/checkout.py`, `backend/app/services/pdf.py`, `backend/app/models/models.py` (Order, ProductVariant) | `backend/tests/test_checkout.py` |
| FR-5.1 | Five-Tier RBAC | `backend/app/api/rbac.py`, `backend/app/core/auth.py` | `backend/tests/test_rbac.py` |
| NFR-3 | Concurrency Correctness | `backend/app/api/checkout.py` (SELECT FOR UPDATE) | `backend/tests/test_checkout.py` |
| NFR-4 | Offline Tolerance | `backend/app/api/offline_sync.py`, `mobile/lib/` | `backend/tests/test_offline.py` |
| NFR-5 | Security | `backend/app/core/auth.py`, `backend/app/main.py` (body limit), `backend/app/api/rbac.py` | `backend/tests/test_rbac.py` |
| NFR-7 | Reproducibility | `docker-compose.yml`, `backend/app/core/seed.py` | Manual: `docker compose up -d --build` |

## Signature Implementation
- File: `backend/app/core/signing.py`
- Function: `sign_payload(id_, payload_obj) -> str`
- Algorithm: HMAC-SHA256 per Section 5.3
- Test vector: Salt=demo-salt, id=evt-1, payload={"team_id":"t1","event_type":"goal"} → 972a8b558690b19121cc5bea84978f85e8eb15a3735018db36616bab1d7ec501

## Endpoint Coverage
All endpoints in Section 5.1 are implemented:
- GET /health → `backend/app/api/health.py`
- POST /audit/v1/reset → `backend/app/api/health.py`
- POST /audit/v1/sports → `backend/app/api/sports.py`
- POST /audit/v1/fixtures → `backend/app/api/fixtures.py`
- POST /audit/v1/leagues → `backend/app/api/leagues.py`
- POST /audit/v1/events → `backend/app/api/events.py`
- GET /audit/v1/score/{match_id} → `backend/app/api/events.py`
- GET /audit/v1/standings/{league_id} → `backend/app/api/standings.py`
- POST /audit/v1/roster/setup → `backend/app/api/roster.py`
- POST /audit/v1/roster/transfer → `backend/app/api/roster.py`
- GET /audit/v1/roster/history/{player_id} → `backend/app/api/roster.py`
- POST /audit/v1/checkout → `backend/app/api/checkout.py`
- GET /audit/v1/inventory/{variant_id} → `backend/app/api/checkout.py`
- POST /audit/v1/rbac-matrix → `backend/app/api/rbac.py`
- /audit/v1/rbac/* (7 routes) → `backend/app/api/rbac.py`
- GET /api/v1/ping → `backend/app/api/rbac.py`
- POST /audit/v1/offline-sync → `backend/app/api/offline_sync.py`
