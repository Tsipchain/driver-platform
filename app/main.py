import logging
import hashlib
import os
import re
import secrets
import smtplib
import socket
from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
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



def make_slug(name: str) -> str:
    value = (name or "").strip().lower().replace("_", " ")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "", value)
    value = re.sub(r"-+", "-", value).strip("-")
    value = value[:40].rstrip("-")
    return value or "org"


def make_unique_slug(db: Session, base_slug_or_name: str) -> str:
    base = make_slug(base_slug_or_name)
    slug = base
    n = 1
    while db.query(models.Organization).filter(models.Organization.slug == slug).first() is not None:
        n += 1
        suffix = f"-{n}"
        slug = f"{base[: max(1, 40 - len(suffix))]}{suffix}"
    return slug


def get_client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    return request.client.host if request.client else "unknown"


def _trial_hash_salt() -> str:
    return (os.getenv("TRIAL_HASH_SALT") or "").strip()


def _sha(value: Optional[str]) -> str:
    val = (value or "").strip()
    return hashlib.sha256(f"{_trial_hash_salt()}|{val}".encode("utf-8")).hexdigest()


def _trial_limits() -> dict:
    return {
        "short": int(os.getenv("TRIAL_RL_WINDOW_SHORT_SEC", "900")),
        "long": int(os.getenv("TRIAL_RL_WINDOW_LONG_SEC", "86400")),
        "ip_short": int(os.getenv("TRIAL_RL_MAX_IP_SHORT", "5")),
        "email_short": int(os.getenv("TRIAL_RL_MAX_EMAIL_SHORT", "3")),
        "ip_email_short": int(os.getenv("TRIAL_RL_MAX_IP_EMAIL_SHORT", "2")),
        "phone_short": int(os.getenv("TRIAL_RL_MAX_PHONE_SHORT", "2")),
        "ip_long": int(os.getenv("TRIAL_RL_MAX_IP_LONG", "25")),
        "email_long": int(os.getenv("TRIAL_RL_MAX_EMAIL_LONG", "6")),
        "phone_long": int(os.getenv("TRIAL_RL_MAX_PHONE_LONG", "6")),
    }


def enqueue_thronos_receipt(org_id: int, provider_event_id: str, amount: float, currency: str) -> dict:
    return {
        "queued": True,
        "organization_id": org_id,
        "provider_event_id": provider_event_id,
        "amount": amount,
        "currency": currency,
    }


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


def dev_show_code_enabled() -> bool:
    # Never allow OTP logging in production, even if misconfigured
    if is_production_env():
        return False
    return (os.getenv("DEV_SHOW_CODE") or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _b2s(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", "replace")
        except Exception:
            return repr(value)
    return str(value)


def send_code_via_email(email: str, code: str, name_or_phone: str) -> bool:
    if not email or not _smtp_enabled() or not _smtp_configured():
        return False

    smtp_host = os.getenv("DRIVER_SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("DRIVER_SMTP_PORT", "465"))
    smtp_user = os.getenv("DRIVER_SMTP_USER", "")
    smtp_password = os.getenv("DRIVER_SMTP_PASSWORD", "")
    smtp_from = (os.getenv("DRIVER_SMTP_FROM") or smtp_user).strip()
    use_ssl = os.getenv("DRIVER_SMTP_USE_SSL", "true").lower() in ("1", "true", "yes")
    timeout = int(os.getenv("DRIVER_SMTP_TIMEOUT", "10"))

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

    if not msg.get("Message-ID"):
        msg["Message-ID"] = make_msgid()

    message_id = msg.get("Message-ID")

    try:
        if use_ssl:
            server_ctx = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=timeout)
        else:
            server_ctx = smtplib.SMTP(smtp_host, smtp_port, timeout=timeout)

        with server_ctx as server:
            ehlo_code, ehlo_resp = server.ehlo()
            logger.info(
                "SMTP response EHLO: %s %s host=%s port=%s ssl=%s",
                ehlo_code,
                _b2s(ehlo_resp),
                smtp_host,
                smtp_port,
                use_ssl,
            )

            if not use_ssl:
                tls_code, tls_resp = server.starttls()
                logger.info(
                    "SMTP response STARTTLS: %s %s host=%s port=%s",
                    tls_code,
                    _b2s(tls_resp),
                    smtp_host,
                    smtp_port,
                )
                ehlo2_code, ehlo2_resp = server.ehlo()
                logger.info(
                    "SMTP response EHLO2: %s %s host=%s port=%s",
                    ehlo2_code,
                    _b2s(ehlo2_resp),
                    smtp_host,
                    smtp_port,
                )

            login_code, login_resp = server.login(smtp_user, smtp_password)
            logger.info(
                "SMTP response LOGIN: %s %s host=%s port=%s ssl=%s",
                login_code,
                _b2s(login_resp),
                smtp_host,
                smtp_port,
                use_ssl,
            )

            from_addr = parseaddr(msg.get("From", ""))[1] or smtp_user
            to_addr = parseaddr(email)[1] or email

            refused = server.send_message(msg, from_addr=from_addr, to_addrs=[to_addr])
            noop_code, noop_resp = server.noop()
            refused_list = list(refused.keys()) if isinstance(refused, dict) else []

            logger.info(
                "smtp_send_success host=%s port=%s ssl=%s message_id=%s to=%s refused=%s server_noop=%s %s",
                smtp_host,
                smtp_port,
                use_ssl,
                message_id,
                to_addr,
                refused_list,
                noop_code,
                _b2s(noop_resp),
            )

            if to_addr in refused_list:
                logger.error(
                    "smtp_send_refused host=%s port=%s ssl=%s message_id=%s to=%s",
                    smtp_host,
                    smtp_port,
                    use_ssl,
                    message_id,
                    to_addr,
                )
                return False

        return True
    except (smtplib.SMTPException, socket.error, OSError) as e:
        logger.exception(
            "SMTP send failure to=%s host=%s port=%s ssl=%s message_id=%s -> %s",
            email,
            smtp_host,
            smtp_port,
            use_ssl,
            message_id,
            str(e),
        )
        return False


def get_current_driver(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Driver:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.split(" ", 1)[1].strip()
    if crud.is_token_revoked(db, token):
        raise HTTPException(status_code=401, detail="Unauthorized")
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
    if crud.is_token_revoked(db, token):
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




def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_operator_scope(db: Session, token: Optional[str]) -> tuple[Optional[str], Optional[int]]:
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = token.strip()
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    global_token = _get_admin_token()
    if global_token and token == global_token:
        return None, None  # full access

    hashed = _hash_token(token)
    row = db.query(models.OperatorToken).filter(models.OperatorToken.token_hash == hashed).first()
    if not row:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if row.expires_at and row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Token expired")
    row.last_used_at = datetime.utcnow()
    db.commit()
    return row.group_tag, row.organization_id


def _branding_defaults(group_tag: Optional[str]) -> dict:
    return {
        "group_tag": group_tag,
        "plan": "basic",
        "app_name": "Thronos Driver",
        "title": "Thronos Driver",
        "logo_url": "https://thronoschain.org/thronos-decentralize.png",
        "favicon_url": "https://thronoschain.org/thronos-coin.png",
        "primary_color": "#00ff88",
    }



PLANS_MATRIX = {
    "basic": {
        "features": ["trips", "telemetry_manual", "telemetry_auto_gps", "operator_map_basic", "otp_login", "voice_send_only"],
    },
    "pro": {
        "features": ["trips", "telemetry_manual", "telemetry_auto_gps", "operator_map_basic", "voice_send_only", "voice_reply", "events_filters", "exports_pdf", "white_label_branding", "retention_12m"],
    },
    "enterprise": {
        "features": ["trips", "telemetry_manual", "telemetry_auto_gps", "operator_map_basic", "voice_send_only", "voice_reply", "events_filters", "exports_pdf", "white_label_branding", "retention_12m", "multi_org", "custom_domain", "rewards_module"],
    },
}


def _addons_set(addons_json: Optional[str]) -> set[str]:
    if not addons_json:
        return set()
    try:
        import json
        data = json.loads(addons_json)
        if isinstance(data, list):
            return {str(x) for x in data}
        if isinstance(data, dict):
            return {k for k, v in data.items() if v}
    except Exception:
        return set()
    return set()


def is_feature_enabled(org: Optional[models.Organization], feature: str) -> bool:
    if org is None:
        return feature in PLANS_MATRIX["basic"]["features"]
    plan = (org.plan or "basic").lower()
    base = set(PLANS_MATRIX.get(plan, PLANS_MATRIX["basic"])["features"])
    addons = _addons_set(org.addons_json)
    if "white_label" in addons:
        base.add("white_label_branding")
    if "rewards" in addons:
        base.add("rewards_module")
    if "pdf_packs" in addons:
        base.add("exports_pdf")
    return feature in base

def _parse_multipart_voice_payload(raw_body: bytes, content_type: str) -> tuple[bytes, str, Optional[int], Optional[str], Optional[str], Optional[int], Optional[str]]:
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
    driver_id: Optional[int] = None
    group_tag: Optional[str] = None

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
        elif 'name="driver_id"' in headers_text:
            txt = value.decode("utf-8", errors="ignore").strip()
            if txt:
                driver_id = int(txt)
        elif 'name="group_tag"' in headers_text:
            group_tag = value.decode("utf-8", errors="ignore").strip() or None

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Missing file part")

    return file_bytes, filename, trip_id, note, target, driver_id, group_tag




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

    driver = crud.get_or_create_driver_by_phone(
        db,
        phone=phone,
        email=req.email,
        name=req.name,
        role=req.role,
        group_tag=None,
        organization_id=req.organization_id,
    )
    if req.organization_id:
        org = crud.get_organization(db, int(req.organization_id))
        if not org or org.status != "active":
            raise HTTPException(status_code=400, detail="Invalid organization")
        driver.organization_id = org.id
        driver.approved = False
        driver.group_tag = None
        member = crud.get_org_member(db, org.id, driver.id)
        if not member:
            member = models.OrganizationMember(organization_id=org.id, driver_id=driver.id, role="driver", approved=False, created_at=datetime.utcnow())
            db.add(member)
    now = datetime.utcnow()
    cooldown_seconds = 120

    if driver.last_code_sent_at:
        elapsed = (now - driver.last_code_sent_at).total_seconds()
        if elapsed < cooldown_seconds:
            retry_after = max(1, int(cooldown_seconds - elapsed))
            return JSONResponse(status_code=429, content={"error": "CODE_TOO_SOON", "retry_after": retry_after})

    code = generate_otp_code()
    if dev_show_code_enabled():
        logger.warning("DEV OTP for %s = %s", phone, code)
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
        "driver": {"id": driver.id, "name": driver.name, "role": driver.role, "phone": driver.phone, "group_tag": driver.group_tag, "organization_id": driver.organization_id, "approved": bool(driver.approved)},
        "session_token": token,
    }


@auth_router.post("/logout")
def logout(authorization: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if token:
        crud.revoke_session_token(db, token)
    return {"ok": True}


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
        "group_tag": current_driver.group_tag,
        "organization_id": current_driver.organization_id,
        "approved": bool(current_driver.approved),
        "company_name": current_driver.company_name,
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


def _require_driver_approved(driver: Driver):
    if not bool(driver.approved):
        raise HTTPException(status_code=403, detail="Driver approval pending")


@app.post("/api/v1/voice-messages", response_model=schemas.VoiceMessageRead)
async def api_create_voice_message(
    request: Request,
    current_driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    _require_driver_approved(current_driver)

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    raw_body = await request.body()
    file_bytes, incoming_filename, trip_id, note, target, _driver_id, _group_tag = _parse_multipart_voice_payload(raw_body, content_type)
    target = target or "center"

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
    msg.direction = "up"
    msg.group_tag = current_driver.group_tag
    db.commit()
    db.refresh(msg)
    return msg



@app.post("/api/v1/voice-messages/send", response_model=schemas.VoiceMessageRead)
async def api_create_voice_message_send_alias(
    request: Request,
    current_driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    return await api_create_voice_message(request=request, current_driver=current_driver, db=db)


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


@app.get("/api/plans")
def api_plans():
    return {
        "plans": PLANS_MATRIX,
        "addons": ["white_label", "extra_retention", "pdf_packs", "ai_scoring", "rewards"],
    }


@app.post("/api/trials/create")
def api_create_trial(req: schemas.TrialCreateRequest, db: Session = Depends(get_db)):
    slug = slugify_text(req.name)
    row = db.query(models.Organization).filter(models.Organization.slug == slug).first()
    if row:
        return {"ok": True, "organization_id": row.id, "plan_status": row.plan_status}
    row = models.Organization(
        name=req.name.strip(),
        slug=slug,
        type=req.type,
        status="active",
        default_group_tag=f"{slug}-a",
        title=req.name.strip(),
        plan="basic",
        plan_status="trialing",
        trial_ends_at=datetime.utcnow() + timedelta(days=14),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "organization_id": row.id, "plan_status": row.plan_status, "trial_ends_at": row.trial_ends_at}


@app.get("/api/organizations", response_model=List[schemas.OrganizationRead])
def api_list_organizations(
    type: Optional[str] = None,
    status: Optional[str] = "active",
    db: Session = Depends(get_db),
):
    return crud.list_organizations(db, org_type=type, status=status)


@app.post("/api/organizations/request")
def api_organization_request(req: schemas.OrganizationRequestCreate, db: Session = Depends(get_db)):
    slug = make_slug(req.name)
    existing = db.query(models.OrganizationRequest).filter(models.OrganizationRequest.slug == slug).first()
    if existing:
        return {"ok": True, "id": existing.id, "status": existing.status}
    row = models.OrganizationRequest(
        name=req.name.strip(),
        slug=slug,
        city=(req.city or "").strip() or None,
        contact_email=(req.contact_email or "").strip() or None,
        type=req.type or "taxi",
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id, "status": row.status}


@app.post("/api/organizations/{organization_id}/approve")
def api_organization_approve(
    organization_id: int,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    _resolve_operator_scope(db, x_admin_token)
    row = crud.get_organization(db, organization_id)
    if not row:
        req = db.query(models.OrganizationRequest).filter(models.OrganizationRequest.id == organization_id).first()
        if not req:
            raise HTTPException(status_code=404, detail="Organization not found")
        row = models.Organization(
            name=req.name,
            slug=req.slug,
            type=req.type,
            status="active",
            default_group_tag=req.slug + "-a",
            title=req.name,
            created_at=datetime.utcnow(),
        )
        req.status = "approved"
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "organization_id": row.id, "status": row.status}
    row.status = "active"
    db.commit()
    return {"ok": True, "organization_id": row.id, "status": row.status}


@app.post("/api/organizations/{organization_id}/join")
def api_organization_join(
    organization_id: int,
    current_driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    org = crud.get_organization(db, organization_id)
    if not org or org.status != "active":
        raise HTTPException(status_code=404, detail="Organization not found")
    current_driver.organization_id = org.id
    current_driver.approved = False
    current_driver.group_tag = None
    member = crud.get_org_member(db, org.id, current_driver.id)
    if not member:
        member = models.OrganizationMember(organization_id=org.id, driver_id=current_driver.id, role="driver", approved=False, created_at=datetime.utcnow())
        db.add(member)
    db.commit()
    return {"ok": True, "pending": True}


@app.post("/api/organizations/{organization_id}/members/{driver_id}/approve")
def api_organization_member_approve(
    organization_id: int,
    driver_id: int,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    if forced_org and forced_org != organization_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    org = crud.get_organization(db, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if forced_group and org.default_group_tag != forced_group:
        raise HTTPException(status_code=403, detail="Forbidden")
    driver = crud.get_driver(db, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    member = crud.get_org_member(db, organization_id, driver_id)
    if not member:
        member = models.OrganizationMember(organization_id=organization_id, driver_id=driver_id, role="driver", approved=True, created_at=datetime.utcnow())
        db.add(member)
    member.approved = True
    driver.organization_id = organization_id
    driver.group_tag = org.default_group_tag
    driver.approved = True
    db.commit()
    return {"ok": True, "driver_id": driver_id, "approved": True, "group_tag": driver.group_tag}


@app.get("/api/operator/dashboard")
def api_operator_dashboard(
    group_tag: Optional[str] = None,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    if forced_org:
        org = crud.get_organization(db, forced_org)
        effective_group = (org.default_group_tag if org else None) or forced_group
    else:
        effective_group = forced_group or group_tag
    return crud.get_operator_dashboard(db, group_tag=effective_group)


@app.get("/api/operator/pending-drivers")
def api_operator_pending_drivers(
    group_tag: Optional[str] = None,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    effective_group = forced_group or group_tag
    q = db.query(models.Driver).filter(models.Driver.approved == False)
    if forced_org:
        q = q.filter(models.Driver.organization_id == forced_org)
    if effective_group:
        q = q.filter(models.Driver.group_tag == effective_group)
    rows = q.order_by(models.Driver.created_at.desc()).limit(200).all()
    return {"items": [{"id": d.id, "name": d.name, "phone": d.phone, "group_tag": d.group_tag, "approved": bool(d.approved)} for d in rows]}


@app.post("/api/operator/drivers/{driver_id}/approve")
def api_operator_approve_driver(
    driver_id: int,
    group_tag: Optional[str] = None,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    driver = crud.get_driver(db, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    effective_group = forced_group or group_tag
    if forced_org and driver.organization_id != forced_org:
        raise HTTPException(status_code=403, detail="Forbidden")
    if effective_group and driver.group_tag and driver.group_tag != effective_group:
        raise HTTPException(status_code=403, detail="Forbidden")
    driver.approved = True
    db.commit()
    return {"ok": True, "driver_id": driver.id, "approved": True}


@app.get("/api/operator/events/recent")
def api_operator_recent_events(
    group_tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    if forced_org:
        org = crud.get_organization(db, forced_org)
        effective_group = (org.default_group_tag if org else None) or forced_group
    else:
        effective_group = forced_group or group_tag
    return {"events": crud.get_recent_operator_events(db, group_tag=effective_group, limit=limit)}




@app.get("/api/branding")
def api_branding(group_tag: Optional[str] = None, org: Optional[int] = None, db: Session = Depends(get_db)):
    if org and not group_tag:
        org_row = crud.get_organization(db, org)
        if org_row:
            group_tag = org_row.default_group_tag
    defaults = _branding_defaults(group_tag)
    if not group_tag:
        return defaults
    row = db.query(models.TenantBranding).filter(models.TenantBranding.group_tag == group_tag).first()
    if not row:
        return defaults
    defaults.update({
        "plan": row.plan or defaults["plan"],
        "app_name": row.app_name or defaults["app_name"],
        "title": row.app_name or defaults["title"],
        "logo_url": row.logo_url or defaults["logo_url"],
        "favicon_url": row.favicon_url or defaults["favicon_url"],
        "primary_color": row.primary_color or defaults["primary_color"],
    })
    return defaults


@app.post("/api/admin/branding")
async def api_admin_branding(request: Request, x_admin_token: Optional[str] = Header(default=None), db: Session = Depends(get_db)):
    if not _get_admin_token() or x_admin_token != _get_admin_token():
        raise HTTPException(status_code=401, detail="Unauthorized")
    if "multipart/form-data" not in (request.headers.get("content-type") or ""):
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    form = await request.form()
    group_tag = (form.get("group_tag") or "").strip()
    if not group_tag:
        raise HTTPException(status_code=400, detail="group_tag required")

    org = db.query(models.Organization).filter(models.Organization.default_group_tag == group_tag).first()
    if org and not is_feature_enabled(org, "white_label_branding"):
        raise HTTPException(status_code=403, detail="Branding available on Pro/Enterprise or addon")

    row = db.query(models.TenantBranding).filter(models.TenantBranding.group_tag == group_tag).first()
    if not row:
        row = models.TenantBranding(group_tag=group_tag, updated_at=datetime.utcnow())
        db.add(row)

    row.plan = (form.get("plan") or row.plan or "basic")
    row.app_name = form.get("app_name") or row.app_name
    row.primary_color = form.get("primary_color") or row.primary_color
    row.logo_url = form.get("logo_url") or row.logo_url
    row.favicon_url = form.get("favicon_url") or row.favicon_url

    brand_dir = Path("/app/data/branding") / group_tag
    brand_dir.mkdir(parents=True, exist_ok=True)

    logo_file = form.get("logo_file")
    if logo_file is not None and hasattr(logo_file, "read"):
        content = await logo_file.read()
        (brand_dir / "logo.png").write_bytes(content)
        row.logo_url = f"/branding/{group_tag}/logo.png"

    favicon_file = form.get("favicon_file")
    if favicon_file is not None and hasattr(favicon_file, "read"):
        content = await favicon_file.read()
        (brand_dir / "favicon.png").write_bytes(content)
        row.favicon_url = f"/branding/{group_tag}/favicon.png"

    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.get("/branding/{group_tag}/{filename}")
def branding_file(group_tag: str, filename: str):
    if filename not in {"logo.png", "favicon.png", "favicon.ico"}:
        raise HTTPException(status_code=404, detail="Not found")
    file_path = Path("/app/data/branding") / group_tag / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(file_path)


@app.get("/api/v1/voice-messages/operator-inbox")
def api_operator_voice_inbox(
    group_tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    effective_group = forced_group or group_tag
    q = db.query(models.VoiceMessage).filter(models.VoiceMessage.target == "center")
    if forced_org:
        q = q.join(models.Driver, models.Driver.id == models.VoiceMessage.driver_id).filter(models.Driver.organization_id == forced_org)
    if effective_group:
        q = q.filter(models.VoiceMessage.group_tag == effective_group)
    rows = q.order_by(models.VoiceMessage.created_at.desc()).limit(limit).all()
    return {"items": [
        {"id": r.id, "driver_id": r.driver_id, "trip_id": r.trip_id, "group_tag": r.group_tag, "note": r.note, "created_at": r.created_at, "audio_url": f"/api/v1/voice-messages/{r.id}/download"}
        for r in rows
    ]}


@app.get("/api/operator/voice/recent")
def api_operator_voice_recent(
    group_tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    effective_group = forced_group or group_tag
    q = db.query(models.VoiceMessage).filter(models.VoiceMessage.direction == "up")
    if forced_org:
        q = q.join(models.Driver, models.Driver.id == models.VoiceMessage.driver_id).filter(models.Driver.organization_id == forced_org)
    if effective_group:
        q = q.filter(models.VoiceMessage.group_tag == effective_group)
    rows = q.order_by(models.VoiceMessage.created_at.desc()).limit(limit).all()
    return {"items": [
        {"id":r.id,"driver_id":r.driver_id,"trip_id":r.trip_id,"group_tag":r.group_tag,"note":r.note,"created_at":r.created_at}
        for r in rows
    ]}


@app.post("/api/operator/voice/send")
async def api_operator_voice_send(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    if "multipart/form-data" not in (request.headers.get("content-type") or ""):
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")

    raw = await request.body()
    file_bytes, incoming_filename, trip_id, note, _target, payload_driver_id, payload_group_tag = _parse_multipart_voice_payload(raw, request.headers.get("content-type", ""))

    target_group = forced_group or payload_group_tag
    target_driver = None
    if payload_driver_id:
        target_driver = crud.get_driver(db, int(payload_driver_id))
        if not target_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        if forced_group and target_driver.group_tag != forced_group:
            raise HTTPException(status_code=403, detail="Forbidden")
        if forced_org and target_driver.organization_id != forced_org:
            raise HTTPException(status_code=403, detail="Forbidden")
        if target_driver.organization_id:
            org = crud.get_organization(db, target_driver.organization_id)
            if not is_feature_enabled(org, "voice_reply"):
                raise HTTPException(status_code=403, detail="Voice reply not enabled for plan")
        target_group = target_driver.group_tag or target_group
    elif target_group:
        q = db.query(models.Driver).filter(models.Driver.group_tag == target_group)
        target_driver = q.order_by(models.Driver.last_login_at.desc().nullslast(), models.Driver.created_at.desc()).first()
        if not target_driver:
            raise HTTPException(status_code=404, detail="No driver found for group")
    else:
        raise HTTPException(status_code=400, detail="driver_id or group_tag required")

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    suffix = Path(incoming_filename).suffix or ".webm"
    ddir = _voice_storage_base() / str(target_driver.id) / "down"
    ddir.mkdir(parents=True, exist_ok=True)
    path = ddir / f"{ts}{suffix}"
    path.write_bytes(file_bytes)

    row = crud.create_voice_message(
        db,
        driver_id=target_driver.id,
        trip_id=trip_id,
        file_path=str(path),
        note=note,
        target="cb",
        status="received",
    )
    row.direction = "to_driver"
    row.target = "driver"
    row.group_tag = target_driver.group_tag or target_group
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id, "driver_id": row.driver_id, "group_tag": row.group_tag}


@app.post("/api/v1/voice-messages/reply-to-driver")
async def api_voice_reply_to_driver(
    request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    return await api_operator_voice_send(request=request, x_admin_token=x_admin_token, db=db)


@app.post("/api/operator/voice/{msg_id}/reply")
async def api_operator_voice_reply(
    msg_id: int,
    request: Request,
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    parent = db.query(models.VoiceMessage).filter(models.VoiceMessage.id == msg_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Message not found")
    if forced_group and parent.group_tag != forced_group:
        raise HTTPException(status_code=403, detail="Forbidden")

    if "multipart/form-data" not in (request.headers.get("content-type") or ""):
        raise HTTPException(status_code=400, detail="Expected multipart/form-data")
    raw = await request.body()
    file_bytes, incoming_filename, _trip_id, note, _target, _driver_id, _group_tag = _parse_multipart_voice_payload(raw, request.headers.get("content-type",""))

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    suffix = Path(incoming_filename).suffix or ".webm"
    ddir = _voice_storage_base() / str(parent.driver_id) / "down"
    ddir.mkdir(parents=True, exist_ok=True)
    path = ddir / f"{ts}{suffix}"
    path.write_bytes(file_bytes)

    row = crud.create_voice_message(db, driver_id=parent.driver_id, trip_id=parent.trip_id, file_path=str(path), note=note, target="cb", status="received")
    row.direction = "down"
    row.target = "driver"
    row.in_reply_to = parent.id
    row.group_tag = parent.group_tag
    db.commit(); db.refresh(row)
    return {"ok": True, "id": row.id}


@app.get("/api/v1/voice-messages/inbox")
def api_driver_voice_inbox(
    since: Optional[str] = None,
    current_driver: Driver = Depends(get_current_driver),
    db: Session = Depends(get_db),
):
    q = db.query(models.VoiceMessage).filter(
        models.VoiceMessage.driver_id == current_driver.id,
        models.VoiceMessage.target == "driver"
    )
    if since:
        try:
            dt = datetime.fromisoformat(since)
            q = q.filter(models.VoiceMessage.created_at >= dt)
        except Exception:
            pass
    rows = q.order_by(models.VoiceMessage.created_at.desc()).limit(100).all()
    return {"items": [{"id":r.id,"note":r.note,"created_at":r.created_at,"read_at":r.read_at,"from_center":True,"audio_url":f"/api/v1/voice-messages/{r.id}/download"} for r in rows]}


@app.post("/api/v1/voice-messages/{msg_id}/ack")
def api_driver_voice_ack(msg_id: int, current_driver: Driver = Depends(get_current_driver), db: Session = Depends(get_db)):
    row = db.query(models.VoiceMessage).filter(models.VoiceMessage.id == msg_id, models.VoiceMessage.driver_id == current_driver.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    row.read_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@app.get("/api/v1/voice-messages/{msg_id}/download")
def api_voice_download(
    msg_id: int,
    authorization: Optional[str] = Header(default=None),
    x_admin_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    row = db.query(models.VoiceMessage).filter(models.VoiceMessage.id == msg_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")

    # driver auth path
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ",1)[1].strip()
        if not crud.is_token_revoked(db, token):
            sess = crud.get_session_by_token(db, token)
            if sess and sess.driver_id == row.driver_id:
                return FileResponse(row.file_path)

    forced_group, forced_org = _resolve_operator_scope(db, x_admin_token)
    if forced_group is not None and row.group_tag != forced_group:
        raise HTTPException(status_code=403, detail="Forbidden")
    if x_admin_token:
        return FileResponse(row.file_path)

    raise HTTPException(status_code=401, detail="Unauthorized")



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
    if current_driver:
        _require_driver_approved(current_driver)
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
    if current_driver:
        _require_driver_approved(current_driver)
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


@app.get("/")
def landing_page():
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    return FileResponse(file_path)


@app.get("/app")
def app_page():
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.html")
    return FileResponse(file_path)


@app.get("/operator")
def operator_page():
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.html")
    return FileResponse(file_path)


@app.get("/school")
def school_page():
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "app.html")
    return FileResponse(file_path)


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=False), name="frontend")
