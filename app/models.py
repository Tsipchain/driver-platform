from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    name = Column(String(120), nullable=True)
    role = Column(String(32), nullable=False, default="taxi")
    is_verified = Column(Integer, nullable=False, default=0)
    wallet_address = Column(String(255), nullable=True)
    company_token_symbol = Column(String(32), nullable=True)
    verification_code = Column(String(16), nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    verification_channel = Column(String(16), nullable=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_code_sent_at = Column(DateTime, nullable=True)

    taxi_company = Column(String(128), nullable=True)
    plate_number = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)
    company_name = Column(String(128), nullable=True)
    group_tag = Column(String(64), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    approved = Column(Boolean, nullable=False, default=False)

    trips = relationship("Trip", back_populates="driver", cascade="all, delete-orphan")
    telemetry_events = relationship("TelemetryEvent", back_populates="driver", cascade="all, delete-orphan")
    voice_events = relationship("VoiceEvent", back_populates="driver", cascade="all, delete-orphan")
    sessions = relationship("SessionToken", back_populates="driver", cascade="all, delete-orphan")


class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    driver = relationship("Driver", back_populates="sessions")


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    origin = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    distance_km = Column(Float, nullable=True)
    avg_speed_kmh = Column(Float, nullable=True)
    safety_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    company_name = Column(String(128), nullable=True)
    group_tag = Column(String(64), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    reward_points = Column(Float, nullable=True)

    driver = relationship("Driver", back_populates="trips")
    telemetry_events = relationship("TelemetryEvent", back_populates="trip", cascade="all, delete-orphan")


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)

    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    accel = Column(Float, nullable=True)
    brake_hard = Column(Boolean, default=False, nullable=False)
    accel_hard = Column(Boolean, default=False, nullable=False)
    cornering_hard = Column(Boolean, default=False, nullable=False)
    road_type = Column(String(64), nullable=True)
    weather = Column(String(64), nullable=True)
    raw_notes = Column(Text, nullable=True)

    driver = relationship("Driver", back_populates="telemetry_events")
    trip = relationship("Trip", back_populates="telemetry_events")


class VoiceEvent(Base):
    __tablename__ = "voice_events"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)

    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    transcript = Column(Text, nullable=False)
    intent_hint = Column(String(64), nullable=True)

    driver = relationship("Driver", back_populates="voice_events")
    trip = relationship("Trip")


class VoiceMessage(Base):
    __tablename__ = "voice_messages"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)
    file_path = Column(String(512), nullable=False)
    duration_sec = Column(Float, nullable=True)
    target = Column(String(64), nullable=True)
    note = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="received")
    direction = Column(String(16), nullable=False, default="up")
    in_reply_to = Column(Integer, nullable=True)
    read_at = Column(DateTime, nullable=True)
    group_tag = Column(String(64), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    driver = relationship("Driver")
    trip = relationship("Trip")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(128), nullable=False, unique=True, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    cert_type = Column(String(64), nullable=False)
    cert_ref = Column(String(128), nullable=True)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    driver = relationship("Driver")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    type = Column(String(32), nullable=False, default="taxi")
    status = Column(String(32), nullable=False, default="pending")
    default_group_tag = Column(String(64), nullable=True, index=True)
    title = Column(String(128), nullable=True)
    logo_url = Column(String(512), nullable=True)
    favicon_url = Column(String(512), nullable=True)
    token_symbol = Column(String(32), nullable=True)
    treasury_wallet = Column(String(255), nullable=True)
    reward_policy_json = Column(Text, nullable=True)
    plan = Column(String(32), nullable=False, default="basic")
    plan_status = Column(String(32), nullable=False, default="trialing")
    trial_ends_at = Column(DateTime, nullable=True)
    addons_json = Column(Text, nullable=True)
    billing_name = Column(String(128), nullable=True)
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(Text, nullable=True)
    billing_country = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False, index=True)
    role = Column(String(32), nullable=False, default="driver")
    approved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OrganizationRequest(Base):
    __tablename__ = "organization_requests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    slug = Column(String(128), nullable=False, unique=True, index=True)
    city = Column(String(128), nullable=True)
    contact_email = Column(String(255), nullable=True)
    type = Column(String(32), nullable=False, default="taxi")
    status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TenantBranding(Base):
    __tablename__ = "tenant_branding"

    id = Column(Integer, primary_key=True, index=True)
    group_tag = Column(String(64), nullable=False, unique=True, index=True)
    app_name = Column(String(128), nullable=True)
    logo_url = Column(String(512), nullable=True)
    favicon_url = Column(String(512), nullable=True)
    primary_color = Column(String(32), nullable=True)
    plan = Column(String(32), nullable=False, default="basic")
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OperatorToken(Base):
    __tablename__ = "operator_tokens"

    id = Column(Integer, primary_key=True, index=True)
    group_tag = Column(String(64), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    role = Column(String(32), nullable=False, default="operator")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class TrialAttempt(Base):
    __tablename__ = "trial_attempts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_hash = Column(String(128), nullable=False, index=True)
    email_hash = Column(String(128), nullable=False, index=True)
    phone_hash = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False)
    retry_after = Column(Integer, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    error_code = Column(String(64), nullable=True)


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    provider_event_id = Column(String(128), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False)
    thronos_tx_id = Column(String(128), nullable=True)
    block_height = Column(Integer, nullable=True)
    confirmations = Column(Integer, nullable=False, default=0)

