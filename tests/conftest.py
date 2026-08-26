"""Shared fixtures and headless-import stubs for Horizon Drive tests.

The GUI modules import tkinter-backed libraries (customtkinter, PIL.ImageTk).
CI and dev machines may have no display or no python3-tk, so we register
minimal stand-ins before any application module is imported.
"""

import importlib.machinery
import sys
import threading
import types


class _StubModule(types.ModuleType):
    """Module that fabricates placeholder classes for any attribute access."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        placeholder = type(name, (), {"__init__": lambda self, *a, **k: None})
        setattr(self, name, placeholder)
        return placeholder


def _ensure_stub(module_name: str) -> None:
    try:
        importlib.import_module(module_name)
    except Exception:
        sys.modules[module_name] = _StubModule(module_name)


_ensure_stub("tkinter")
_ensure_stub("customtkinter")
_ensure_stub("PIL.ImageTk")
_ensure_stub("pystray")

importlib.import_module("PIL")

import pytest  # noqa: E402  (must come after stub registration above)


class FakeKeyring:
    """In-memory stand-in for the platform keyring backend."""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def get_password(self, service, username):
        with self._lock:
            return self._store.get((service, username))

    def set_password(self, service, username, password):
        with self._lock:
            self._store[(service, username)] = password


@pytest.fixture
def fake_keyring(monkeypatch):
    backend = FakeKeyring()
    monkeypatch.setattr("horizon_drive.auth.keyring", backend)
    return backend
