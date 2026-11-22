import json
from urllib.parse import parse_qs

import httpx
import pytest

from zoom_monitor.zoom_client import ZoomAPIError, ZoomClient, encode_uuid


def response(status, data, headers=None):
    return httpx.Response(status, json=data, headers=headers or {})


@pytest.mark.asyncio
async def test_oauth_and_participant_pagination():
    calls = []
    async def handler(request):
        calls.append(request)
        if request.url.host == "zoom.us":
            assert request.url.params["grant_type"] == "account_credentials"
            return response(200, {"access_token": "secret-token", "expires_in": 3600})
        token = request.url.params.get("next_page_token")
        if not token: return response(200, {"participants": [{}] * 100, "next_page_token": "next"})
        return response(200, {"participants": [{}] * 37, "next_page_token": ""})
    client = ZoomClient("account", "client", "secret", transport=httpx.MockTransport(handler))
    assert await client.count_live_participants("abc") == 137
    assert len(calls) == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_count_excludes_departed_and_waiting_room_connections():
    async def handler(request):
        if request.url.host == "zoom.us":
            return response(200, {"access_token": "x", "expires_in": 3600})
        return response(200, {"participants": [
            {"status": "in_meeting"},
            {"status": "in_meeting", "leave_time": "2026-11-22T14:00:00Z"},
            {"status": "in_waiting_room"},
            {},
        ]})
    client = ZoomClient("a", "c", "s", transport=httpx.MockTransport(handler))
    assert await client.count_live_participants("u") == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_live_meeting_pagination():
    async def handler(request):
        if request.url.host == "zoom.us": return response(200, {"access_token": "x", "expires_in": 3600})
        if not request.url.params.get("next_page_token"):
            return response(200, {"meetings": [{"id": 123, "uuid": "u1"}], "next_page_token": "n"})
        return response(200, {"meetings": [{"id": "456", "uuid": "u2"}]})
    client = ZoomClient("a", "c", "s", transport=httpx.MockTransport(handler))
    assert [(m.meeting_id, m.uuid) for m in await client.list_live_meetings()] == [("123", "u1"), ("456", "u2")]
    await client.aclose()


@pytest.mark.asyncio
async def test_error_is_not_zero():
    async def handler(request):
        if request.url.host == "zoom.us": return response(200, {"access_token": "x"})
        return response(403, {"message": "forbidden"})
    client = ZoomClient("a", "c", "s", max_retries=0, transport=httpx.MockTransport(handler))
    with pytest.raises(ZoomAPIError) as caught: await client.count_live_participants("u")
    assert caught.value.status == 403
    await client.aclose()


def test_double_encoding():
    assert encode_uuid("/abc//def==") == "%252Fabc%252F%252Fdef%253D%253D"
    assert encode_uuid("abc/def==") == "abc%2Fdef%3D%3D"


@pytest.mark.asyncio
async def test_get_meeting_name():
    async def handler(request):
        if request.url.host == "zoom.us": return response(200, {"access_token": "x"})
        assert request.url.path == "/v2/meetings/123"
        return response(200, {"id": 123, "topic": "Reunion semanal"})
    client = ZoomClient("a", "c", "s", transport=httpx.MockTransport(handler))
    assert await client.get_meeting_name("123") == "Reunion semanal"
    await client.aclose()

