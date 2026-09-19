"""Application configuration persistence.

Config lives at ~/.config/horizon-drive/config.json (XDG standard,
respecting $XDG_CONFIG_HOME). For compatibility with pre-0.2.2 installs,
loading falls back to ./config.json in the working directory if the
canonical file is absent.
"""

import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

APP_DIR_NAME = "horizon-drive"
CONFIG_FILE_NAME = "config.json"


def get_config_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    if not os.path.isabs(base):
        base = os.path.expanduser("~/.config")
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
    try:
        return validate_config(config) if config is not None else None
    except ValueError as exc:
        logger.warning("Invalid configuration: %s", exc)
        return None


def validate_config(config):
    folder = config.get("local_folder")
    mode = config.get("sync_mode", "Two-way")
    if not isinstance(folder, str) or not folder.strip():
        raise ValueError("Choose a local sync folder.")
    folder = os.path.expanduser(folder.strip())
    if not os.path.isabs(folder):
        raise ValueError("Choose an absolute folder path.")
    if mode not in ("Two-way", "Backup"):
        raise ValueError("Choose Two-way or Backup sync.")
    return {**config, "local_folder": folder, "sync_mode": mode}


def atomic_write_json(path, data):
    """Replace metadata only after a complete write, preserving the old file on error."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".horizon-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=4)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_config(config):
    """Persists config to the canonical location. Returns the path written."""
    directory = get_config_dir()
    os.makedirs(directory, exist_ok=True)
    path = get_config_path()
    atomic_write_json(path, validate_config(config))
    logger.info("Saved config to %s", path)
    return path
