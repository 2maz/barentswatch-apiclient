import requests
import datetime as dt
import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from bwac.core.constants import BARENTS_WATCH_TOKEN_URL

logger = logging.getLogger(__name__)


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
        )

        now = dt.datetime.now(tz=dt.timezone.utc)
        self._token = response.json()

        self.expiration = now + dt.timedelta(seconds=self.expires_in)

    def ensure_token(self):
        if not self._token:
            raise RuntimeError("Access: not token available. Call .acquire() first")

    def requires_renewal(self):
        now = dt.datetime.now(tz=dt.timezone.utc)
        return (now - dt.timedelta(seconds=100)) > self.expiration

    @property
    def access_token(self):
        self.ensure_token()
        return self._token["access_token"]

    @property
    def expires_in(self):
        self.ensure_token()
        return int(self._token["expires_in"])
