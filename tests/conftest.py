import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_httpx_client():
    client = AsyncMock()
    client.post = AsyncMock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def completed_download_old():
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "test-123",
        "name": "old-torrent.torrent",
        "created_at": (now - timedelta(days=15)).isoformat(),
        "download_state": "completed",
    }


@pytest.fixture
def completed_download_recent():
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "test-456",
        "name": "recent-torrent.torrent",
        "created_at": (now - timedelta(days=5)).isoformat(),
        "download_state": "completed",
    }


@pytest.fixture
def cached_download_old():
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "test-789",
        "name": "cached-file.torrent",
        "created_at": (now - timedelta(days=20)).isoformat(),
        "download_state": "cached",
    }


@pytest.fixture
def downloading_stalled():
    return {
        "id": "test-stalled",
        "name": "stalled-download.torrent",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "download_state": "downloading",
        "download_speed": 0,
        "progress": 0.5,
        "eta": 100,
    }


@pytest.fixture
def downloading_slow():
    return {
        "id": "test-slow",
        "name": "slow-download.torrent",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "download_state": "downloading",
        "download_speed": 1000,
        "progress": 0.1,
        "eta": 5000,
    }


@pytest.fixture
def downloading_active():
    return {
        "id": "test-active",
        "name": "active-download.torrent",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "download_state": "downloading",
        "download_speed": 5000,
        "progress": 0.3,
        "eta": 300,
    }


@pytest.fixture
def uploading_expired():
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "test-upload-expired",
        "name": "uploading-file.torrent",
        "created_at": (now - timedelta(hours=2)).isoformat(),
        "download_state": "uploading",
    }


@pytest.fixture
def uploading_valid():
    now = datetime.now(tz=timezone.utc)
    return {
        "id": "test-upload-valid",
        "name": "uploading-file.torrent",
        "created_at": (now - timedelta(minutes=30)).isoformat(),
        "download_state": "uploading",
    }


@pytest.fixture
def queued_item():
    return {
        "id": "test-queued",
        "name": "queued-file.torrent",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def unknown_state_download():
    return {
        "id": "test-unknown",
        "name": "unknown-state.torrent",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "download_state": "some_weird_state",
    }


@pytest.fixture
def mock_responses():
    def _make_responses(torrents=None, webdl=None, queued_list=None):
        torrents = torrents or []
        webdl = webdl or []
        queued_list = queued_list or []

        responses = [
            MagicMock(
                status_code=200,
                json=lambda: {"data": torrents},
            ),
            MagicMock(
                status_code=200,
                json=lambda: {"data": webdl},
            ),
            MagicMock(
                status_code=200,
                json=lambda: {"data": queued_list},
            ),
        ]
        return responses

    return _make_responses
