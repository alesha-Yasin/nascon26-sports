"""Seed baseline data and reset logic."""
import hashlib
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Sport, Tenant, League, User, Club, Player, Squad,
    RosterLeague, Product, ProductVariant, DiscountCode, AppState
)

def _hash_password(pw): return "sha256:" + __import__("hashlib").sha256(pw.encode()).hexdigest()

DEFAULT_TIE_BREAK = ["h2h_points", "h2h_diff", "overall_diff", "scored", "fair_play", "draw_lots"]

SPORTS_SEED = [
    {
        "sport_id": "football",
        "name": "Football",
        "scoring_model": "event",
        "periods": {"count": 2, "duration_minutes": 45},
        "scoring_events": {"goal": {"points": 1}},
        "draw_allowed": True,
        "overtime": {"policy": "none"},
        "tie_break_order": DEFAULT_TIE_BREAK,
        "roster_config": {
            "min_squad_size": 11, "max_squad_size": 25,
            "required_positions": {"gk": 1}
        }
    },
    {
        "sport_id": "basketball",
        "name": "Basketball",
        "scoring_model": "event",
        "periods": {"count": 4, "duration_minutes": 12},
        "scoring_events": {
            "free_throw": {"points": 1},
            "two_pointer": {"points": 2},
            "three_pointer": {"points": 3}
        },
        "draw_allowed": False,
        "overtime": {"policy": "extra_time", "duration_minutes": 5},
        "tie_break_order": DEFAULT_TIE_BREAK,
        "roster_config": {
            "min_squad_size": 5, "max_squad_size": 15,
            "required_positions": {}
        }
    },
    {
        "sport_id": "cricket",
        "name": "Cricket",
        "scoring_model": "innings",
        "periods": {
            "innings_per_team": 1, "overs_per_innings": 20,
            "balls_per_over": 6, "wickets_per_innings": 10
        },
        "scoring_events": {
            "dot_ball": {"runs": 0, "legal_ball": True, "wicket": False},
            "single": {"runs": 1, "legal_ball": True, "wicket": False},
            "two": {"runs": 2, "legal_ball": True, "wicket": False},
            "four": {"runs": 4, "legal_ball": True, "wicket": False},
            "six": {"runs": 6, "legal_ball": True, "wicket": False},
            "wide": {"runs": 1, "legal_ball": False, "wicket": False},
            "no_ball": {"runs": 1, "legal_ball": False, "wicket": False},
            "wicket": {"runs": 0, "legal_ball": True, "wicket": True}
        },
        "draw_allowed": True,
        "overtime": {"policy": "super_over"},
        "tie_break_order": DEFAULT_TIE_BREAK,
        "roster_config": {
            "min_squad_size": 11, "max_squad_size": 18,
            "required_positions": {"wicketkeeper": 1}
        }
    },
    {
        "sport_id": "esports",
        "name": "Esports",
        "scoring_model": "round",
        "periods": {"best_of": 3},
        "scoring_events": {"round_win": {"rounds": 1}},
        "draw_allowed": False,
        "overtime": {"policy": "none"},
        "tie_break_order": DEFAULT_TIE_BREAK,
        "roster_config": {
            "min_squad_size": 5, "max_squad_size": 8,
            "required_positions": {}
        }
    }
]


async def wipe_all(db: AsyncSession):
    """Delete all data in reverse dependency order."""
    tables = [
        "offline_sync_records", "roster_audits", "players", "squads",
        "roster_leagues", "match_events", "matches", "orders",
        "product_variants", "products", "discount_codes",
        "leagues", "clubs", "users", "sports", "tenants", "app_state"
    ]
    for table in tables:
        await db.execute(text(f"DELETE FROM {table}"))
    await db.commit()


async def seed_baseline(db: AsyncSession, seed: int = 42, stock: dict = None):
    """Seed all baseline data. Idempotent after wipe_all."""
    if stock is None:
        stock = {"var-jersey-001-M": 1, "var-jersey-001-L": 5}

    # Sports
    for s in SPORTS_SEED:
        sport = Sport(
            sport_id=s["sport_id"],
            name=s["name"],
            scoring_model=s["scoring_model"],
            periods=s["periods"],
            scoring_events=s["scoring_events"],
            draw_allowed=s["draw_allowed"],
            overtime=s["overtime"],
            tie_break_order=s["tie_break_order"],
            roster_config=s["roster_config"]
        )
        db.add(sport)

    # Tenants
    db.add(Tenant(tenant_id="tenant-alpha", name="Alpha Sports"))
    db.add(Tenant(tenant_id="tenant-beta", name="Beta Athletics"))

    # Clubs
    db.add(Club(club_id="club-alpha-1", tenant_id="tenant-alpha", name="Alpha Club 1"))
    db.add(Club(club_id="club-alpha-2", tenant_id="tenant-alpha", name="Alpha Club 2"))
    db.add(Club(club_id="club-beta-1", tenant_id="tenant-beta", name="Beta Club 1"))

    # Leagues (RBAC scenario)
    db.add(League(
        league_id="league-alpha-1", tenant_id="tenant-alpha", sport_id="football",
        teams=[], points_win=3, points_draw=1, points_loss=0,
        tie_break_order=DEFAULT_TIE_BREAK, qualification_spots=2, lots_seed=seed
    ))
    db.add(League(
        league_id="league-alpha-2", tenant_id="tenant-alpha", sport_id="football",
        teams=[], points_win=3, points_draw=1, points_loss=0,
        tie_break_order=DEFAULT_TIE_BREAK, qualification_spots=2, lots_seed=seed
    ))
    db.add(League(
        league_id="league-beta-1", tenant_id="tenant-beta", sport_id="football",
        teams=[], points_win=3, points_draw=1, points_loss=0,
        tie_break_order=DEFAULT_TIE_BREAK, qualification_spots=2, lots_seed=seed
    ))

    # Users (5 demo accounts)
    pw = _hash_password("Nascon@26")
    db.add(User(user_id="user-super-admin", email="admin@nascon.test", password_hash=pw,
                role="super_admin", tenant_id=None))
    db.add(User(user_id="user-organizer", email="organizer@nascon.test", password_hash=pw,
                role="league_organizer", tenant_id="tenant-alpha", owns_league_id="league-alpha-1"))
    db.add(User(user_id="user-manager", email="manager@nascon.test", password_hash=pw,
                role="club_manager", tenant_id="tenant-alpha", owns_club_id="club-alpha-1"))
    db.add(User(user_id="user-player", email="player@nascon.test", password_hash=pw,
                role="player", tenant_id="tenant-alpha", player_id="player-alpha-1"))
    db.add(User(user_id="user-viewer", email="viewer@nascon.test", password_hash=pw,
                role="viewer", tenant_id="tenant-alpha"))

    # Players (RBAC scenario)
    db.add(Player(player_id="player-alpha-1", name="Alpha Player 1", position="gk",
                  league_id="league-alpha-1", current_squad_id="club-alpha-1",
                  role="starter", registration_type="transfer"))
    db.add(Player(player_id="player-alpha-2", name="Alpha Player 2", position="fw",
                  league_id="league-alpha-2", current_squad_id="club-alpha-2",
                  role="starter", registration_type="transfer"))
    db.add(Player(player_id="player-beta-1", name="Beta Player 1", position="mf",
                  league_id="league-beta-1", current_squad_id="club-beta-1",
                  role="starter", registration_type="transfer"))

    # Store
    db.add(Product(product_id="prod-jersey-001", tenant_id="tenant-alpha",
                   name="Alpha Jersey", category="apparel"))
    db.add(ProductVariant(
        variant_id="var-jersey-001-M", product_id="prod-jersey-001",
        size="M", price_minor=450000, currency="PKR",
        stock=stock.get("var-jersey-001-M", 1)
    ))
    db.add(ProductVariant(
        variant_id="var-jersey-001-L", product_id="prod-jersey-001",
        size="L", price_minor=450000, currency="PKR",
        stock=stock.get("var-jersey-001-L", 5)
    ))
    db.add(DiscountCode(code="WELCOME10", discount_percent=10))

    # App state
    db.add(AppState(key="lots_seed", value=str(seed)))

    await db.commit()
