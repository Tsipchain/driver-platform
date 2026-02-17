import logging
import os
import re
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import List, Optional

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, schemas
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


def _smtp_configured() -> bool:
    required = ["DRIVER_SMTP_HOST", "DRIVER_SMTP_PORT", "DRIVER_SMTP_USER", "DRIVER_SMTP_PASSWORD", "DRIVER_EMAIL_FROM"]
    return all(os.getenv(key) for key in required)


def send_code_via_email(email: str, code: str) -> bool:
    if not _smtp_configured() or not email:
        return False

    msg = EmailMessage()
    msg["Subject"] = "Your Driver login code"
    msg["From"] = os.getenv("DRIVER_EMAIL_FROM")
    msg["To"] = email
    msg.set_content(f"Your 6-digit driver login code is: {code}\nIt expires in 10 minutes.")

    try:
        with smtplib.SMTP(os.getenv("DRIVER_SMTP_HOST"), int(os.getenv("DRIVER_SMTP_PORT", "587"))) as server:
            server.starttls()
            server.login(os.getenv("DRIVER_SMTP_USER"), os.getenv("DRIVER_SMTP_PASSWORD"))
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Failed to send verification email")
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
    code = f"{secrets.randbelow(1000000):06d}"
    driver.verification_code = code
    driver.verification_expires_at = datetime.utcnow() + timedelta(minutes=10)
    driver.failed_attempts = 0

    delivery = "log"
    channel = "sms"
    if req.email:
        if send_code_via_email(req.email, code):
            delivery = "email"
            channel = "email"
        else:
            logger.info("[DEV] login code for %s is %s", phone, code)
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


@app.post("/api/wallet/link")
def wallet_link(req: schemas.WalletLinkRequest, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    wallet = req.wallet_address.strip()
    if not wallet or len(wallet) < 6 or len(wallet) > 128:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    if wallet.upper().startswith("THR") is False and not wallet.startswith("0x"):
        raise HTTPException(status_code=400, detail="Invalid wallet address")

    current_driver.wallet_address = wallet
    current_driver.company_token_symbol = req.company_token_symbol.strip() if req.company_token_symbol else None
    db.commit()
    return {"ok": True}


@app.get("/api/wallet")
def wallet_get(current_driver: Driver = Depends(get_current_driver)):
    return {
        "wallet_address": current_driver.wallet_address,
        "company_token_symbol": current_driver.company_token_symbol,
    }


app.include_router(auth_router)


@app.get("/api/v1/drivers", response_model=List[schemas.DriverRead])
def api_list_drivers(db: Session = Depends(get_db)):
    return crud.list_drivers(db)


@app.post("/api/v1/drivers", response_model=schemas.DriverRead)
def api_create_driver(driver: schemas.DriverCreate, db: Session = Depends(get_db)):
    driver.phone = normalize_phone(driver.phone)
    return crud.create_driver(db, driver)


@app.post("/api/v1/trips/start", response_model=schemas.TripRead)
def api_start_trip(req: schemas.TripStartRequest, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return crud.start_trip(db, req, driver_id=current_driver.id)


@app.post("/api/v1/trips/{trip_id}/finish", response_model=schemas.TripRead)
def api_finish_trip(trip_id: int, req: schemas.TripFinishRequest, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    trip = crud.finish_trip(db, trip_id, req, driver_id=current_driver.id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.post("/api/v1/telemetry", response_model=schemas.TelemetryRead)
def api_create_telemetry(req: schemas.TelemetryCreate, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return crud.create_telemetry(db, req, driver_id=current_driver.id)


@app.get("/api/v1/telemetry", response_model=List[schemas.TelemetryRead])
def api_list_telemetry(limit: int = 100, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return crud.list_telemetry_for_driver(db, driver_id=current_driver.id, limit=min(limit, 500))


@app.post("/api/v1/voice-events", response_model=schemas.VoiceEventRead)
def api_create_voice_event(req: schemas.VoiceEventCreate, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return crud.create_voice_event(db, req, driver_id=current_driver.id)


@app.get("/api/v1/voice-events", response_model=List[schemas.VoiceEventRead])
def api_list_voice_events(limit: int = 100, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    return crud.list_voice_events_for_driver(db, driver_id=current_driver.id, limit=min(limit, 500))


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


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
