import json
from typing import Any

import pydantic.json
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel as Base

from src.config import DATABASE_URL, DEBUG

__all__ = ["Base", "engine", "AsyncSessionLocal"]


def _custom_json_serializer(*args: Any, **kwargs: Any) -> str:
    """
    Encodes json in the same way that pydantic does.
    """
    return json.dumps(*args, default=pydantic.json.pydantic_encoder, **kwargs)


engine = create_async_engine(
    DATABASE_URL,
    echo=DEBUG,
    json_serializer=_custom_json_serializer,
    # SQLite-specific connection args
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    expire_on_commit=False,
    autoflush=True,
    bind=engine,
)
