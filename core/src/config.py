import logging
import os
from pathlib import Path
from typing import Any, Final

import yaml

log = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file with fallback chain.

    Priority:
    1. ./.business-use/config.yaml (project-level, highest priority)
    2. ./config.yaml (legacy support, will be deprecated)
    3. ~/.business-use/config.yaml (global fallback)
    4. Defaults

    Returns:
        Configuration dictionary with all settings
    """
    config_data: dict[str, Any] = {}

    # Priority 1: Project-level workspace config
    project_config = Path(".business-use") / "config.yaml"

    # Priority 2: Legacy local config (backward compatibility)
    local_config = Path("./config.yaml")

    # Priority 3: Global config
    user_config = Path.home() / ".business-use" / "config.yaml"

    loaded_from = None
    if project_config.exists():
        with open(project_config) as f:
            config_data = yaml.safe_load(f) or {}
        loaded_from = str(project_config)
    elif local_config.exists():
        with open(local_config) as f:
            config_data = yaml.safe_load(f) or {}
        loaded_from = str(local_config)
        log.warning(
            f"Config found at {local_config} - consider moving to .business-use/config.yaml"
        )
    elif user_config.exists():
        with open(user_config) as f:
            config_data = yaml.safe_load(f) or {}
        loaded_from = str(user_config)

    if loaded_from:
        log.info(f"Loaded configuration from: {loaded_from}")
    else:
        log.info("No config file found, using defaults")

    return config_data


def get_env_or_config(env_key: str, config_key: str, default: Any = None) -> Any:
    """Get value from environment variable or config file, with env taking precedence.

    Args:
        env_key: Environment variable name
        config_key: Key in config dictionary
        default: Default value if neither env nor config has the value

    Returns:
        Value from env var (highest priority), config file, or default
    """
    # Priority: ENV var → Config file → Default
    env_value = os.environ.get(env_key)
    if env_value is not None:
        return env_value

    return _config.get(config_key, default)


# Load configuration
_config = load_config()

# Determine if we're in development mode (project config or legacy config exists)
_is_dev = (Path(".business-use") / "config.yaml").exists() or Path(
    "./config.yaml"
).exists()

# Log level configuration
LOG_LEVEL: Any = get_env_or_config(
    "BUSINESS_USE_LOG_LEVEL", "log_level", logging.WARNING
)
ENV: str = get_env_or_config("BUSINESS_USE_ENV", "env", "local")
DEBUG: bool = get_env_or_config("BUSINESS_USE_DEBUG", "debug", False)

# API key - optional, validated when needed
API_KEY: Final[str | None] = get_env_or_config("BUSINESS_USE_API_KEY", "api_key")

# Database configuration
# DATABASE_URL can be:
# - Postgres: postgresql+asyncpg://user:pass@host/db (or postgresql://, auto-converted)
# - SQLite: Not set (uses DATABASE_PATH instead)
_database_url_raw: str | None = get_env_or_config(
    "BUSINESS_USE_DATABASE_URL", "database_url"
)

# Auto-convert postgresql:// to postgresql+asyncpg:// for async support
if _database_url_raw and _database_url_raw.startswith("postgresql://"):
    _database_url_raw = _database_url_raw.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )

# Fix sslmode parameter for asyncpg (it doesn't accept sslmode, needs ssl)
if _database_url_raw and "sslmode=" in _database_url_raw:
    _database_url_raw = _database_url_raw.replace("sslmode=", "ssl=")

# Local database path for SQLite
# Use .business-use/db.sqlite in dev, ~/.business-use/db.sqlite in production
_default_db_path = (
    "./.business-use/db.sqlite"
    if _is_dev
    else str(Path.home() / ".business-use" / "db.sqlite")
)
DATABASE_PATH: Final[str] = get_env_or_config(
    "BUSINESS_USE_DATABASE_PATH", "database_path", _default_db_path
)

# Ensure ~/.business-use directory exists for production
if not _is_dev:
    Path.home().joinpath(".business-use").mkdir(parents=True, exist_ok=True)

# Determine database type and build DATABASE_URL
_is_postgres = _database_url_raw and (
    _database_url_raw.startswith("postgresql+asyncpg://")
    or _database_url_raw.startswith("postgres://")
)

# Build DATABASE_URL based on database type
DATABASE_URL: Final[str] = (
    _database_url_raw  # type: ignore[assignment]
    if _is_postgres
    else f"sqlite+aiosqlite:///{DATABASE_PATH}"
)
IS_POSTGRES: Final[bool] = bool(_is_postgres)
