import logging
from pathlib import Path
from typing import Any, Final

import yaml

log = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file with fallback chain.

    Priority:
    1. ./config.yaml (development)
    2. ~/.business-use/config.yaml (production/PyPI users)
    3. Defaults

    Returns:
        Configuration dictionary with all settings
    """
    config_data: dict[str, Any] = {}

    # Try local config first (development)
    local_config = Path("./config.yaml")
    user_config = Path.home() / ".business-use" / "config.yaml"

    loaded_from = None
    if local_config.exists():
        with open(local_config) as f:
            config_data = yaml.safe_load(f) or {}
        loaded_from = str(local_config)
    elif user_config.exists():
        with open(user_config) as f:
            config_data = yaml.safe_load(f) or {}
        loaded_from = str(user_config)

    if loaded_from:
        log.info(f"Loaded configuration from: {loaded_from}")
    else:
        log.info("No config file found, using defaults")

    return config_data


# Load configuration
_config = load_config()

# Determine if we're in development mode (local config exists)
_is_dev = Path("./config.yaml").exists()

# Log level configuration
LOG_LEVEL: Any = _config.get("log_level", logging.WARNING)
ENV: str = _config.get("env", "local")
DEBUG: bool = _config.get("debug", False)

# API key - optional, validated when needed
API_KEY: Final[str | None] = _config.get("api_key")

# Database configuration
# Use local db.sqlite in dev, ~/.business-use/db.sqlite in production
_default_db_path = (
    "./db.sqlite" if _is_dev else str(Path.home() / ".business-use" / "db.sqlite")
)
DATABASE_PATH: Final[str] = _config.get("database_path", _default_db_path)

# Ensure ~/.business-use directory exists for production
if not _is_dev:
    Path.home().joinpath(".business-use").mkdir(parents=True, exist_ok=True)

# For absolute paths, SQLite URLs need 4 slashes total: sqlite+aiosqlite:/// + /path
# For relative paths, use 3 slashes: sqlite+aiosqlite:///path
DATABASE_URL: Final[str] = f"sqlite+aiosqlite:///{DATABASE_PATH}"
