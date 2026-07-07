import os
import json
import logging
import keyring
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class AuthManager:
    SERVICE_NAME = "HorizonDrive"
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self):
        self.client_id = keyring.get_password(self.SERVICE_NAME, "client_id")
        self.client_secret = keyring.get_password(self.SERVICE_NAME, "client_secret")
        self.credentials = self._load_credentials()

    def set_client_secrets(self, client_id, client_secret):
        """Sets the client ID and secret in the keyring."""
        keyring.set_password(self.SERVICE_NAME, "client_id", client_id)
        keyring.set_password(self.SERVICE_NAME, "client_secret", client_secret)
        self.client_id = client_id
        self.client_secret = client_secret

    def _load_credentials(self):
        """Loads credentials from the keyring."""
        refresh_token = keyring.get_password(self.SERVICE_NAME, "refresh_token")
        if refresh_token and self.client_id and self.client_secret:
            return Credentials(
                token=None,
                refresh_token=refresh_token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_uri="https://oauth2.googleapis.com/token",
                scopes=self.SCOPES
            )
        return None

    def authenticate(self):
        """Starts the OAuth2 flow to get user credentials."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Client ID and Secret must be set before authentication.")

        client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
        self.credentials = flow.run_local_server(port=0)

        # Save the refresh token to the keyring
        if self.credentials and self.credentials.refresh_token:
            keyring.set_password(self.SERVICE_NAME, "refresh_token", self.credentials.refresh_token)
        
        return self.credentials

    def get_service(self):
        """Returns a Google Drive API service instance."""
        if not self.credentials or not self.credentials.valid:
            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
            else:
                self.authenticate()
        
        return build('drive', 'v3', credentials=self.credentials)

    def is_authenticated(self):
        """Checks if the user is currently authenticated."""
        return self.credentials is not None and self.credentials.valid

    def get_quota(self):
        """Fetches Google Drive storage quota.

        Returns:
            dict with keys 'limit', 'usage', 'usageInDrive' (all str bytes),
            or None on failure.
        """
        try:
            service = self.get_service()
            about = service.about().get(fields='storageQuota').execute()
            quota = about.get('storageQuota', {})
            return {
                'limit': quota.get('limit', '0'),
                'usage': quota.get('usage', '0'),
                'usageInDrive': quota.get('usageInDrive', '0'),
            }
        except Exception as e:
            logger.error("AuthManager: Failed to fetch storage quota: %s", e)
            return None
