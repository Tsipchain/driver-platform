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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    driver = relationship("Driver")
    trip = relationship("Trip")
