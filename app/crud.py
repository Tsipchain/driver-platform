from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from . import models, schemas


def create_driver(db: Session, driver: schemas.DriverCreate) -> models.Driver:
    obj = models.Driver(
        name=driver.name,
        phone=driver.phone,
        email=driver.email,
        role=driver.role,
        taxi_company=driver.taxi_company,
        plate_number=driver.plate_number,
        notes=driver.notes,
        company_name=driver.company_name,
        group_tag=driver.group_tag,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_drivers(db: Session) -> List[models.Driver]:
    return db.query(models.Driver).order_by(models.Driver.id.desc()).all()


def get_driver(db: Session, driver_id: int) -> Optional[models.Driver]:
    return db.query(models.Driver).filter(models.Driver.id == driver_id).first()


def get_driver_by_phone(db: Session, phone: str) -> Optional[models.Driver]:
    return db.query(models.Driver).filter(models.Driver.phone == phone).first()


def get_or_create_driver_by_phone(
    db: Session,
    phone: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    role: Optional[str] = "taxi",
    group_tag: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> models.Driver:
    driver = get_driver_by_phone(db, phone)
    # Email-based dedup: if phone not found but email matches an existing driver, reuse it
    if not driver and email:
        driver = db.query(models.Driver).filter(models.Driver.email == email).first()
        if driver:
            driver.phone = phone  # update to new phone number
    if driver:
        if email and not driver.email:
            driver.email = email
        if name and not driver.name:
            driver.name = name
        if role:
            driver.role = role
        if email:
            driver.email = email
        if group_tag:
            driver.group_tag = group_tag
        if organization_id is not None:
            driver.organization_id = organization_id
        db.commit()
        db.refresh(driver)
        return driver

    driver = models.Driver(
        phone=phone,
        email=email,
        name=name,
        role=role or "taxi",
        created_at=datetime.utcnow(),
        group_tag=group_tag,
        approved=False,
        organization_id=organization_id,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def create_session_token(db: Session, driver_id: int, token: str) -> models.SessionToken:
    session = models.SessionToken(driver_id=driver_id, token=token, created_at=datetime.utcnow(), last_seen_at=datetime.utcnow())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_token(db: Session, token: str) -> Optional[models.SessionToken]:
    return db.query(models.SessionToken).filter(models.SessionToken.token == token).first()


def touch_session(db: Session, session: models.SessionToken) -> None:
    session.last_seen_at = datetime.utcnow()
    db.commit()


def start_trip(db: Session, req: schemas.TripStartRequest, driver_id: int) -> models.Trip:
    trip = models.Trip(driver_id=driver_id, origin=req.origin, destination=req.destination, notes=req.notes, assignment_id=req.assignment_id)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def finish_trip(db: Session, trip_id: int, req: schemas.TripFinishRequest, driver_id: int) -> Optional[models.Trip]:
    trip = db.query(models.Trip).filter(models.Trip.id == trip_id, models.Trip.driver_id == driver_id).first()
    if not trip:
        return None

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


def create_telemetry(db: Session, req: schemas.TelemetryCreate, driver_id: int) -> models.TelemetryEvent:
    ev = models.TelemetryEvent(
        driver_id=driver_id,
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


def list_telemetry_for_driver(db: Session, driver_id: int, limit: int = 100) -> List[models.TelemetryEvent]:
    q = (
        db.query(models.TelemetryEvent)
        .filter(models.TelemetryEvent.driver_id == driver_id)
        .order_by(models.TelemetryEvent.ts.desc())
        .limit(limit)
    )
    return list(q)


def create_voice_event(db: Session, req: schemas.VoiceEventCreate, driver_id: int) -> models.VoiceEvent:
    ev = models.VoiceEvent(driver_id=driver_id, trip_id=req.trip_id, transcript=req.transcript, intent_hint=req.intent_hint)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_voice_events_for_driver(db: Session, driver_id: int, limit: int = 100) -> List[models.VoiceEvent]:
    q = (
        db.query(models.VoiceEvent)
        .filter(models.VoiceEvent.driver_id == driver_id)
        .order_by(models.VoiceEvent.ts.desc())
        .limit(limit)
    )
    return list(q)


def count_driver_trips(db: Session, driver_id: int) -> int:
    return db.query(models.Trip).filter(models.Trip.driver_id == driver_id).count()


def count_driver_telemetry(db: Session, driver_id: int) -> int:
    return db.query(models.TelemetryEvent).filter(models.TelemetryEvent.driver_id == driver_id).count()


def compute_driver_score(db: Session, driver_id: int) -> Tuple[int, int, int, float, Optional[float], float]:
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

    score = 100.0
    score -= harsh_ratio * 40.0
    if avg_speed is not None and avg_speed > 55:
        score -= min((avg_speed - 55.0) * 0.5, 30.0)

    score = max(0.0, min(score, 100.0))
    return total_trips, total_events, harsh_events, harsh_ratio, avg_speed, score


def create_voice_message(
    db: Session,
    driver_id: int,
    file_path: str,
    trip_id: Optional[int] = None,
    duration_sec: Optional[float] = None,
    target: Optional[str] = None,
    note: Optional[str] = None,
    status: str = "received",
    group_tag: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> models.VoiceMessage:
    msg = models.VoiceMessage(
        driver_id=driver_id,
        trip_id=trip_id,
        file_path=file_path,
        duration_sec=duration_sec,
        target=target,
        note=note,
        status=status,
        created_at=datetime.utcnow(),
        group_tag=group_tag,
        approved=False,
        organization_id=organization_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def list_recent_voice_messages(db: Session, limit: int = 20) -> List[models.VoiceMessage]:
    return (
        db.query(models.VoiceMessage)
        .order_by(models.VoiceMessage.created_at.desc())
        .limit(limit)
        .all()
    )


def get_operator_dashboard(db: Session, group_tag: Optional[str] = None, organization_id: Optional[int] = None) -> dict:
    q = db.query(models.Driver)
    if organization_id:
        q = q.filter(models.Driver.organization_id == organization_id)
    elif group_tag:
        q = q.filter(models.Driver.group_tag == group_tag)
    drivers = q.order_by(models.Driver.id.desc()).all()

    items = []
    active_count = 0
    for d in drivers:
        last_trip = (
            db.query(models.Trip)
            .filter(models.Trip.driver_id == d.id)
            .order_by(models.Trip.started_at.desc())
            .first()
        )
        if not last_trip:
            last_trip_status = "none"
        elif last_trip.finished_at is None:
            last_trip_status = "active"
            active_count += 1
        else:
            last_trip_status = "completed"

        last_tel = (
            db.query(models.TelemetryEvent)
            .filter(models.TelemetryEvent.driver_id == d.id)
            .order_by(models.TelemetryEvent.ts.desc())
            .first()
        )
        last_event = None
        if last_tel and (last_tel.brake_hard or last_tel.accel_hard or last_tel.cornering_hard):
            flags = []
            if last_tel.brake_hard:
                flags.append("brake_hard")
            if last_tel.accel_hard:
                flags.append("accel_hard")
            if last_tel.cornering_hard:
                flags.append("cornering_hard")
            last_event = {"type": "telemetry_flag", "flags": flags, "timestamp": last_tel.ts}

        items.append(
            {
                "id": d.id,
                "name": d.name,
                "phone": d.phone,
                "company_name": d.company_name,
                "group_tag": d.group_tag,
                "approved": bool(d.approved),
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "last_login_at": d.last_login_at.isoformat() if d.last_login_at else None,
                "kyc_status": d.kyc_status,
                "last_trip_status": last_trip_status,
                "last_telemetry": (
                    {
                        "lat": last_tel.latitude,
                        "lng": last_tel.longitude,
                        "speed": last_tel.speed_kmh,
                        "timestamp": last_tel.ts,
                    }
                    if last_tel
                    else None
                ),
                "last_event": last_event,
            }
        )

    return {"active_drivers": active_count, "drivers": items}


def get_recent_operator_events(db: Session, group_tag: Optional[str] = None, limit: int = 50) -> List[dict]:
    q = db.query(models.TelemetryEvent, models.Driver).join(models.Driver, models.Driver.id == models.TelemetryEvent.driver_id)
    if group_tag:
        q = q.filter(models.Driver.group_tag == group_tag)
    q = q.filter(
        (models.TelemetryEvent.brake_hard == True)
        | (models.TelemetryEvent.accel_hard == True)
        | (models.TelemetryEvent.cornering_hard == True)
    )
    rows = q.order_by(models.TelemetryEvent.ts.desc()).limit(limit).all()

    events = []
    for tel, drv in rows:
        flags = []
        if tel.brake_hard:
            flags.append("brake_hard")
        if tel.accel_hard:
            flags.append("accel_hard")
        if tel.cornering_hard:
            flags.append("cornering_hard")
        events.append(
            {
                "driver_id": drv.id,
                "driver_name": drv.name,
                "group_tag": drv.group_tag,
                "trip_id": tel.trip_id,
                "flags": flags,
                "speed_kmh": tel.speed_kmh,
                "latitude": tel.latitude,
                "longitude": tel.longitude,
                "timestamp": tel.ts,
            }
        )
    return events


def revoke_session_token(db: Session, token: str) -> None:
    create_revoked_token(db, token)
    obj = db.query(models.SessionToken).filter(models.SessionToken.token == token).first()
    if obj:
        db.delete(obj)
        db.commit()


def create_revoked_token(db: Session, token: str) -> None:
    if not token:
        return
    existing = db.query(models.RevokedToken).filter(models.RevokedToken.token == token).first()
    if existing:
        return
    db.add(models.RevokedToken(token=token, revoked_at=datetime.utcnow()))
    db.commit()


def is_token_revoked(db: Session, token: str) -> bool:
    if not token:
        return False
    return db.query(models.RevokedToken).filter(models.RevokedToken.token == token).first() is not None


def list_organizations(db: Session, org_type: Optional[str] = None, status: Optional[str] = "active") -> List[models.Organization]:
    q = db.query(models.Organization)
    if org_type:
        q = q.filter(models.Organization.type == org_type)
    if status:
        q = q.filter(models.Organization.status == status)
    return q.order_by(models.Organization.name.asc()).all()


def get_organization(db: Session, organization_id: int) -> Optional[models.Organization]:
    return db.query(models.Organization).filter(models.Organization.id == organization_id).first()


def get_org_member(db: Session, organization_id: int, driver_id: int) -> Optional[models.OrganizationMember]:
    return db.query(models.OrganizationMember).filter(models.OrganizationMember.organization_id == organization_id, models.OrganizationMember.driver_id == driver_id).first()


def delete_driver(db: Session, driver_id: int) -> bool:
    driver = get_driver(db, driver_id)
    if not driver:
        return False
    # Delete related rows not covered by cascade
    db.query(models.OrganizationMember).filter(models.OrganizationMember.driver_id == driver_id).delete()
    db.query(models.AssignmentClaim).filter(models.AssignmentClaim.driver_id == driver_id).delete()
    db.query(models.RewardEvent).filter(models.RewardEvent.driver_id == driver_id).delete()
    db.delete(driver)
    db.commit()
    return True


def create_trial_attempt(
    db: Session,
    *,
    ip_hash: str,
    email_hash: str,
    phone_hash: Optional[str],
    status: str,
    retry_after: Optional[int] = None,
    organization_id: Optional[int] = None,
    error_code: Optional[str] = None,
) -> models.TrialAttempt:
    row = models.TrialAttempt(
        ip_hash=ip_hash,
        email_hash=email_hash,
        phone_hash=phone_hash,
        status=status,
        retry_after=retry_after,
        organization_id=organization_id,
        error_code=error_code,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def count_trial_attempts_since(
    db: Session,
    *,
    since: datetime,
    ip_hash: Optional[str] = None,
    email_hash: Optional[str] = None,
    phone_hash: Optional[str] = None,
    statuses: Optional[tuple[str, ...]] = None,
) -> int:
    q = db.query(models.TrialAttempt).filter(models.TrialAttempt.created_at >= since)
    if ip_hash is not None:
        q = q.filter(models.TrialAttempt.ip_hash == ip_hash)
    if email_hash is not None:
        q = q.filter(models.TrialAttempt.email_hash == email_hash)
    if phone_hash is not None:
        q = q.filter(models.TrialAttempt.phone_hash == phone_hash)
    if statuses:
        q = q.filter(models.TrialAttempt.status.in_(statuses))
    return q.count()


def _retry_after_for_window(
    db: Session,
    *,
    now: datetime,
    ip_hash: Optional[str] = None,
    email_hash: Optional[str] = None,
    phone_hash: Optional[str] = None,
    statuses: Optional[tuple[str, ...]] = None,
    window_sec: int,
) -> int:
    since = now - timedelta(seconds=window_sec)
    q = db.query(models.TrialAttempt).filter(models.TrialAttempt.created_at >= since)
    if ip_hash is not None:
        q = q.filter(models.TrialAttempt.ip_hash == ip_hash)
    if email_hash is not None:
        q = q.filter(models.TrialAttempt.email_hash == email_hash)
    if phone_hash is not None:
        q = q.filter(models.TrialAttempt.phone_hash == phone_hash)
    if statuses:
        q = q.filter(models.TrialAttempt.status.in_(statuses))
    oldest = q.order_by(models.TrialAttempt.created_at.asc()).first()
    if not oldest:
        return window_sec
    elapsed = int((now - oldest.created_at).total_seconds())
    return max(1, window_sec - elapsed)


def enforce_trial_rate_limit_db(
    db: Session,
    *,
    now: datetime,
    ip_hash: str,
    email_hash: str,
    phone_hash: Optional[str],
    short_window_sec: int,
    long_window_sec: int,
    max_ip_short: int,
    max_email_short: int,
    max_ip_email_short: int,
    max_phone_short: int,
    max_ip_long: int,
    max_email_long: int,
    max_phone_long: int,
) -> tuple[bool, int, str]:
    short_since = now - timedelta(seconds=short_window_sec)
    long_since = now - timedelta(seconds=long_window_sec)

    email_statuses = ("accepted", "created")

    checks = [
        {"count": count_trial_attempts_since(db, since=short_since, ip_hash=ip_hash), "limit": max_ip_short, "window": short_window_sec, "code": "RL_IP_SHORT", "filters": {"ip_hash": ip_hash}, "statuses": None},
        {"count": count_trial_attempts_since(db, since=short_since, email_hash=email_hash, statuses=email_statuses), "limit": max_email_short, "window": short_window_sec, "code": "RL_EMAIL_SHORT", "filters": {"email_hash": email_hash}, "statuses": email_statuses},
        {"count": count_trial_attempts_since(db, since=short_since, ip_hash=ip_hash, email_hash=email_hash), "limit": max_ip_email_short, "window": short_window_sec, "code": "RL_IP_EMAIL_SHORT", "filters": {"ip_hash": ip_hash, "email_hash": email_hash}, "statuses": None},
        {"count": count_trial_attempts_since(db, since=long_since, ip_hash=ip_hash), "limit": max_ip_long, "window": long_window_sec, "code": "RL_IP_LONG", "filters": {"ip_hash": ip_hash}, "statuses": None},
        {"count": count_trial_attempts_since(db, since=long_since, email_hash=email_hash, statuses=email_statuses), "limit": max_email_long, "window": long_window_sec, "code": "RL_EMAIL_LONG", "filters": {"email_hash": email_hash}, "statuses": email_statuses},
    ]
    if phone_hash:
        checks.extend([
            {"count": count_trial_attempts_since(db, since=short_since, phone_hash=phone_hash, statuses=email_statuses), "limit": max_phone_short, "window": short_window_sec, "code": "RL_PHONE_SHORT", "filters": {"phone_hash": phone_hash}, "statuses": email_statuses},
            {"count": count_trial_attempts_since(db, since=long_since, phone_hash=phone_hash, statuses=email_statuses), "limit": max_phone_long, "window": long_window_sec, "code": "RL_PHONE_LONG", "filters": {"phone_hash": phone_hash}, "statuses": email_statuses},
        ])

    for check in checks:
        if check["count"] >= check["limit"]:
            retry_after = _retry_after_for_window(
                db,
                now=now,
                window_sec=check["window"],
                statuses=check["statuses"],
                **check["filters"],
            )
            return False, retry_after, check["code"]
    return True, 0, ""
