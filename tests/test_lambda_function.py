import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from lambda_function import (
    should_delete_download,
    should_delete_queued,
    delete_res,
    async_lambda_handler,
)


class TestShouldDeleteDownload:
    def test_completed_expired(self, completed_download_old):
        assert should_delete_download(completed_download_old) is True

    def test_completed_valid(self, completed_download_recent):
        assert should_delete_download(completed_download_recent) is False

    def test_cached_expired(self, cached_download_old):
        assert should_delete_download(cached_download_old) is True

    def test_downloading_stalled(self, downloading_stalled):
        assert should_delete_download(downloading_stalled) is True

    def test_downloading_slow(self, downloading_slow):
        assert should_delete_download(downloading_slow) is True

    def test_downloading_active(self, downloading_active):
        assert should_delete_download(downloading_active) is False

    def test_uploading_expired(self, uploading_expired):
        assert should_delete_download(uploading_expired) is True

    def test_uploading_valid(self, uploading_valid):
        assert should_delete_download(uploading_valid) is False

    def test_unknown_state(self, unknown_state_download):
        assert should_delete_download(unknown_state_download) is True


class TestShouldDeleteQueued:
    def test_always_returns_true(self, queued_item):
        assert should_delete_queued(queued_item) is True

    def test_with_any_queued_data(self):
        assert should_delete_queued({"id": "1", "name": "test"}) is True


class TestDeleteRes:
    @pytest.mark.asyncio
    async def test_delete_res(self):
        mock_client = AsyncMock()
        with patch("lambda_function.client", mock_client):
            await delete_res("torrent_id", "123", "/torrents/controltorrent")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/torrents/controltorrent"
        assert call_args[1]["json"] == {"torrent_id": "123", "operation": "delete"}

    @pytest.mark.asyncio
    async def test_delete_res_webdl(self):
        mock_client = AsyncMock()
        with patch("lambda_function.client", mock_client):
            await delete_res("webdl_id", "456", "/webdl/controlwebdownload")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/webdl/controlwebdownload"
        assert call_args[1]["json"] == {"webdl_id": "456", "operation": "delete"}

    @pytest.mark.asyncio
    async def test_delete_res_queued(self):
        mock_client = AsyncMock()
        with patch("lambda_function.client", mock_client):
            await delete_res("queued_id", "789", "/queued/controlqueued")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "/queued/controlqueued"
        assert call_args[1]["json"] == {"queued_id": "789", "operation": "delete"}


class TestAsyncLambdaHandler:
    @pytest.mark.asyncio
    async def test_deletes_old_completed_torrent(
        self, mock_httpx_client, mock_responses, completed_download_old
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[completed_download_old],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_keeps_recent_completed_torrent(
        self, mock_httpx_client, mock_responses, completed_download_recent
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[completed_download_recent],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_stalled_download(
        self, mock_httpx_client, mock_responses, downloading_stalled
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[downloading_stalled],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletes_slow_download(
        self, mock_httpx_client, mock_responses, downloading_slow
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[downloading_slow],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_keeps_active_download(
        self, mock_httpx_client, mock_responses, downloading_active
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[downloading_active],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_queued_items(
        self, mock_httpx_client, mock_responses, queued_item
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[],
                webdl=[],
                queued_list=[queued_item],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_deletes_multiple_resource_types(
        self,
        mock_httpx_client,
        mock_responses,
        completed_download_old,
        downloading_stalled,
        queued_item,
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[completed_download_old, downloading_stalled],
                webdl=[],
                queued_list=[queued_item],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_handles_api_error(
        self, mock_httpx_client, mock_responses, completed_download_old
    ):
        error_response = MagicMock(
            status_code=500,
            content=b"Internal Server Error",
        )
        mock_httpx_client.get = AsyncMock(
            side_effect=[
                error_response,
                MagicMock(status_code=200, json=lambda: {"data": []}),
                MagicMock(status_code=200, json=lambda: {"data": []}),
            ]
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_deletes_webdl(
        self, mock_httpx_client, mock_responses, cached_download_old
    ):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[],
                webdl=[cached_download_old],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_client(self, mock_httpx_client, mock_responses):
        mock_httpx_client.get = AsyncMock(
            side_effect=mock_responses(
                torrents=[],
                webdl=[],
                queued_list=[],
            )
        )
        mock_httpx_client.post = AsyncMock()

        with patch("lambda_function.client", mock_httpx_client):
            await async_lambda_handler()

        mock_httpx_client.aclose.assert_called_once()
