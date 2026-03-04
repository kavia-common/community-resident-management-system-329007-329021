"""
Database connection and session management.

Flow: DatabaseSessionFlow
- Reads PostgreSQL connection parameters from environment variables.
- Creates a SQLAlchemy engine and session factory.
- Provides a dependency-injectable session generator for FastAPI routes.

Contract:
  Input: POSTGRES_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT env vars
  Output: SQLAlchemy Session via get_db() generator
  Errors: Raises on connection failure; logs connection issues
  Side effects: Opens/closes DB connections
"""

import logging
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

# --- Configuration from environment variables ---
# These are set in the .env file and provided by the deployment environment.
POSTGRES_USER = os.getenv("POSTGRES_USER", "appuser")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dbuser123")
POSTGRES_DB = os.getenv("POSTGRES_DB", "myapp")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5000")

# POSTGRES_URL may contain the full URL or just host:port/db
_raw_url = os.getenv("POSTGRES_URL", "")
if _raw_url.startswith("postgresql://"):
    # Full URL provided — inject user:password if not already present
    # Format: postgresql://user:pass@host:port/db
    DATABASE_URL = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
else:
    DATABASE_URL = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@localhost:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

logger.info("Connecting to database at port %s, db=%s", POSTGRES_PORT, POSTGRES_DB)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# PUBLIC_INTERFACE
def get_db():
    """
    FastAPI dependency that yields a database session.

    Yields a SQLAlchemy Session and ensures it is closed after the request.
    Usage: Depends(get_db) in route parameters.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
