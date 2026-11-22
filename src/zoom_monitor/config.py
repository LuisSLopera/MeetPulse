from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    account_id: str
    client_id: str
    client_secret: str
    meeting_ids: tuple[str, ...]
    poll_seconds: float = 20
    sample_seconds: float = 300
    log_level: str = "INFO"
    request_timeout: float = 20
    max_retries: int = 4

    @classmethod
    def from_env(cls, *, require_credentials: bool = True) -> "Settings":
        credentials = {name: os.getenv(name, "").strip() for name in
                       ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET")}
        missing = [name for name, value in credentials.items() if not value]
        raw_ids = os.getenv("ZOOM_MEETING_IDS", "")
        normalized_ids = ("".join(c for c in item if c.isdigit()) for item in raw_ids.split(","))
        ids = tuple(dict.fromkeys(meeting_id for meeting_id in normalized_ids if meeting_id))
        if require_credentials and missing:
            raise ConfigurationError("Faltan variables: " + ", ".join(missing))
        if require_credentials and not ids:
            raise ConfigurationError("ZOOM_MEETING_IDS debe contener al menos un Meeting ID")
        try:
            poll = float(os.getenv("POLL_SECONDS", "20"))
            sample = float(os.getenv("SAMPLE_SECONDS", "300"))
            timeout = float(os.getenv("ZOOM_REQUEST_TIMEOUT", "20"))
            retries = int(os.getenv("ZOOM_MAX_RETRIES", "4"))
        except ValueError as exc:
            raise ConfigurationError("Los intervalos y reintentos deben ser numericos") from exc
        if poll <= 0 or sample <= 0 or timeout <= 0 or retries < 0:
            raise ConfigurationError("Los intervalos deben ser positivos y los reintentos no negativos")
        return cls(credentials["ZOOM_ACCOUNT_ID"], credentials["ZOOM_CLIENT_ID"],
                   credentials["ZOOM_CLIENT_SECRET"], ids, poll, sample,
                   os.getenv("LOG_LEVEL", "INFO").upper(), timeout, retries)

