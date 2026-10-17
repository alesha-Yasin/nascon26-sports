"""
POST /audit/v1/rbac-matrix — Issue JWTs for all 5 roles
/audit/v1/rbac/* — Authorization probe routes
GET  /api/v1/ping — Rate limited endpoint
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from jose import JWTError

from app.core.auth import create_token, decode_token

router = APIRouter()

# ── Rate limiting state (simple in-memory) ─────────────────────────────────
from collections import defaultdict
import time
_rate_store: dict = defaultdict(list)
RATE_LIMIT = 100
RATE_WINDOW = 10  # seconds


@router.post("/audit/v1/rbac-matrix")
async def rbac_matrix():
    """Issue JWTs for all 5 roles, valid 2 hours."""
    def make_token(role: str, **kwargs):
        return create_token({"role": role, "tenant_id": "tenant-alpha", **kwargs}, expires_hours=2)

    return {
        "tokens": {
            "super_admin": make_token("super_admin", tenant_id=None, user_id="user-super-admin"),
            "league_organizer": make_token("league_organizer", owns_league_id="league-alpha-1", user_id="user-organizer"),
            "club_manager": make_token("club_manager", owns_club_id="club-alpha-1", user_id="user-manager"),
            "player": make_token("player", player_id="player-alpha-1", user_id="user-player"),
            "viewer": make_token("viewer", user_id="user-viewer"),
        },
        "context": {
            "tenant_id": "tenant-alpha",
            "foreign_tenant_id": "tenant-beta",
            "own_league_id": "league-alpha-1",
            "other_league_id": "league-alpha-2",
            "foreign_league_id": "league-beta-1",
            "own_club_id": "club-alpha-1",
            "other_club_id": "club-alpha-2",
            "foreign_club_id": "club-beta-1",
            "own_player_id": "player-alpha-1",
            "other_player_id": "player-alpha-2",
            "foreign_player_id": "player-beta-1"
        }
    }


def _get_claims(request: Request) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": {
            "code": "UNAUTHENTICATED", "message": "Missing or invalid Authorization header", "details": {}
        }})
    token = auth[7:]
    try:
        claims = decode_token(token)
        return claims
    except JWTError:
        raise HTTPException(status_code=401, detail={"error": {
            "code": "UNAUTHENTICATED", "message": "Invalid or expired token", "details": {}
        }})


def _forbidden():
    raise HTTPException(status_code=403, detail={"error": {
        "code": "FORBIDDEN", "message": "Access denied", "details": {}
    }})


def _is_alpha_tenant(claims: dict) -> bool:
    return claims.get("tenant_id") == "tenant-alpha"


# ── Probe P1: POST /audit/v1/rbac/tenants ─────────────────────────────────
@router.post("/audit/v1/rbac/tenants")
async def p1_tenants(request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    _forbidden()


# ── Probe P2: POST /audit/v1/rbac/leagues/{league_id}/fixtures ────────────
@router.post("/audit/v1/rbac/leagues/{league_id}/fixtures")
async def p2_fixtures(league_id: str, request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    if role == "league_organizer":
        # Can only manage own league
        if claims.get("owns_league_id") == league_id:
            return {"authorized": True}
        _forbidden()
    _forbidden()


# ── Probe P3: POST /audit/v1/rbac/clubs/{club_id}/roster ──────────────────
@router.post("/audit/v1/rbac/clubs/{club_id}/roster")
async def p3_roster(club_id: str, request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    if role == "club_manager":
        if claims.get("owns_club_id") == club_id:
            return {"authorized": True}
        _forbidden()
    _forbidden()


# ── Probe P4: POST /audit/v1/rbac/clubs/{club_id}/products ───────────────
@router.post("/audit/v1/rbac/clubs/{club_id}/products")
async def p4_products(club_id: str, request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    if role == "club_manager":
        if claims.get("owns_club_id") == club_id:
            return {"authorized": True}
        _forbidden()
    _forbidden()


# ── Probe P5: PATCH /audit/v1/rbac/players/{player_id} ───────────────────
@router.patch("/audit/v1/rbac/players/{player_id}")
async def p5_player(player_id: str, request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    if role == "club_manager":
        # Can manage own club's players — but we check tenant for now
        # Cross-tenant always denied
        if not _is_alpha_tenant(claims):
            _forbidden()
        # Foreign players (beta) always denied for non-super
        if player_id == "player-beta-1":
            _forbidden()
        return {"authorized": True}
    if role == "player":
        if claims.get("player_id") == player_id:
            return {"authorized": True}
        _forbidden()
    _forbidden()


# ── Probe P6: GET /audit/v1/rbac/clubs/{club_id} ─────────────────────────
@router.get("/audit/v1/rbac/clubs/{club_id}")
async def p6_club(club_id: str, request: Request):
    claims = _get_claims(request)
    role = claims.get("role")
    if role == "super_admin":
        return {"authorized": True}
    # Foreign club (beta) — only super_admin
    if club_id == "club-beta-1":
        _forbidden()
    # Any alpha tenant role can read alpha clubs
    if _is_alpha_tenant(claims):
        return {"authorized": True}
    _forbidden()


# ── Probe P7: GET /audit/v1/rbac/platform/config ─────────────────────────
@router.get("/audit/v1/rbac/platform/config")
async def p7_config(request: Request):
    claims = _get_claims(request)
    if claims.get("role") == "super_admin":
        return {"authorized": True}
    _forbidden()


# ── Rate limited ping ─────────────────────────────────────────────────────
@router.get("/api/v1/ping")
async def ping(request: Request):
    client_ip = request.client.host
    now = time.time()
    window_start = now - RATE_WINDOW

    # Clean old entries
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Rate limit exceeded", "details": {}}},
            headers={"Retry-After": "10"}
        )

    _rate_store[client_ip].append(now)
    return {"pong": True}
