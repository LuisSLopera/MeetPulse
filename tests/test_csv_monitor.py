import csv

import pytest

from zoom_monitor.csv_monitor import CsvMonitor, default_csv_path
from zoom_monitor.zoom_client import LiveMeeting


class FakeClient:
    def __init__(self): self.calls = 0
    async def list_live_meetings(self):
        self.calls += 1
        return [LiveMeeting("123", "uuid")]
    async def count_live_participants(self, uuid): return 115


@pytest.mark.asyncio
async def test_each_run_creates_csv_with_local_time_and_can_stop(tmp_path):
    output = tmp_path / "run.csv"
    client = FakeClient()
    monitor = CsvMonitor(client, "123", "Reunion de prueba", output,
                         poll_seconds=0.01, sample_seconds=300)

    original_count = client.count_live_participants
    async def count_and_stop(uuid):
        result = await original_count(uuid)
        monitor.stop()
        return result
    client.count_live_participants = count_and_stop

    await monitor.run()
    with output.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    assert len(rows) == 1
    assert rows[0]["meeting_id"] == "123"
    assert rows[0]["participantes"] == "115"
    assert rows[0]["nombre_reunion"] == "Reunion de prueba"
    assert len(rows[0]["fecha"].split("-")) == 3
    assert len(rows[0]["hora"].split(":")) == 3
    assert "session_uuid" not in rows[0]


def test_default_path_is_per_execution(tmp_path):
    first = default_csv_path("123", tmp_path)
    first.touch()
    second = default_csv_path("123", tmp_path)
    assert second != first

