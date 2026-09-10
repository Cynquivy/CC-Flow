from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine is not None else None
)


def check_db_connection() -> str:
    """Lightweight connectivity probe for the health endpoint.

    Never raises: an unreachable or unconfigured database must not stop the
    API from booting, since no schema exists yet (that's M3).
    """
    if engine is None:
        return "not_configured"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unreachable"
