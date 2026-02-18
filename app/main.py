import logging
import os
import re
import secrets
import smtplib
from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .db import SessionLocal, init_db
from .models import Driver

logger = logging.getLogger(__name__)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_phone(phone: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", phone or "")
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) == 10 and cleaned.isdigit():
        return f"+30{cleaned[1:]}"
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.isdigit() and len(cleaned) == 9:
        return f"+30{cleaned}"
    return cleaned


def mask_value(email: Optional[str], phone: str) -> str:
    if email:
        parts = email.split("@")
        if len(parts) == 2 and parts[0]:
            return f"{parts[0][0]}***@{parts[1]}"
    if len(phone) >= 4:
        return f"***{phone[-4:]}"
    return "***"


def is_production_env() -> bool:
    return (os.getenv("DRIVER_ENV") or "").strip().lower() == "production"


def generate_otp_code() -> str:
    fixed = os.getenv("DRIVER_DEV_FIXED_OTP")
    if fixed:
        fixed_clean = fixed.strip()
        if len(fixed_clean) == 6 and fixed_clean.isdigit():
            return fixed_clean
        logger.warning("DRIVER_DEV_FIXED_OTP is set but invalid; expected 6 digits")

    return str(secrets.randbelow(900000) + 100000)


def _smtp_enabled() -> bool:
    return (os.getenv("DRIVER_SMTP_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}


def _smtp_configured() -> bool:
    required = [
        "DRIVER_SMTP_HOST",
        "DRIVER_SMTP_PORT",
        "DRIVER_SMTP_USER",
        "DRIVER_SMTP_PASSWORD",
        "DRIVER_SMTP_FROM",
    ]
    return all((os.getenv(key) or "").strip() for key in required)


def send_code_via_email(email: str, code: str, name_or_phone: str) -> bool:
    if not email or not _smtp_enabled() or not _smtp_configured():
        return False

    smtp_host = (os.getenv("DRIVER_SMTP_HOST") or "").strip()
    smtp_port = int((os.getenv("DRIVER_SMTP_PORT") or "465").strip())
    smtp_user = (os.getenv("DRIVER_SMTP_USER") or "").strip()
    smtp_password = os.getenv("DRIVER_SMTP_PASSWORD") or ""
    smtp_from = (os.getenv("DRIVER_SMTP_FROM") or "").strip()
    smtp_timeout = int((os.getenv("DRIVER_SMTP_TIMEOUT") or "10").strip())

    msg = EmailMessage()
    msg["Subject"] = "[Thronos Driver] Κωδικός σύνδεσης / Login code"
    msg["From"] = smtp_from
    msg["To"] = email
    msg.set_content(
        f"""Γεια σου {name_or_phone},

Ο κωδικός σύνδεσης για την πλατφόρμα Thronos Driver είναι:

    {code}

Ο κωδικός ισχύει μόνο για λίγα λεπτά και μπορεί να χρησιμοποιηθεί μία φορά
για να συνδεθείς από αυτή τη συσκευή.

Αν δεν ζήτησες εσύ αυτόν τον κωδικό, μπορείς να αγνοήσεις αυτό το μήνυμα.


Hi {name_or_phone},

Your login code for the Thronos Driver platform is:

    {code}

This code is valid only for a few minutes and can be used once to sign in
from this device.

If you did not request this code, you can safely ignore this email.

— Thronos Driver
"""
    )

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=smtp_timeout) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info("OTP email sent to %s", email)
        return True
    except Exception:
        logger.exception("Failed to send OTP email to %s", email)
        return False


def get_current_driver(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Driver:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.split(" ", 1)[1].strip()
    session = crud.get_session_by_token(db, token)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized")

    driver = crud.get_driver(db, session.driver_id)
    if not driver:
        raise HTTPException(status_code=401, detail="Unauthorized")

    crud.touch_session(db, session)
    return driver


def get_current_driver_optional(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[Driver]:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None
    session = crud.get_session_by_token(db, token)
    if not session:
        return None
    driver = crud.get_driver(db, session.driver_id)
    if not driver:
        return None
    crud.touch_session(db, session)
    return driver


def _get_admin_token() -> str:
    return (os.getenv("X_ADMIN_TOKEN") or os.getenv("DRIVER_ADMIN_TOKEN") or "").strip()


def require_admin_token(x_admin_token: Optional[str] = Header(default=None)) -> None:
    configured = _get_admin_token()
    if not configured or x_admin_token != configured:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _voice_storage_base() -> Path:
    return Path("/app/data/voice")


def _parse_multipart_voice_payload(raw_body: bytes, content_type: str) -> tuple[bytes, str, Optional[int], Optional[str], Optional[str]]:
    boundary_marker = "boundary="
    if boundary_marker not in content_type:
        raise HTTPException(status_code=400, detail="Invalid multipart payload")

    boundary = content_type.split(boundary_marker, 1)[1].strip()
    if boundary.startswith('"') and boundary.endswith('"'):
        boundary = boundary[1:-1]

    delimiter = ("--" + boundary).encode()
    file_bytes = b""
    filename = "voice.webm"
    trip_id: Optional[int] = None
    note: Optional[str] = None
    target: Optional[str] = "cb"

    for part in raw_body.split(delimiter):
        part = part.strip()
        if not part or part in {b"--", b"--\r\n"}:
            continue
        if b"\r\n\r\n" not in part:
            continue
        headers_raw, data = part.split(b"\r\n\r\n", 1)
        headers_text = headers_raw.decode("utf-8", errors="ignore")
        value = data.rstrip(b"\r\n")

        if 'name="file"' in headers_text:
            file_bytes = value
            if 'filename="' in headers_text:
                filename = headers_text.split('filename="', 1)[1].split('"', 1)[0] or filename
        elif 'name="trip_id"' in headers_text:
            txt = value.decode("utf-8", errors="ignore").strip()
            if txt:
                trip_id = int(txt)
        elif 'name="note"' in headers_text:
            note = value.decode("utf-8", errors="ignore").strip() or None
        elif 'name="target"' in headers_text:
            target = value.decode("utf-8", errors="ignore").strip() or "cb"

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Missing file part")

    return file_bytes, filename, trip_id, note, target




init_db()

app = FastAPI(title="Thronos Driver Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@app.get("/health")
def health():
    return {"status": "ok"}


@auth_router.post("/request-code")
def request_code(req: schemas.AuthRequestCode, db: Session = Depends(get_db)):
    phone = normalize_phone(req.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Invalid phone")

    driver = crud.get_or_create_driver_by_phone(db, phone=phone, email=req.email, name=req.name, role=req.role)
    now = datetime.utcnow()
    cooldown_seconds = 120

    if driver.last_code_sent_at:
        elapsed = (now - driver.last_code_sent_at).total_seconds()
        if elapsed < cooldown_seconds:
            retry_after = max(1, int(cooldown_seconds - elapsed))
            return JSONResponse(status_code=429, content={"error": "CODE_TOO_SOON", "retry_after": retry_after})

    code = generate_otp_code()
    driver.verification_code = code
    driver.verification_expires_at = now + timedelta(minutes=10)
    driver.last_code_sent_at = now
    driver.failed_attempts = 0

    delivery = "log"
    channel = "sms"
    recipient_name = (req.name or driver.name or phone).strip()

    if req.email and _smtp_enabled() and _smtp_configured():
        if send_code_via_email(req.email, code, recipient_name):
            delivery = "email"
            channel = "email"
        else:
            logger.warning("OTP delivery fell back to log-only mode for %s", req.email)
    elif req.email and (not _smtp_enabled() or not _smtp_configured()):
        logger.warning("SMTP disabled or incomplete; falling back to log-only OTP mode for %s", req.email)

    if delivery == "log":
        if is_production_env():
            logger.warning("OTP created in log-only mode for phone=%s", phone)
        else:
            logger.info("[DEV] login code for %s is %s", phone, code)

    driver.verification_channel = channel
    db.commit()

    return {"ok": True, "delivery": delivery, "masked": mask_value(req.email, phone)}


@auth_router.post("/verify-code")
def verify_code(req: schemas.AuthVerifyCode, db: Session = Depends(get_db)):
    phone = normalize_phone(req.phone)
    driver = crud.get_driver_by_phone(db, phone)
    now = datetime.utcnow()

    if not driver:
        raise HTTPException(status_code=401, detail="Invalid verification request")

    if (
        not driver.verification_code
        or req.code != driver.verification_code
        or not driver.verification_expires_at
        or driver.verification_expires_at < now
    ):
        driver.failed_attempts = (driver.failed_attempts or 0) + 1
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid verification request")

    driver.is_verified = 1
    driver.verification_code = None
    driver.verification_expires_at = None
    driver.failed_attempts = 0
    driver.last_login_at = now
    db.commit()

    token = secrets.token_hex(32)
    crud.create_session_token(db, driver_id=driver.id, token=token)
    return {
        "ok": True,
        "driver": {"id": driver.id, "name": driver.name, "role": driver.role, "phone": driver.phone},
        "session_token": token,
    }


@app.get("/api/me")
def me(current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return {
        "id": current_driver.id,
        "phone": current_driver.phone,
        "name": current_driver.name,
        "role": current_driver.role,
        "email": current_driver.email,
        "wallet_address": current_driver.wallet_address,
        "company_token_symbol": current_driver.company_token_symbol,
        "stats": {
            "trips": crud.count_driver_trips(db, current_driver.id),
            "telemetry": crud.count_driver_telemetry(db, current_driver.id),
        },
    }


@app.post("/api/me")
def me_update(req: schemas.MeUpdateRequest, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    if req.name is not None:
        current_driver.name = req.name.strip() or None
        db.commit()
    return {"ok": True, "name": current_driver.name}


@app.post("/api/wallet/link")
def wallet_link(
    req: schemas.WalletLinkRequest,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    wallet = req.wallet_address.strip()
    if not wallet or len(wallet) < 6 or len(wallet) > 128:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    if wallet.upper().startswith("THR") is False and not wallet.startswith("0x"):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    target_driver = current_driver
    if not target_driver and req.driver_id:
        target_driver = crud.get_driver(db, req.driver_id)

    if not target_driver:
        raise HTTPException(status_code=401, detail="Unauthorized")

    target_driver.wallet_address = wallet
    target_driver.company_token_symbol = req.company_token_symbol.strip() if req.company_token_symbol else None
    db.commit()
    return {"ok": True}


@app.get("/api/wallet")
def wallet_get(
    driver_id: Optional[int] = None,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    target_driver = current_driver
    if not target_driver and driver_id:
        target_driver = crud.get_driver(db, driver_id)
    if not target_driver:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "wallet_address": target_driver.wallet_address,
        "company_token_symbol": target_driver.company_token_symbol,
    }


@app.post("/api/v1/voice-messages", response_model=schemas.VoiceMessageRead)
async def api_create_voice_message(
    request: Request,
    current_driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    raw_body = await request.body()
    file_bytes, incoming_filename, trip_id, note, target = _parse_multipart_voice_payload(raw_body, content_type)

    now = datetime.utcnow()
    ts = now.strftime("%Y%m%d%H%M%S%f")
    suffix = Path(incoming_filename).suffix or ".webm"
    driver_dir = _voice_storage_base() / str(current_driver.id)
    driver_dir.mkdir(parents=True, exist_ok=True)
    absolute_path = driver_dir / f"{ts}{suffix}"
    absolute_path.write_bytes(file_bytes)

    msg = crud.create_voice_message(
        db,
        driver_id=current_driver.id,
        trip_id=trip_id,
        file_path=str(absolute_path),
        duration_sec=None,
        target=target,
        note=note,
        status="received",
    )
    return msg


@app.get("/api/v1/voice-messages/recent")
def api_recent_voice_messages(
    limit: int = Query(default=20, ge=1, le=200),
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    rows = crud.list_recent_voice_messages(db, limit=limit)
    out = []
    for row in rows:
        drv = crud.get_driver(db, row.driver_id)
        out.append(
            {
                "id": row.id,
                "driver": {
                    "id": drv.id if drv else None,
                    "name": drv.name if drv else None,
                    "phone": drv.phone if drv else None,
                    "group_tag": drv.group_tag if drv else None,
                },
                "trip_id": row.trip_id,
                "file_path": row.file_path,
                "duration_sec": row.duration_sec,
                "target": row.target,
                "status": row.status,
                "created_at": row.created_at,
            }
        )
    return {"items": out}


@app.get("/api/operator/dashboard")
def api_operator_dashboard(
    group_tag: Optional[str] = None,
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return crud.get_operator_dashboard(db, group_tag=group_tag)


@app.get("/api/operator/events/recent")
def api_operator_recent_events(
    group_tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    _: None = Depends(require_admin_token),
    db: Session = Depends(get_db),
):
    return {"events": crud.get_recent_operator_events(db, group_tag=group_tag, limit=limit)}




app.include_router(auth_router)


@app.get("/api/v1/drivers", response_model=List[schemas.DriverRead])
def api_list_drivers(db: Session = Depends(get_db)):
    return crud.list_drivers(db)


@app.post("/api/v1/drivers", response_model=schemas.DriverRead)
def api_create_driver(driver: schemas.DriverCreate, db: Session = Depends(get_db)):
    driver.phone = normalize_phone(driver.phone)
    return crud.create_driver(db, driver)


@app.post("/api/v1/trips/start", response_model=schemas.TripRead)
def api_start_trip(
    req: schemas.TripStartRequest,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    resolved_driver_id = current_driver.id if current_driver else req.driver_id
    if not resolved_driver_id or not crud.get_driver(db, int(resolved_driver_id)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return crud.start_trip(db, req, driver_id=int(resolved_driver_id))


@app.post("/api/v1/trips/{trip_id}/finish", response_model=schemas.TripRead)
def api_finish_trip(
    trip_id: int,
    req: schemas.TripFinishRequest,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    if current_driver:
        driver_id = current_driver.id
    else:
        trip = db.query(models.Trip).filter(models.Trip.id == trip_id).first()
        if not trip:
            raise HTTPException(status_code=404, detail="Trip not found")
        driver_id = trip.driver_id

    trip = crud.finish_trip(db, trip_id, req, driver_id=driver_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.post("/api/v1/telemetry", response_model=schemas.TelemetryRead)
def api_create_telemetry(
    req: schemas.TelemetryCreate,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    resolved_driver_id = current_driver.id if current_driver else req.driver_id
    if not resolved_driver_id or not crud.get_driver(db, int(resolved_driver_id)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return crud.create_telemetry(db, req, driver_id=int(resolved_driver_id))


@app.get("/api/v1/telemetry", response_model=List[schemas.TelemetryRead])
def api_list_telemetry(
    driver_id: Optional[int] = None,
    limit: int = 100,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    resolved_driver_id = current_driver.id if current_driver else driver_id
    if not resolved_driver_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return crud.list_telemetry_for_driver(db, driver_id=resolved_driver_id, limit=min(limit, 500))


@app.post("/api/v1/voice-events", response_model=schemas.VoiceEventRead)
def api_create_voice_event(
    req: schemas.VoiceEventCreate,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    resolved_driver_id = current_driver.id if current_driver else req.driver_id
    if not resolved_driver_id or not crud.get_driver(db, int(resolved_driver_id)):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return crud.create_voice_event(db, req, driver_id=int(resolved_driver_id))


@app.get("/api/v1/voice-events", response_model=List[schemas.VoiceEventRead])
def api_list_voice_events(
    driver_id: Optional[int] = None,
    limit: int = 100,
    current_driver: Optional[Driver] = Depends(get_current_driver_optional),
    db: Session = Depends(get_db),
):
    resolved_driver_id = current_driver.id if current_driver else driver_id
    if not resolved_driver_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return crud.list_voice_events_for_driver(db, driver_id=resolved_driver_id, limit=min(limit, 500))


@app.get("/api/v1/score/driver/{driver_id}", response_model=schemas.DriverScore)
def api_driver_score(driver_id: int, db: Session = Depends(get_db)):
    if not crud.get_driver(db, driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    total_trips, total_events, harsh_events, harsh_ratio, avg_speed, score = crud.compute_driver_score(db, driver_id)
    return schemas.DriverScore(
        driver_id=driver_id,
        total_trips=total_trips,
        total_events=total_events,
        harsh_events=harsh_events,
        harsh_ratio=harsh_ratio,
        avg_speed_kmh=avg_speed,
        score_0_100=score,
    )


@app.get("/operator")
def operator_page():
    index_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    return FileResponse(index_file)


@app.get("/school")
def school_page():
    index_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    return FileResponse(index_file)


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
