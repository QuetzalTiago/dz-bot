"""Centralized configuration loading.

Historically every cog opened ``config.json`` independently and read secrets
straight out of it. This module gives the whole bot a single, cached entry
point and, crucially, lets any value be overridden by an environment variable
so secrets can be injected by a secret manager instead of living in a file on
disk.

Environment overrides use the ``DZ_`` prefix. Secrets map to
``DZ_SECRET_<UPPER_SNAKE>`` and top-level keys to ``DZ_<UPPER_SNAKE>``. For
example ``config["secrets"]["discordToken"]`` can be supplied as
``DZ_SECRET_DISCORD_TOKEN`` and ``config["prefix"]`` as ``DZ_PREFIX``.
"""

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, Optional

logger = logging.getLogger("discord")

CONFIG_PATH = os.environ.get("DZ_CONFIG_PATH", "config.json")


def _camel_to_env(name: str) -> str:
    """Convert a camelCase config key to UPPER_SNAKE for env lookups."""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return snake.upper()


@lru_cache(maxsize=1)
def _load_file() -> Dict[str, Any]:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(
            "Config file %s not found; relying on environment variables only.",
            CONFIG_PATH,
        )
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Config file %s is not valid JSON: %s", CONFIG_PATH, exc)
        raise


def load_config() -> Dict[str, Any]:
    """Return the merged configuration (file values, env overrides applied).

    The returned dict is safe to read repeatedly; the file is read once and
    cached. Secrets are never logged.
    """
    config = json.loads(json.dumps(_load_file()))  # deep copy of cached file
    config.setdefault("secrets", {})

    # Environment overrides for secrets: DZ_SECRET_<UPPER_SNAKE>
    for key, value in os.environ.items():
        if key.startswith("DZ_SECRET_"):
            # Match against known camelCase secret names, else store as-is.
            target = key[len("DZ_SECRET_") :]
            config["secrets"][_env_to_existing_key(config["secrets"], target)] = value
        elif key.startswith("DZ_") and not key.startswith("DZ_SECRET_"):
            target = key[len("DZ_") :]
            existing_key = _env_to_existing_key(config, target)
            # Never let a scalar env value clobber a nested section (e.g. a
            # stray DZ_SECRETS would otherwise replace the "secrets" dict).
            if not isinstance(config.get(existing_key), dict):
                config[existing_key] = value

    return config


def _env_to_existing_key(section: Dict[str, Any], env_suffix: str) -> str:
    """Find an existing camelCase key whose UPPER_SNAKE form matches env_suffix.

    Falls back to the lowercased suffix when there is no existing key so brand
    new values can still be injected from the environment.
    """
    for existing in section:
        if _camel_to_env(existing) == env_suffix:
            return existing
    return env_suffix.lower()


def get_secret(name: str, required: bool = True) -> Optional[str]:
    """Fetch a single secret by its config key, honoring env overrides."""
    config = load_config()
    value = config.get("secrets", {}).get(name)
    if value is None:
        env_key = f"DZ_SECRET_{_camel_to_env(name)}"
        value = os.environ.get(env_key)
    if value is None and required:
        raise KeyError(
            f"Missing required secret '{name}'. Set it in {CONFIG_PATH} under "
            f"'secrets' or via the {f'DZ_SECRET_{_camel_to_env(name)}'} env var."
        )
    return value


def reset_cache() -> None:
    """Clear the cached config file (used by tests)."""
    _load_file.cache_clear()
