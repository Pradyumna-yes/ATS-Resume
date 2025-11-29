# app/db/session.py
"""
Compatibility shim for DB sessions.

- If settings.DATABASE_URL is a SQLAlchemy URL (not Mongo), this will create
  a normal SQLAlchemy engine + SessionLocal (sync).
- If the project uses MongoDB (MONGODB_URI set, or DATABASE_URL starts with "mongodb"),
  this module provides a clear runtime error when someone tries to use SQL sessions,
  so code fails fast with an actionable message instead of an ImportError.
"""

from typing import Generator, Optional
import os

from app.core.config import settings

# Guard to avoid importing SQLAlchemy unless needed (keeps dependencies optional)
def _is_sql_database(url: Optional[str]) -> bool:
    if not url:
        return False
    lower = url.lower()
    # treat mongodb URIs as non-sql
    if lower.startswith("mongodb"):
        return False
    # common SQL schemes
    return any(lower.startswith(s) for s in ("postgresql", "mysql", "sqlite", "mssql", "oracle"))

if _is_sql_database(getattr(settings, "DATABASE_URL", None)):
    # Create a SQLAlchemy engine and SessionLocal
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
        engine = create_engine(SQLALCHEMY_DATABASE_URL, future=True, echo=False, pool_pre_ping=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

        def get_db() -> Generator:
            """
            Yields a SQLAlchemy session. Use as dependency:
                db = Depends(get_db)
            """
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

    except Exception as exc:
        # If sqlalchemy isn't installed, give a useful error
        raise RuntimeError(
            "SQLAlchemy support requested, but failed to import or configure it. "
            "Install SQLAlchemy (`pip install sqlalchemy`) and ensure DATABASE_URL is valid. "
            f"Original error: {exc}"
        ) from exc

else:
    # MongoDB / no-SQL configuration: provide a friendly shim to help debugging
    SessionLocal = None

    def get_db() -> Generator:
        """
        Compatibility shim when using MongoDB / Beanie.

        Many older modules expect a SQLAlchemy session dependency (get_db / SessionLocal).
        If your app is now using MongoDB, replace SQL usage with the async Beanie/Motor API.

        If you really need SQL for some operations, set a proper DATABASE_URL in .env (Postgres)
        and install SQLAlchemy. Otherwise update imports that expect a SQL session.

        Raises a clear RuntimeError to fail fast and show next steps.
        """
        raise RuntimeError(
            "SQL session requested but the application is configured for MongoDB (no SQL DATABASE_URL found). "
            "Options:\n"
            " 1) If you want to use Postgres, set DATABASE_URL in your .env to a valid SQLAlchemy URL "
            "   (e.g. postgresql+psycopg2://user:pass@localhost:5432/dbname) and install SQLAlchemy.\n"
            " 2) If you moved to MongoDB (Beanie), update the code that imports SQL sessions to use the Mongo API. "
            "   See app/db/mongo.py and app/db/documents.py for the Beanie setup.\n"
            "This error helps you find and update legacy SQL usage."
        )
