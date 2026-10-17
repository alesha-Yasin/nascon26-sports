"""
All SQLAlchemy ORM models for the sports platform.
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, ForeignKey,
    JSON, UniqueConstraint, BigInteger, Numeric
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ─── Sports ───────────────────────────────────────────────────────────────────

class Sport(Base):
    __tablename__ = "sports"

    sport_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    scoring_model: Mapped[str] = mapped_column(String(20))  # event, innings, round
    periods: Mapped[dict] = mapped_column(JSON)
    scoring_events: Mapped[dict] = mapped_column(JSON)
    draw_allowed: Mapped[bool] = mapped_column(Boolean)
    overtime: Mapped[dict] = mapped_column(JSON)
    tie_break_order: Mapped[list] = mapped_column(JSON)
    roster_config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Tenants ──────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


# ─── Leagues ──────────────────────────────────────────────────────────────────

class League(Base):
    __tablename__ = "leagues"

    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"))
    sport_id: Mapped[str] = mapped_column(String(40), ForeignKey("sports.sport_id"))
    teams: Mapped[list] = mapped_column(JSON)  # list of team_ids
    points_win: Mapped[int] = mapped_column(Integer, default=3)
    points_draw: Mapped[int] = mapped_column(Integer, default=1)
    points_loss: Mapped[int] = mapped_column(Integer, default=0)
    tie_break_order: Mapped[list] = mapped_column(JSON)
    qualification_spots: Mapped[int] = mapped_column(Integer, default=2)
    lots_seed: Mapped[int] = mapped_column(Integer, default=42)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Matches ──────────────────────────────────────────────────────────────────

class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sport_id: Mapped[str] = mapped_column(String(40), ForeignKey("sports.sport_id"))
    league_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("leagues.league_id"), nullable=True)
    home_team_id: Mapped[str] = mapped_column(String(64))
    away_team_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Match Events (append-only log) ───────────────────────────────────────────

class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    match_id: Mapped[str] = mapped_column(String(64), ForeignKey("matches.match_id"), index=True)
    type: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    sequence: Mapped[int] = mapped_column(Integer)
    match_version: Mapped[int] = mapped_column(Integer)
    signature: Mapped[str] = mapped_column(String(64))
    compensated: Mapped[bool] = mapped_column(Boolean, default=False)
    compensated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))  # super_admin, league_organizer, club_manager, player, viewer
    tenant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owns_league_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    owns_club_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    player_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Clubs ────────────────────────────────────────────────────────────────────

class Club(Base):
    __tablename__ = "clubs"

    club_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("tenants.tenant_id"))
    name: Mapped[str] = mapped_column(String(200))
    venue_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    venue_lon: Mapped[Optional[float]] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Roster / Players ─────────────────────────────────────────────────────────

class RosterLeague(Base):
    """Roster configuration for a league."""
    __tablename__ = "roster_leagues"

    league_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    sport_id: Mapped[str] = mapped_column(String(40))
    transfer_window_open: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    transfer_window_close: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    max_squad_size: Mapped[int] = mapped_column(Integer)
    required_positions: Mapped[dict] = mapped_column(JSON)
    matches_in_progress: Mapped[list] = mapped_column(JSON, default=list)


class Squad(Base):
    __tablename__ = "squads"

    squad_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    league_id: Mapped[str] = mapped_column(String(64))
    club_id: Mapped[str] = mapped_column(String(64))
    tenant_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))


class Player(Base):
    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(64))
    league_id: Mapped[str] = mapped_column(String(64), index=True)
    current_squad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parent_squad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="substitute")
    registration_type: Mapped[str] = mapped_column(String(20), default="transfer")
    start_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    loan_end_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_released: Mapped[bool] = mapped_column(Boolean, default=False)
    on_loan: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("player_id", "league_id", name="uq_player_league"),)


class RosterAudit(Base):
    __tablename__ = "roster_audits"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    action: Mapped[str] = mapped_column(String(30))  # transfer, loan, release, loan_return
    player_id: Mapped[str] = mapped_column(String(64), index=True)
    league_id: Mapped[str] = mapped_column(String(64))
    from_squad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    to_squad_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[str] = mapped_column(String(10))
    state: Mapped[str] = mapped_column(String(30))  # active, deferred_until_match_end
    blocking_match_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    who: Mapped[str] = mapped_column(String(64))
    when_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    why: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stored_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# ─── Store / Merchandise ──────────────────────────────────────────────────────

class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))


class ProductVariant(Base):
    __tablename__ = "product_variants"

    variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("products.product_id"))
    size: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(5), default="PKR")
    stock: Mapped[int] = mapped_column(Integer, default=0)


class DiscountCode(Base):
    __tablename__ = "discount_codes"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    discount_percent: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    currency: Mapped[str] = mapped_column(String(5), default="PKR")
    subtotal_minor: Mapped[int] = mapped_column(BigInteger)
    discount_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    total_minor: Mapped[int] = mapped_column(BigInteger)
    items: Mapped[list] = mapped_column(JSON)
    payment_token: Mapped[str] = mapped_column(String(64))
    authorization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    capture_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payment_state: Mapped[str] = mapped_column(String(20), default="pending")
    receipt_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    receipt_signature: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    receipt_pdf_base64: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── App State (seed/reset tracking) ──────────────────────────────────────────

class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


# ─── Offline Sync ─────────────────────────────────────────────────────────────

class OfflineSyncRecord(Base):
    __tablename__ = "offline_sync_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    action_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))  # applied, rejected, duplicate
    resolution: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("device_id", "action_id", name="uq_device_action"),)
