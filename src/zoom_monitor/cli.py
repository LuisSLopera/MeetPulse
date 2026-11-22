from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from dotenv import load_dotenv

from .config import ConfigurationError, Settings
from .csv_monitor import CsvMonitor, default_csv_path
from .zoom_client import ZoomAPIError, ZoomClient


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="zoom-monitor", description="Monitor de participantes Zoom")
    command.add_argument("--env-file", default=".env", help="Archivo dotenv (predeterminado: .env)")
    command.add_argument("command", nargs="?", choices=["validate"],
                         help="Use validate para comprobar credenciales y permisos")
    return command


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level, logging.INFO), stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def load_meeting_names(client: ZoomClient, meeting_ids: tuple[str, ...]) -> list[tuple[str, str]]:
    meetings = []
    for meeting_id in meeting_ids:
        meetings.append((meeting_id, await client.get_meeting_name(meeting_id)))
    return meetings


def choose_meeting(meetings: list[tuple[str, str]]) -> tuple[str, str] | None:
    print("\nReuniones configuradas:\n")
    for number, (meeting_id, name) in enumerate(meetings, start=1):
        print(f"  {number}. {name} (ID: {meeting_id})")
    print("  0. Salir")
    while True:
        try:
            choice = input("\nSeleccione la reunion que desea monitorear: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nOperacion cancelada.")
            return None
        if choice == "0": return None
        if choice.isdigit() and 1 <= int(choice) <= len(meetings):
            return meetings[int(choice) - 1]
        print("Opcion invalida. Escriba el numero mostrado en el menu.")


async def validate(settings: Settings) -> int:
    async with ZoomClient(settings.account_id, settings.client_id, settings.client_secret,
                          timeout=settings.request_timeout, max_retries=settings.max_retries) as client:
        try:
            await client.authenticate()
            meetings = await load_meeting_names(client, settings.meeting_ids)
            await client.list_live_meetings()
        except ZoomAPIError as exc:
            print(json.dumps({"ok": False, "operation": exc.operation, "http_status": exc.status,
                              "message": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps({"ok": True, "oauth": "valid", "meetings": [
            {"id": meeting_id, "name": name} for meeting_id, name in meetings
        ]}, ensure_ascii=False))
        return 0


async def interactive_monitor(settings: Settings) -> int:
    async with ZoomClient(settings.account_id, settings.client_id, settings.client_secret,
                          timeout=settings.request_timeout, max_retries=settings.max_retries) as client:
        try:
            meetings = await load_meeting_names(client, settings.meeting_ids)
        except ZoomAPIError as exc:
            print(f"No fue posible consultar los nombres: {exc}", file=sys.stderr)
            if exc.status in (400, 403):
                print("Verifique el scope meeting:read:meeting:admin en la app de Zoom.", file=sys.stderr)
            return 2
        selected = choose_meeting(meetings)
        if selected is None: return 0
        meeting_id, meeting_name = selected
        monitor = CsvMonitor(client, meeting_id, meeting_name, default_csv_path(meeting_id),
                             settings.poll_seconds, settings.sample_seconds)
        try:
            await monitor.run()
        except KeyboardInterrupt:
            print("\nMonitoreo detenido por el usuario.")
        return 0


def main(argv: list[str] | None = None) -> int:
    # PowerShell heredado puede anunciar una pagina de codigos distinta; forzar
    # UTF-8 evita que los nombres de reuniones con tildes se muestren corruptos.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    load_dotenv(args.env_file, override=False)
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        print(f"Error de configuracion: {exc}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    if args.command == "validate": return asyncio.run(validate(settings))
    return asyncio.run(interactive_monitor(settings))


if __name__ == "__main__":
    raise SystemExit(main())
