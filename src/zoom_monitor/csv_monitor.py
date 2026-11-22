from __future__ import annotations

import asyncio
import csv
import logging
import signal
from datetime import datetime
from pathlib import Path

from .zoom_client import ZoomAPIError, ZoomClient

LOG = logging.getLogger(__name__)


class CsvMonitor:
    """Monitor interactivo: una ejecucion produce exactamente un CSV."""

    def __init__(self, client: ZoomClient, meeting_id: str, meeting_name: str, output: Path,
                 poll_seconds: float = 20, sample_seconds: float = 300):
        self.client = client
        self.meeting_id = meeting_id
        self.meeting_name = meeting_name
        self.output = output
        self.poll_seconds = poll_seconds
        self.sample_seconds = sample_seconds
        self.stop_event = asyncio.Event()
        self._session_uuid: str | None = None
        self._next_sample_monotonic: float | None = None

    def stop(self) -> None:
        self.stop_event.set()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop)
            except (NotImplementedError, RuntimeError):
                pass

        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open("x", encoding="utf-8-sig", newline="", buffering=1) as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(["fecha", "hora", "meeting_id", "nombre_reunion", "participantes", "estado"])
            handle.flush()
            print(f"Monitoreando: {self.meeting_name} ({self.meeting_id})")
            print(f"Archivo: {self.output.resolve()}")
            print("Presione Ctrl+C para detener el monitoreo.")

            while not self.stop_event.is_set():
                cycle_started = loop.time()
                try:
                    meetings = [m for m in await self.client.list_live_meetings()
                                if m.meeting_id == self.meeting_id]
                    if len(meetings) > 1:
                        LOG.warning("Zoom devolvio multiples sesiones para el mismo Meeting ID")
                    elif not meetings:
                        if self._session_uuid:
                            print("La reunion termino. Monitoreo finalizado.")
                            return
                        LOG.info("Esperando que la reunion se encuentre activa")
                    else:
                        meeting = meetings[0]
                        if meeting.uuid != self._session_uuid:
                            self._session_uuid = meeting.uuid
                            self._next_sample_monotonic = cycle_started
                            print("Reunion activa detectada.")
                        if (self._next_sample_monotonic is None or
                                cycle_started >= self._next_sample_monotonic):
                            count = await self.client.count_live_participants(meeting.uuid)
                            local_time = datetime.now().astimezone()
                            date_text = local_time.strftime("%Y-%m-%d")
                            time_text = local_time.strftime("%H:%M:%S")
                            writer.writerow([date_text, time_text, self.meeting_id,
                                             self.meeting_name, count, "ok"])
                            handle.flush()
                            print(f"{date_text} {time_text} | participantes: {count}")
                            self._next_sample_monotonic = cycle_started + self.sample_seconds
                except ZoomAPIError as exc:
                    # Los fallos se muestran, pero nunca se escriben como cero participantes.
                    LOG.error("Consulta Zoom fallida: %s", exc)

                delay = max(0.0, self.poll_seconds - (loop.time() - cycle_started))
                try:
                    await asyncio.wait_for(self.stop_event.wait(), delay)
                except TimeoutError:
                    pass
        print("Monitoreo detenido.")


def default_csv_path(meeting_id: str, directory: Path = Path("exports")) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    candidate = directory / f"reunion_{meeting_id}_{stamp}.csv"
    suffix = 1
    while candidate.exists():
        candidate = directory / f"reunion_{meeting_id}_{stamp}_{suffix}.csv"
        suffix += 1
    return candidate

