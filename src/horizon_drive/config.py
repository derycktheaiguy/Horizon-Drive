"""Application configuration persistence.

Config lives at ~/.config/horizon-drive/config.json (XDG standard,
respecting $XDG_CONFIG_HOME). For compatibility with pre-0.2.2 installs,
loading falls back to ./config.json in the working directory if the
canonical file is absent.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

APP_DIR_NAME = "horizon-drive"
CONFIG_FILE_NAME = "config.json"


def get_config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_DIR_NAME)


def get_config_path():
    return os.path.join(get_config_dir(), CONFIG_FILE_NAME)


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("Could not parse config at %s: %s", path, e)
        return None


def load_config():
    """Returns the parsed config dict, or None when no valid config exists."""
    config = _read_json(get_config_path())
    if config is None:
        legacy_path = os.path.join(os.getcwd(), CONFIG_FILE_NAME)
        config = _read_json(legacy_path)
        if config is not None:
            logger.info("Using legacy config from %s", legacy_path)
    return config


def save_config(config):
    """Persists config to the canonical location. Returns the path written."""
    directory = get_config_dir()
    os.makedirs(directory, exist_ok=True)
    path = get_config_path()
    with open(path, "w") as f:
        json.dump(config, f, indent=4)
    logger.info("Saved config to %s", path)
    return path
