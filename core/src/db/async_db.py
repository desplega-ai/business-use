import json
import logging
from typing import Any

import pydantic.json
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel as Base

from src.config import DATABASE_URL, DEBUG, IS_POSTGRES

__all__ = ["Base", "engine", "AsyncSessionLocal"]

log = logging.getLogger(__name__)


def _custom_json_serializer(*args: Any, **kwargs: Any) -> str:
    """
    Encodes json in the same way that pydantic does.
    """
    return json.dumps(*args, default=pydantic.json.pydantic_encoder, **kwargs)


# Build connection arguments based on database type
if IS_POSTGRES:
    # PostgreSQL with asyncpg - no special connect_args needed
    connect_args: dict[str, Any] = {}
    log.info("Initializing PostgreSQL connection with asyncpg")
else:
    # Local SQLite with aiosqlite
    connect_args = {"check_same_thread": False}
    log.info("Initializing SQLite connection with aiosqlite")

engine = create_async_engine(
    DATABASE_URL,
    echo=DEBUG,
    json_serializer=_custom_json_serializer,
    connect_args=connect_args,
)


# Enable WAL mode and pragmas for SQLite only
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:
    # Only apply SQLite-specific pragmas, skip for PostgreSQL
    if IS_POSTGRES:
        return

    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


AsyncSessionLocal = async_sessionmaker(
    expire_on_commit=False,
    autoflush=True,
    bind=engine,
)
