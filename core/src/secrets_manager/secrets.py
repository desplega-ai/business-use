"""Secrets management with priority resolution.

Supports loading secrets from project and global locations:
- Project: ./.business-use/secrets.yaml (highest priority)
- Global: ~/.business-use/secrets.yaml (fallback)

Also supports environment variable substitution.
"""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

# Regex patterns for variable substitution
SECRET_PATTERN = re.compile(r"\$\{secret\.([^}]+)\}")
ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def load_secrets_file(path: Path) -> dict[str, str]:
    """Load secrets from a YAML file.

    Args:
        path: Path to secrets.yaml file

    Returns:
        Dictionary of key-value pairs

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is malformed
    """
    if not path.exists():
        raise FileNotFoundError(f"Secrets file not found: {path}")

    with path.open("r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Secrets file must contain a dictionary: {path}")

    # Convert all values to strings
    return {str(k): str(v) for k, v in data.items()}


def load_secrets_from_workspace() -> dict[str, str]:
    """Load secrets with priority: project → global.

    Priority:
    1. ./.business-use/secrets.yaml (project-level, highest priority)
    2. ~/.business-use/secrets.yaml (global fallback)

    Returns:
        Merged dictionary with project secrets overriding global

    Note:
        If neither file exists, returns empty dict (not an error - secrets are optional)
    """
    secrets: dict[str, str] = {}

    # Load global secrets first (lower priority)
    global_secrets_path = Path.home() / ".business-use" / "secrets.yaml"
    if global_secrets_path.exists():
        try:
            global_secrets = load_secrets_file(global_secrets_path)
            secrets.update(global_secrets)
            log.debug(
                f"Loaded {len(global_secrets)} secrets from {global_secrets_path}"
            )
        except Exception as e:
            log.warning(f"Failed to load global secrets: {e}")

    # Load project secrets (higher priority, overrides global)
    project_secrets_path = Path(".business-use") / "secrets.yaml"
    if project_secrets_path.exists():
        try:
            project_secrets = load_secrets_file(project_secrets_path)
            secrets.update(project_secrets)
            log.debug(
                f"Loaded {len(project_secrets)} secrets from {project_secrets_path}"
            )
        except Exception as e:
            log.warning(f"Failed to load project secrets: {e}")

    return secrets


def get_secret(key: str, secrets: dict[str, str] | None = None) -> str:
    """Get secret with priority: project → global → error.

    Args:
        key: Secret key to lookup
        secrets: Optional pre-loaded secrets dict. If None, will load from workspace.

    Returns:
        Secret value

    Raises:
        ValueError: If secret not found in any location
    """
    if secrets is None:
        secrets = load_secrets_from_workspace()

    if key in secrets:
        return secrets[key]

    # Build helpful error message
    project_path = Path(".business-use") / "secrets.yaml"
    global_path = Path.home() / ".business-use" / "secrets.yaml"

    error_msg = f"Secret '{key}' not found\n"
    error_msg += "Searched:\n"
    error_msg += f"  1. {project_path} {'✗' if not project_path.exists() else '(not found in file)'}\n"
    error_msg += f"  2. {global_path} {'✗' if not global_path.exists() else '(not found in file)'}\n"
    error_msg += "\n"
    error_msg += "Create a secrets file:\n"
    error_msg += "  cp .business-use/secrets.yaml.example .business-use/secrets.yaml\n"
    error_msg += f"  # Then add: {key}: your_value_here"

    raise ValueError(error_msg)


def get_env_var(key: str) -> str:
    """Get environment variable or raise error.

    Args:
        key: Environment variable name

    Returns:
        Environment variable value

    Raises:
        ValueError: If environment variable not set
    """
    value = os.getenv(key)
    if value is None:
        error_msg = f"Environment variable '{key}' not set\n"
        error_msg += "Set it with:\n"
        error_msg += f"  export {key}=your_value_here"
        raise ValueError(error_msg)

    return value


def resolve_variable(value: str, secrets: dict[str, str] | None = None) -> str:
    """Parse and resolve ${secret.KEY} and ${VAR} patterns.

    Resolution order:
    1. ${secret.KEY} → get_secret(KEY) from project/global secrets
    2. ${VAR} → get_env_var(VAR) from environment

    Fail fast if variable not found (no defaults).

    Args:
        value: String potentially containing variables
        secrets: Optional pre-loaded secrets dict

    Returns:
        String with variables resolved

    Raises:
        ValueError: If any variable cannot be resolved

    Examples:
        >>> resolve_variable("Bearer ${secret.API_KEY}")
        "Bearer sk_test_123"

        >>> resolve_variable("${API_BASE_URL}/payments")
        "https://api.example.com/payments"
    """
    if not isinstance(value, str):
        return value

    # Load secrets once if not provided
    if secrets is None:
        secrets = load_secrets_from_workspace()

    result = value

    # First, resolve ${secret.KEY} patterns
    for match in SECRET_PATTERN.finditer(value):
        full_match = match.group(0)  # ${secret.KEY}
        key = match.group(1)  # KEY
        secret_value = get_secret(key, secrets)
        result = result.replace(full_match, secret_value)

    # Then, resolve ${VAR} patterns (but not ${secret.*} which are already handled)
    for match in ENV_PATTERN.finditer(result):
        full_match = match.group(0)  # ${VAR}
        # Skip if it's a secret pattern
        if full_match.startswith("${secret."):
            continue
        key = match.group(1)  # VAR
        env_value = get_env_var(key)
        result = result.replace(full_match, env_value)

    return result


def substitute_string_values(obj: Any, secrets: dict[str, str] | None = None) -> Any:
    """Recursively substitute variables in string values.

    Works with:
    - Strings: resolve variables
    - Dicts: recursively process values
    - Lists: recursively process items
    - Other types: return as-is

    Args:
        obj: Object to process
        secrets: Optional pre-loaded secrets dict

    Returns:
        Object with variables resolved in all string values
    """
    if isinstance(obj, str):
        return resolve_variable(obj, secrets)
    elif isinstance(obj, dict):
        return {k: substitute_string_values(v, secrets) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_string_values(item, secrets) for item in obj]
    else:
        return obj


def substitute_handler_input(
    handler_input: Any, secrets: dict[str, str] | None = None
) -> Any:
    """Substitute variables in handler_input params.

    Only processes params.url, params.headers, params.body, params.command.
    This is the scoped substitution for trigger nodes.

    Args:
        handler_input: ActionInput object (or dict)
        secrets: Optional pre-loaded secrets dict

    Returns:
        Handler input with variables resolved
    """
    # Handle both Pydantic models and dicts
    if hasattr(handler_input, "model_dump"):
        data = handler_input.model_dump()
    elif isinstance(handler_input, dict):
        data = handler_input
    else:
        return handler_input

    # Only substitute in params
    if "params" in data and data["params"]:
        params = data["params"]

        # Substitute in specific fields only
        if "url" in params and params["url"]:
            params["url"] = substitute_string_values(params["url"], secrets)

        if "headers" in params and params["headers"]:
            params["headers"] = substitute_string_values(params["headers"], secrets)

        if "body" in params and params["body"]:
            params["body"] = substitute_string_values(params["body"], secrets)

        if "command" in params and params["command"]:
            params["command"] = substitute_string_values(params["command"], secrets)

    return data
