import datetime as dt
import logging

import requests
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from bwac.core.constants import BARENTS_WATCH_TOKEN_URL

logger = logging.getLogger(__name__)

# renew a token this many seconds before it actually expires
RENEWAL_MARGIN_S = 100


class BarentsWatchSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="_",
        env_prefix="BARENTS_WATCH_",
        extra="ignore",
    )

    client_id: str
    client_secret: str

    scope: str = Field(default="ais")
    grant_type: str = Field(default="client_credentials")


class Access:
    config: BarentsWatchSettings
    expiration: None
    _token: str

    def __init__(self):
        self.config = BarentsWatchSettings()
        self._token = None
        self.expiration = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)

    def acquire(self, force: bool = False):
        if not force and not self.requires_renewal():
            logger.debug("Access.acquire: no renewal required")
            return

        response = requests.post(
            BARENTS_WATCH_TOKEN_URL,
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": self.config.scope,
                "grant_type": self.config.grant_type,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()

        now = dt.datetime.now(tz=dt.timezone.utc)
        self._token = response.json()

        self.expiration = now + dt.timedelta(seconds=self.expires_in)

    def ensure_token(self):
        if not self._token:
            raise RuntimeError("Access: not token available. Call .acquire() first")

    def requires_renewal(self):
        # renew ahead of the expiry, so that a token is never handed out when
        # it is about to be rejected
        now = dt.datetime.now(tz=dt.timezone.utc)
        return (now + dt.timedelta(seconds=RENEWAL_MARGIN_S)) > self.expiration

    @property
    def access_token(self):
        self.ensure_token()
        return self._token["access_token"]

    @property
    def expires_in(self):
        self.ensure_token()
        return int(self._token["expires_in"])
