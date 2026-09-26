"""Database connection and session factory."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# Default to local SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./shipsafe.db")

# For SQLite, enable check_same_thread=False for multi-threaded FastAPI / Streamlit access
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from sqlalchemy import text


def init_db():
    """Create all database tables if they do not exist and ensure columns exist."""
    Base.metadata.create_all(bind=engine)
    # Automatic column additions for SQLite
    with engine.connect() as conn:
        for table, col, col_type in [
            ("analysis_runs", "engine_version", "VARCHAR(50) DEFAULT '2.1.0'"),
            ("analysis_runs", "prompt_version", "VARCHAR(50) DEFAULT '2.1.0'"),
            ("analysis_runs", "context_hash", "VARCHAR(100)"),
            ("findings", "evidence_type", "VARCHAR(50) DEFAULT 'source_code'"),
            ("findings", "validation_status", "VARCHAR(50) DEFAULT 'UNVERIFIABLE'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass



def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
