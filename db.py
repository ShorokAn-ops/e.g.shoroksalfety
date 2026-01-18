# db.py
import os
import sqlite3
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()

if DB_BACKEND == "postgres":
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/predictions")
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./invoices.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# ✅ 1) This is for tests that do: with get_db() as conn:
@contextmanager
def get_db():
    """
    Returns a sqlite3 connection as a context manager.
    Needed for legacy tests that use raw SQL with sqlite3.
    """
    # extract sqlite file path from DATABASE_URL like: sqlite:///./invoices.db
    if "sqlite:///" in DATABASE_URL:
        db_path = DATABASE_URL.replace("sqlite:///", "")
    elif DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL[10:]
    else:
        # fallback to default file name
        db_path = "invoices.db"

    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ✅ 2) This is for FastAPI Depends(get_db_session):
def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
