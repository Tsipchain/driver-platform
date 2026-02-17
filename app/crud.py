from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import func, case
from sqlalchemy.orm import Session

from . import models, schemas


# Drivers --------------------------------------------------------------------


def create_driver(db: Session, driver: schemas.DriverCreate) -> models.Driver:
    obj = models.Driver(
        name=driver.name,
        phone=driver.phone,
        taxi_company=driver.taxi_company,
        plate_number=driver.plate_number,
        notes=driver.notes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_drivers(db: Session) -> List[models.Driver]:
    return db.query(models.Driver).order_by(models.Driver.id.desc()).all()


def get_driver(db: Session, driver_id: int) -> Optional[models.Driver]:
    return db.query(models.Driver).filter(models.Driver.id == driver_id).first()


# Trips ----------------------------------------------------------------------


def start_trip(db: Session, req: schemas.TripStartRequest) -> models.Trip:
    trip = models.Trip(
        driver_id=req.driver_id,
        origin=req.origin,
        destination=req.destination,
        notes=req.notes,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def finish_trip(db: Session, trip_id: int, req: schemas.TripFinishRequest) -> Optional[models.Trip]:
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
    if not trip:
        return None
    from datetime import datetime

    trip.finished_at = datetime.utcnow()
    if req.distance_km is not None:
        trip.distance_km = req.distance_km
    if req.avg_speed_kmh is not None:
        trip.avg_speed_kmh = req.avg_speed_kmh
    if req.safety_score is not None:
        trip.safety_score = req.safety_score
    if req.notes:
        trip.notes = (trip.notes or "") + f"\n{req.notes}"
    db.commit()
    db.refresh(trip)
    return trip


# Telemetry ------------------------------------------------------------------


def create_telemetry(db: Session, req: schemas.TelemetryCreate) -> models.TelemetryEvent:
    ev = models.TelemetryEvent(
        driver_id=req.driver_id,
        trip_id=req.trip_id,
        latitude=req.latitude,
        longitude=req.longitude,
        speed_kmh=req.speed_kmh,
        accel=req.accel,
        brake_hard=req.brake_hard,
        accel_hard=req.accel_hard,
        cornering_hard=req.cornering_hard,
        road_type=req.road_type,
        weather=req.weather,
        raw_notes=req.raw_notes,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_telemetry_for_driver(
    db: Session,
    driver_id: int,
    limit: int = 100,
) -> List[models.TelemetryEvent]:
    q = (
        db.query(models.TelemetryEvent)
        .filter(models.TelemetryEvent.driver_id == driver_id)
        .order_by(models.TelemetryEvent.ts.desc())
        .limit(limit)
    )
    return list(q)


# Voice events ---------------------------------------------------------------


def create_voice_event(db: Session, req: schemas.VoiceEventCreate) -> models.VoiceEvent:
    ev = models.VoiceEvent(
        driver_id=req.driver_id,
        trip_id=req.trip_id,
        transcript=req.transcript,
        intent_hint=req.intent_hint,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_voice_events_for_driver(
    db: Session,
    driver_id: int,
    limit: int = 100,
) -> List[models.VoiceEvent]:
    q = (
        db.query(models.VoiceEvent)
        .filter(models.VoiceEvent.driver_id == driver_id)
        .order_by(models.VoiceEvent.ts.desc())
        .limit(limit)
    )
    return list(q)


# Scoring --------------------------------------------------------------------


def compute_driver_score(db: Session, driver_id: int) -> Tuple[int, int, int, float, Optional[float], float]:
    """Return (total_trips, total_events, harsh_events, harsh_ratio, avg_speed, score_0_100)."""
    total_trips = db.query(models.Trip).filter(models.Trip.driver_id == driver_id).count()

    total_events, harsh_events, avg_speed = db.query(
        func.count(models.TelemetryEvent.id),
        func.sum(
            case(
                (
                    models.TelemetryEvent.brake_hard
                    | models.TelemetryEvent.accel_hard
                    | models.TelemetryEvent.cornering_hard,
                    1,
                ),
                else_=0,
            )
        ),
        func.avg(models.TelemetryEvent.speed_kmh),
    ).filter(models.TelemetryEvent.driver_id == driver_id).one()

    total_events = total_events or 0
    harsh_events = int(harsh_events or 0)
    avg_speed = float(avg_speed) if avg_speed is not None else None

    harsh_ratio = float(harsh_events) / float(total_events) if total_events > 0 else 0.0

    # Simple heuristic: start from 100, subtract penalty for harsh ratio and overspeeding
    score = 100.0
    score -= harsh_ratio * 40.0  # up to -40 points
    if avg_speed is not None and avg_speed > 55:
        score -= min((avg_speed - 55.0) * 0.5, 30.0)  # up to -30 for high average speed

    if score < 0:
        score = 0.0
    if score > 100:
        score = 100.0

    return total_trips, total_events, harsh_events, harsh_ratio, avg_speed, score
