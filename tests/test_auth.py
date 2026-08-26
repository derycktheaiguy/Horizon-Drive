"""Tests for horizon_drive.auth.AuthManager."""

from unittest import mock

import pytest
from google.oauth2.credentials import Credentials

from horizon_drive.auth import AuthManager


class TestKeyringBackedState:
    def test_no_stored_secrets(self, fake_keyring):
        manager = AuthManager()
        assert manager.client_id is None
        assert manager.client_secret is None
        assert manager.credentials is None
        assert manager.is_authenticated() is False

    def test_set_client_secrets_persists_to_keyring(self, fake_keyring):
        manager = AuthManager()
        manager.set_client_secrets("id-123", "secret-456")

        assert manager.client_id == "id-123"
        assert manager.client_secret == "secret-456"
        assert fake_keyring.get_password(AuthManager.SERVICE_NAME, "client_id") == "id-123"
        assert fake_keyring.get_password(AuthManager.SERVICE_NAME, "client_secret") == "secret-456"

    def test_refresh_token_restores_credentials(self, fake_keyring):
        fake_keyring.set_password(AuthManager.SERVICE_NAME, "client_id", "cid")
        fake_keyring.set_password(AuthManager.SERVICE_NAME, "client_secret", "csec")
        fake_keyring.set_password(AuthManager.SERVICE_NAME, "refresh_token", "rtok-xyz")

        manager = AuthManager()

        assert isinstance(manager.credentials, Credentials)
        assert manager.credentials.refresh_token == "rtok-xyz"
        assert manager.credentials.client_id == "cid"

    def test_missing_client_secrets_ignores_refresh_token(self, fake_keyring):
        fake_keyring.set_password(AuthManager.SERVICE_NAME, "refresh_token", "rtok")

        manager = AuthManager()
        assert manager.credentials is None


class TestAuthenticate:
    def test_requires_secrets(self, fake_keyring):
        manager = AuthManager()
        with pytest.raises(ValueError, match="Client ID and Secret"):
            manager.authenticate()

    def test_successful_flow_saves_refresh_token(self, fake_keyring):
        manager = AuthManager()
        manager.set_client_secrets("cid", "csec")

        creds = Credentials(token="access", refresh_token="rtok-1")
        flow = mock.MagicMock()
        flow.run_local_server.return_value = creds

        with mock.patch(
            "horizon_drive.auth.InstalledAppFlow.from_client_config",
            return_value=flow,
        ) as from_config:
            result = manager.authenticate()

        assert result is creds
        assert fake_keyring.get_password(AuthManager.SERVICE_NAME, "refresh_token") == "rtok-1"
        config = from_config.call_args[0][0]
        assert config["installed"]["client_id"] == "cid"
        assert config["installed"]["client_secret"] == "csec"

    def test_flow_without_refresh_token_stores_nothing(self, fake_keyring):
        manager = AuthManager()
        manager.set_client_secrets("cid", "csec")

        creds = Credentials(token="access")  # no refresh token issued
        flow = mock.MagicMock()
        flow.run_local_server.return_value = creds

        with mock.patch(
            "horizon_drive.auth.InstalledAppFlow.from_client_config",
            return_value=flow,
        ):
            manager.authenticate()

        assert fake_keyring.get_password(AuthManager.SERVICE_NAME, "refresh_token") is None


class TestQuota:
    def _service_mock(self, execute_result=None, raises=False):
        about_call = mock.MagicMock()
        if raises:
            about_call.execute.side_effect = RuntimeError("API down")
        else:
            about_call.execute.return_value = execute_result

        service = mock.MagicMock()
        service.about.return_value.get.return_value = about_call
        return service

    def test_quota_happy_path(self, fake_keyring):
        manager = AuthManager()
        service = self._service_mock({"storageQuota": {"limit": "15", "usage": "5", "usageInDrive": "4"}})
        with mock.patch.object(manager, "get_service", return_value=service):
            quota = manager.get_quota()

        assert quota == {"limit": "15", "usage": "5", "usageInDrive": "4"}

    def test_quota_defaults_when_fields_absent(self, fake_keyring):
        manager = AuthManager()
        service = self._service_mock({})
        with mock.patch.object(manager, "get_service", return_value=service):
            quota = manager.get_quota()

        assert quota == {"limit": "0", "usage": "0", "usageInDrive": "0"}

    def test_quota_returns_none_on_api_failure(self, fake_keyring):
        manager = AuthManager()
        service = self._service_mock(raises=True)
        with mock.patch.object(manager, "get_service", return_value=service):
            assert manager.get_quota() is None
