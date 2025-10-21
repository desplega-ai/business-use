"""Adapters layer - Infrastructure adapters (SQLite, etc)."""

from src.adapters.sqlite import SqliteEventStorage

__all__ = [
    "SqliteEventStorage",
]
