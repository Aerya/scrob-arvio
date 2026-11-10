import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
from routers.webhooks import _maybe_bingebase_scrobble
from models.base import MediaType


class BingebaseScrobbleTests(unittest.IsolatedAsyncioTestCase):
    async def test_maybe_bingebase_scrobble_success(self):
        settings = SimpleNamespace(
            bingebase_scrobble=True,
            bingebase_webhook_url="https://bingebase.com/api/webhook",
            bingebase_api_key="secret-token",
        )
        media = SimpleNamespace(
            media_type=MediaType.movie,
            title="American Assassin",
            tmdb_id=398181,
            imdb_id="tt3700804",
            tmdb_data=None,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        result = await _maybe_bingebase_scrobble(
            settings, media, "stop", 1.0, client=mock_client, is_push=True
        )

        self.assertTrue(result)
        mock_client.post.assert_called_once()

    async def test_maybe_bingebase_scrobble_http_error(self):
        settings = SimpleNamespace(
            bingebase_scrobble=True,
            bingebase_webhook_url="https://bingebase.com/api/webhook",
            bingebase_api_key=None,
        )
        media = SimpleNamespace(
            media_type=MediaType.movie,
            title="Elite Force",
            tmdb_id=12345,
            imdb_id=None,
            tmdb_data=None,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized Token"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp

        result = await _maybe_bingebase_scrobble(
            settings, media, "stop", 1.0, client=mock_client, is_push=True
        )

        self.assertFalse(result)

    async def test_maybe_bingebase_scrobble_exception(self):
        settings = SimpleNamespace(
            bingebase_scrobble=True,
            bingebase_webhook_url="https://bingebase.com/api/webhook",
            bingebase_api_key=None,
        )
        media = SimpleNamespace(
            media_type=MediaType.movie,
            title="Test Movie",
            tmdb_id=1,
            imdb_id=None,
            tmdb_data=None,
        )

        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        result = await _maybe_bingebase_scrobble(
            settings, media, "stop", 1.0, client=mock_client, is_push=True
        )

        self.assertFalse(result)


class BingebaseScheduleSettingsTests(unittest.TestCase):
    def test_interval_can_be_disabled_and_cannot_create_busy_loop(self):
        from schemas import UserSettings
        from pydantic import ValidationError
        self.assertIsNone(UserSettings(bingebase_auto_push_interval=None).bingebase_auto_push_interval)
        self.assertEqual(UserSettings(bingebase_auto_push_interval=1).bingebase_auto_push_interval, 1)
        with self.assertRaises(ValidationError):
            UserSettings(bingebase_auto_push_interval=0)
