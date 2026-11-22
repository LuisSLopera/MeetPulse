from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

LOG = logging.getLogger(__name__)


class ZoomAPIError(RuntimeError):
    def __init__(self, operation: str, status: int | None, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.operation, self.status, self.retryable = operation, status, retryable


@dataclass(frozen=True)
class LiveMeeting:
    meeting_id: str
    uuid: str
    started_at: str | None = None


def encode_uuid(uuid: str) -> str:
    """Zoom exige doble URL encoding si el UUID inicia con / o contiene //."""
    encoded = quote(uuid, safe="")
    return quote(encoded, safe="") if uuid.startswith("/") or "//" in uuid else encoded


class ZoomClient:
    def __init__(self, account_id: str, client_id: str, client_secret: str, *,
                 timeout: float = 20, max_retries: int = 4,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.account_id, self.client_id, self.client_secret = account_id, client_id, client_secret
        self.max_retries = max_retries
        self.http = httpx.AsyncClient(timeout=timeout, transport=transport,
                                      headers={"User-Agent": "zoom-attendance-monitor/0.1"})
        self._token: str | None = None
        self._token_expires_monotonic = 0.0

    async def __aenter__(self): return self
    async def __aexit__(self, *_): await self.aclose()
    async def aclose(self): await self.http.aclose()

    async def authenticate(self, *, force: bool = False) -> None:
        if not force and self._token and time.monotonic() < self._token_expires_monotonic:
            return
        try:
            response = await self.http.post("https://zoom.us/oauth/token",
                params={"grant_type": "account_credentials", "account_id": self.account_id},
                auth=(self.client_id, self.client_secret))
        except httpx.RequestError as exc:
            raise ZoomAPIError("oauth", None, f"Error de red: {type(exc).__name__}", retryable=True) from exc
        if response.status_code >= 400:
            raise ZoomAPIError("oauth", response.status_code, "Zoom rechazo la autenticacion")
        data = response.json()
        if not data.get("access_token"):
            raise ZoomAPIError("oauth", response.status_code, "Respuesta OAuth sin access_token")
        self._token = data["access_token"]
        self._token_expires_monotonic = time.monotonic() + max(1, int(data.get("expires_in", 3600)) - 120)

    async def _get(self, path: str, params: dict[str, Any], operation: str) -> dict[str, Any]:
        refreshed = False
        for attempt in range(self.max_retries + 1):
            await self.authenticate()
            try:
                response = await self.http.get("https://api.zoom.us/v2" + path, params=params,
                                               headers={"Authorization": f"Bearer {self._token}"})
            except httpx.RequestError as exc:
                if attempt == self.max_retries:
                    raise ZoomAPIError(operation, None, f"Error de red: {type(exc).__name__}", retryable=True) from exc
                await asyncio.sleep(min(30, 2 ** attempt + random.random()))
                continue
            if response.status_code == 401 and not refreshed:
                self._token = None
                await self.authenticate(force=True)
                refreshed = True
                continue
            if response.status_code < 400:
                return response.json()
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                try: delay = float(retry_after) if retry_after else min(30, 2 ** attempt + random.random())
                except ValueError: delay = min(30, 2 ** attempt + random.random())
                LOG.warning("Zoom temporalmente no disponible", extra={"operation": operation, "status": response.status_code})
                await asyncio.sleep(max(0, delay))
                continue
            try:
                error_data = response.json()
                zoom_code = error_data.get("code")
                zoom_message = " ".join(str(error_data.get("message", "")).split())[:300]
                detail = f"; codigo Zoom {zoom_code}: {zoom_message}" if zoom_message else ""
            except (ValueError, AttributeError):
                detail = ""
            raise ZoomAPIError(operation, response.status_code,
                               f"Zoom respondio HTTP {response.status_code}{detail}", retryable=retryable)
        raise AssertionError("bucle de reintentos agotado")

    async def list_live_meetings(self) -> list[LiveMeeting]:
        meetings: list[LiveMeeting] = []
        token = ""
        while True:
            params: dict[str, Any] = {"type": "live", "page_size": 100}
            if token: params["next_page_token"] = token
            data = await self._get("/metrics/meetings", params, "list_live_meetings")
            for row in data.get("meetings", []):
                meeting_id = str(row.get("id") or row.get("meeting_number") or "")
                uuid = str(row.get("uuid") or "")
                if meeting_id and uuid:
                    meetings.append(LiveMeeting(meeting_id, uuid, row.get("start_time")))
            token = data.get("next_page_token") or ""
            if not token: return meetings

    async def get_meeting_name(self, meeting_id: str) -> str:
        data = await self._get(f"/meetings/{meeting_id}", {}, "get_meeting_name")
        topic = " ".join(str(data.get("topic", "")).split())
        return topic or "Reunion sin nombre"

    async def count_live_participants(self, uuid: str) -> int:
        count, token = 0, ""
        path = f"/metrics/meetings/{encode_uuid(uuid)}/participants"
        while True:
            params: dict[str, Any] = {"type": "live", "page_size": 100}
            if token: params["next_page_token"] = token
            data = await self._get(path, params, "count_live_participants")
            # Zoom conserva en la respuesta live entradas de personas que ya salieron
            # (y crea otra entrada si vuelven a entrar). Solo una entrada sin
            # leave_time representa una conexion actualmente activa. La sala de
            # espera no se considera dentro de la reunion.
            count += sum(
                1 for participant in data.get("participants", [])
                if not participant.get("leave_time")
                and participant.get("status", "in_meeting") == "in_meeting"
            )
            token = data.get("next_page_token") or ""
            if not token: return count

