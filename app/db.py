import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


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


def _run_sqlite_migrations() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY, driver_id INTEGER NOT NULL, token TEXT NOT NULL UNIQUE, created_at DATETIME NOT NULL, last_seen_at DATETIME NOT NULL, FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS revoked_tokens (id INTEGER PRIMARY KEY, token TEXT NOT NULL UNIQUE, revoked_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS certifications (id INTEGER PRIMARY KEY, driver_id INTEGER NOT NULL, cert_type TEXT NOT NULL, cert_ref TEXT NULL, issued_at DATETIME NOT NULL, FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS tenant_branding (id INTEGER PRIMARY KEY, group_tag TEXT NOT NULL UNIQUE, app_name TEXT NULL, logo_url TEXT NULL, favicon_url TEXT NULL, primary_color TEXT NULL, plan TEXT NOT NULL DEFAULT 'basic', updated_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS operator_tokens (id INTEGER PRIMARY KEY, group_tag TEXT NULL, organization_id INTEGER NULL, token_hash TEXT NOT NULL UNIQUE, role TEXT NOT NULL, created_at DATETIME NOT NULL, last_used_at DATETIME NULL, expires_at DATETIME NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organizations (id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, type TEXT NOT NULL DEFAULT 'taxi', status TEXT NOT NULL DEFAULT 'pending', default_group_tag TEXT NULL, title TEXT NULL, logo_url TEXT NULL, favicon_url TEXT NULL, token_symbol TEXT NULL, treasury_wallet TEXT NULL, reward_policy_json TEXT NULL, created_at DATETIME NOT NULL)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organization_members (id INTEGER PRIMARY KEY, organization_id INTEGER NOT NULL, driver_id INTEGER NOT NULL, role TEXT NOT NULL DEFAULT 'driver', approved INTEGER NOT NULL DEFAULT 0, created_at DATETIME NOT NULL, FOREIGN KEY(organization_id) REFERENCES organizations(id), FOREIGN KEY(driver_id) REFERENCES drivers(id))"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS organization_requests (id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, city TEXT NULL, contact_email TEXT NULL, type TEXT NOT NULL DEFAULT 'taxi', status TEXT NOT NULL DEFAULT 'pending', created_at DATETIME NOT NULL)"))

        driver_columns = _table_columns(conn, "drivers")
        alterations = {
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
        for col, ddl in alterations.items():
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

        conn.execute(text("UPDATE drivers SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        conn.execute(text("UPDATE drivers SET role = 'taxi' WHERE role IS NULL OR role = ''"))
        conn.execute(text("UPDATE drivers SET phone = '+30' || printf('%09d', id) WHERE phone IS NULL OR phone = ''"))

        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_drivers_phone ON drivers(phone)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_token ON sessions(token)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_revoked_tokens_token ON revoked_tokens(token)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_certifications_driver_id ON certifications(driver_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_trips_group_tag ON trips(group_tag)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_branding_group_tag ON tenant_branding(group_tag)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_operator_tokens_group_tag ON operator_tokens(group_tag)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_operator_tokens_organization_id ON operator_tokens(organization_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_drivers_organization_id ON drivers(organization_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_organization_members_org ON organization_members(organization_id)"))

        conn.execute(text("CREATE TABLE IF NOT EXISTS voice_messages (id INTEGER PRIMARY KEY, driver_id INTEGER NOT NULL, trip_id INTEGER NULL, file_path TEXT NOT NULL, duration_sec REAL NULL, target TEXT NULL, note TEXT NULL, status TEXT NOT NULL, direction TEXT NOT NULL DEFAULT 'up', in_reply_to INTEGER NULL, read_at DATETIME NULL, group_tag TEXT NULL, created_at DATETIME NOT NULL, FOREIGN KEY(driver_id) REFERENCES drivers(id), FOREIGN KEY(trip_id) REFERENCES trips(id))"))
        operator_token_columns = _table_columns(conn, "operator_tokens")
        operator_token_alterations = {
            "organization_id": "ALTER TABLE operator_tokens ADD COLUMN organization_id INTEGER",
            "expires_at": "ALTER TABLE operator_tokens ADD COLUMN expires_at DATETIME",
        }
        for col, ddl in operator_token_alterations.items():
            if col not in operator_token_columns:
                conn.execute(text(ddl))

        voice_columns = _table_columns(conn, "voice_messages")
        voice_alterations = {
            "direction": "ALTER TABLE voice_messages ADD COLUMN direction TEXT NOT NULL DEFAULT 'up'",
            "in_reply_to": "ALTER TABLE voice_messages ADD COLUMN in_reply_to INTEGER",
            "read_at": "ALTER TABLE voice_messages ADD COLUMN read_at DATETIME",
            "group_tag": "ALTER TABLE voice_messages ADD COLUMN group_tag TEXT",
        }
        for col, ddl in voice_alterations.items():
            if col not in voice_columns:
                conn.execute(text(ddl))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_voice_messages_group_tag ON voice_messages(group_tag)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_voice_messages_driver_id ON voice_messages(driver_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_voice_messages_created_at ON voice_messages(created_at)"))


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if DATABASE_URL.startswith("sqlite"):
        _run_sqlite_migrations()
