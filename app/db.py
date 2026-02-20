import logging
import os
import re
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
logger = logging.getLogger(__name__)


def _build_sqlite_url_from_path(path_str: str) -> str:
    path = Path(path_str)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def get_database_url() -> str:
    url = os.getenv("DRIVER_DB_URL")
    if url:
        return url

    path = os.getenv("DRIVER_DB_PATH")
    if path:
        return _build_sqlite_url_from_path(path)

    default_path = Path("data") / "driver_service.db"
    return _build_sqlite_url_from_path(str(default_path))


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in rows}


def _has_col(conn, table_name: str, col_name: str) -> bool:
    return col_name in _table_columns(conn, table_name)


def _ensure_col(conn, table_name: str, col_name: str, col_type: str) -> None:
    if _has_col(conn, table_name, col_name):
        return
    try:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
        logger.info("DB migrate: added %s.%s", table_name, col_name)
    except Exception:
        logger.exception("DB migrate: failed adding %s.%s", table_name, col_name)


def _safe_execute(conn, sql: str) -> None:
    try:
        conn.execute(text(sql))
    except Exception:
        logger.exception("DB migrate: failed SQL: %s", sql)


def _slugify(name: str) -> str:
    value = (name or "").strip().lower().replace("_", " ")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^a-z0-9-]", "", value)
    value = re.sub(r"-+", "-", value).strip("-")
    value = value[:40].rstrip("-")
    return value or "org"


def _backfill_unique_organization_slugs(conn) -> None:
    rows = conn.execute(text("SELECT id, name, slug FROM organizations ORDER BY id ASC")).fetchall()
    used: set[str] = set()
    for row in rows:
        org_id = row[0]
        name = row[1] or "org"
        existing = (row[2] or "").strip().lower()
        base = _slugify(existing if existing else name)
        candidate = base
        n = 2
        while candidate in used:
            suffix = f"-{n}"
            candidate = f"{base[: max(1, 40 - len(suffix))]}{suffix}"
            n += 1
        used.add(candidate)
        if candidate != existing:
            conn.execute(text("UPDATE organizations SET slug = :slug WHERE id = :id"), {"slug": candidate, "id": org_id})


def _run_sqlite_migrations() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, driver_id INTEGER NOT NULL, token TEXT NOT NULL UNIQUE, created_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL, FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS revoked_tokens (id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE, revoked_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS certifications (id INTEGER PRIMARY KEY, driver_id INTEGER NOT NULL, cert_type TEXT NOT NULL, cert_ref TEXT NULL, issued_at DATETIME NOT NULL, FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS tenant_branding (id INTEGER PRIMARY KEY, group_tag TEXT NOT NULL UNIQUE, app_name TEXT NULL, logo_url TEXT NULL, favicon_url TEXT NULL, primary_color TEXT NULL, plan TEXT NOT NULL DEFAULT 'basic', updated_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS operator_tokens (id INTEGER PRIMARY KEY, group_tag TEXT NULL, organization_id INTEGER NULL, token_hash TEXT NOT NULL UNIQUE, role TEXT NOT NULL, created_at DATETIME NOT NULL, last_used_at DATETIME NULL, expires_at DATETIME NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organizations (id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NULL, type TEXT NOT NULL DEFAULT 'taxi', status TEXT NOT NULL DEFAULT 'pending', default_group_tag TEXT NULL, title TEXT NULL, logo_url TEXT NULL, favicon_url TEXT NULL, token_symbol TEXT NULL, treasury_wallet TEXT NULL, reward_policy_json TEXT NULL, plan TEXT NOT NULL DEFAULT 'basic', plan_status TEXT NOT NULL DEFAULT 'trialing', trial_ends_at DATETIME NULL, addons_json TEXT NULL, billing_name TEXT NULL, billing_email TEXT NULL, billing_address TEXT NULL, billing_country TEXT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organization_members (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, driver_id INTEGER NOT NULL, role TEXT NOT NULL DEFAULT 'driver', approved INTEGER NOT NULL DEFAULT 0, created_at DATETIME NOT NULL, FOREIGN KEY(organization_id) REFERENCES organizations(id), FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organization_requests (id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, city TEXT NULL, contact_email TEXT NULL, type TEXT NOT NULL DEFAULT 'taxi', status TEXT NOT NULL DEFAULT 'pending', created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS trial_attempts (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, ip_hash TEXT NOT NULL, email_hash TEXT NOT NULL, phone_hash TEXT NULL, status TEXT NOT NULL, retry_after INTEGER NULL, organization_id INTEGER NULL, error_code TEXT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS payment_events (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, organization_id INTEGER NOT NULL, provider TEXT NOT NULL, provider_event_id TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL, thronos_tx_id TEXT NULL, block_height INTEGER NULL, confirmations INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(organization_id) REFERENCES organizations(id))"))

        driver_columns = _table_columns(conn, "drivers")
        driver_alterations = {
            "phone": "ALTER TABLE drivers ADD COLUMN phone TEXT",
            "email": "ALTER TABLE drivers ADD COLUMN email TEXT",
            "name": "ALTER TABLE drivers ADD COLUMN name TEXT",
            "role": "ALTER TABLE drivers ADD COLUMN role TEXT NOT NULL DEFAULT 'taxi'",
            "is_verified": "ALTER TABLE drivers ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0",
            "wallet_address": "ALTER TABLE drivers ADD COLUMN wallet_address TEXT",
            "company_token_symbol": "ALTER TABLE drivers ADD COLUMN company_token_symbol TEXT",
            "verification_code": "ALTER TABLE drivers ADD COLUMN verification_code TEXT",
            "verification_expires_at": "ALTER TABLE drivers ADD COLUMN verification_expires_at DATETIME",
            "verification_channel": "ALTER TABLE drivers ADD COLUMN verification_channel TEXT",
            "failed_attempts": "ALTER TABLE drivers ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0",
            "created_at": "ALTER TABLE drivers ADD COLUMN created_at DATETIME",
            "last_login_at": "ALTER TABLE drivers ADD COLUMN last_login_at DATETIME",
            "last_code_sent_at": "ALTER TABLE drivers ADD COLUMN last_code_sent_at DATETIME",
            "taxi_company": "ALTER TABLE drivers ADD COLUMN taxi_company TEXT",
            "plate_number": "ALTER TABLE drivers ADD COLUMN plate_number TEXT",
            "notes": "ALTER TABLE drivers ADD COLUMN notes TEXT",
            "company_name": "ALTER TABLE drivers ADD COLUMN company_name TEXT",
            "group_tag": "ALTER TABLE drivers ADD COLUMN group_tag TEXT",
            "approved": "ALTER TABLE drivers ADD COLUMN approved INTEGER NOT NULL DEFAULT 0",
            "organization_id": "ALTER TABLE drivers ADD COLUMN organization_id INTEGER",
        }
        for col, ddl in driver_alterations.items():
            if col not in driver_columns:
                conn.execute(text(ddl))

        trip_columns = _table_columns(conn, "trips")
        trip_alterations = {
            "company_name": "ALTER TABLE trips ADD COLUMN company_name TEXT",
            "group_tag": "ALTER TABLE trips ADD COLUMN group_tag TEXT",
            "organization_id": "ALTER TABLE trips ADD COLUMN organization_id INTEGER",
            "reward_points": "ALTER TABLE trips ADD COLUMN reward_points REAL",
        }
        for col, ddl in trip_alterations.items():
            if col not in trip_columns:
                conn.execute(text(ddl))

        org_columns = _table_columns(conn, "organizations")
        org_alterations = {
            "slug": "ALTER TABLE organizations ADD COLUMN slug TEXT",
            "plan": "ALTER TABLE organizations ADD COLUMN plan TEXT NOT NULL DEFAULT 'basic'",
            "plan_status": "ALTER TABLE organizations ADD COLUMN plan_status TEXT NOT NULL DEFAULT 'trialing'",
            "trial_ends_at": "ALTER TABLE organizations ADD COLUMN trial_ends_at DATETIME",
            "addons_json": "ALTER TABLE organizations ADD COLUMN addons_json TEXT",
            "billing_name": "ALTER TABLE organizations ADD COLUMN billing_name TEXT",
            "billing_email": "ALTER TABLE organizations ADD COLUMN billing_email TEXT",
            "billing_address": "ALTER TABLE organizations ADD COLUMN billing_address TEXT",
            "billing_country": "ALTER TABLE organizations ADD COLUMN billing_country TEXT",
        }
        for col, ddl in org_alterations.items():
            if col not in org_columns:
                conn.execute(text(ddl))
        _backfill_unique_organization_slugs(conn)

        trial_columns = _table_columns(conn, "trial_attempts")
        trial_alterations = {
            "ip_hash": "ALTER TABLE trial_attempts ADD COLUMN ip_hash TEXT",
            "email_hash": "ALTER TABLE trial_attempts ADD COLUMN email_hash TEXT",
            "phone_hash": "ALTER TABLE trial_attempts ADD COLUMN phone_hash TEXT",
            "status": "ALTER TABLE trial_attempts ADD COLUMN status TEXT",
            "retry_after": "ALTER TABLE trial_attempts ADD COLUMN retry_after INTEGER",
            "organization_id": "ALTER TABLE trial_attempts ADD COLUMN organization_id INTEGER",
            "error_code": "ALTER TABLE trial_attempts ADD COLUMN error_code TEXT",
        }
        for col, ddl in trial_alterations.items():
            if col not in trial_columns:
                conn.execute(text(ddl))

        _ensure_col(conn, "operator_tokens", "organization_id", "INTEGER")
        _ensure_col(conn, "operator_tokens", "expires_at", "DATETIME")

        voice_columns = _table_columns(conn, "voice_messages")
        for col, ddl in {
            "direction": "ALTER TABLE voice_messages ADD COLUMN direction TEXT NOT NULL DEFAULT 'up'",
            "in_reply_to": "ALTER TABLE voice_messages ADD COLUMN in_reply_to INTEGER",
            "read_at": "ALTER TABLE voice_messages ADD COLUMN read_at DATETIME",
            "group_tag": "ALTER TABLE voice_messages ADD COLUMN group_tag TEXT",
        }.items():
            if col not in voice_columns:
                conn.execute(text(ddl))

        conn.execute(text("UPDATE drivers SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        conn.execute(text("UPDATE drivers SET role = 'taxi' WHERE role IS NULL OR role = ''"))
        conn.execute(text("UPDATE drivers SET phone = '+30' || printf('%09d', id) WHERE phone IS NULL OR phone = ''"))

        # Ensure indexed columns exist before index creation, then create indexes safely (no crash loops).
        _ensure_col(conn, "operator_tokens", "organization_id", "INTEGER")

        index_statements = [
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_drivers_phone ON drivers(phone)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_token ON sessions(token)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_revoked_tokens_token ON revoked_tokens(token)",
            "CREATE INDEX IF NOT EXISTS ix_certifications_driver_id ON certifications(driver_id)",
            "CREATE INDEX IF NOT EXISTS idx_trips_group_tag ON trips(group_tag)",
            "CREATE INDEX IF NOT EXISTS idx_tenant_branding_group_tag ON tenant_branding(group_tag)",
            "CREATE INDEX IF NOT EXISTS idx_operator_tokens_group_tag ON operator_tokens(group_tag)",
            "CREATE INDEX IF NOT EXISTS idx_operator_tokens_organization_id ON operator_tokens(organization_id)",
            "CREATE INDEX IF NOT EXISTS idx_drivers_organization_id ON drivers(organization_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_organizations_slug ON organizations(slug)",
            "CREATE INDEX IF NOT EXISTS idx_organization_members_org ON organization_members(organization_id)",
            "CREATE INDEX IF NOT EXISTS idx_trial_attempts_created_at ON trial_attempts(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_trial_attempts_ip_created ON trial_attempts(ip_hash, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_trial_attempts_email_created ON trial_attempts(email_hash, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_trial_attempts_phone_created ON trial_attempts(phone_hash, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_trial_attempts_ip_email_created ON trial_attempts(ip_hash, email_hash, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_voice_messages_group_tag ON voice_messages(group_tag)",
            "CREATE INDEX IF NOT EXISTS idx_voice_messages_driver_id ON voice_messages(driver_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_messages_created_at ON voice_messages(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_payment_events_org_created ON payment_events(organization_id, created_at)",
        ]
        for stmt in index_statements:
            _safe_execute(conn, stmt)


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if DATABASE_URL.startswith("sqlite"):
        _run_sqlite_migrations()
