import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def _build_sqlite_url_from_path(path_str: str) -> str:
    path = Path(path_str)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    # Absolute path is recommended inside containers
    return f"sqlite:///{path}"


def get_database_url() -> str:
    """Resolve database URL with precedence:

    1. DRIVER_DB_URL (full SQLAlchemy URL, e.g. PostgreSQL)
    2. DRIVER_DB_PATH (path to SQLite file)
    3. Default ./data/driver_service.db (SQLite)
    """
    url = os.getenv("DRIVER_DB_URL")
    if url:
        return url

    path = os.getenv("DRIVER_DB_PATH")
    if path:
        return _build_sqlite_url_from_path(path)

    # default: ./data/driver_service.db
    default_path = Path("data") / "driver_service.db"
    return _build_sqlite_url_from_path(str(default_path))


DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables if they do not exist."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
