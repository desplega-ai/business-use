import logging
from typing import Any, Final

from starlette.config import Config

log = logging.getLogger(__name__)

config = Config(".env")


LOG_LEVEL: Any = config("LOG_LEVEL", default=logging.WARNING)
ENV: str = config("ENV", default="local")
DEBUG: bool = config("DEBUG", cast=bool, default=False)

API_KEY: Final[str] = config("API_KEY")

# Database configuration
DATABASE_PATH: Final[str] = config("DATABASE_PATH", default="/tmp/business-use-db.sqlite")
# For absolute paths, SQLite URLs need 4 slashes total: sqlite+aiosqlite:/// + /path
# For relative paths, use 3 slashes: sqlite+aiosqlite:///path
DATABASE_URL: Final[str] = f"sqlite+aiosqlite:///{DATABASE_PATH}"
