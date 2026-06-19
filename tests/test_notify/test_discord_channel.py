"""DiscordChannel 单元测试（Webhook + Bot 双模式）。"""
from unittest.mock import MagicMock, patch

import pytest

from src.notify.channels.discord import DiscordChannel


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_webhook_only(self):
        ch = DiscordChannel({"discord_webhook_url": "https://discord.com/x"})
        assert ch.is_configured() is True

    def test_bot_only(self):
        ch = DiscordChannel(
            {"discord_bot_token": "T", "discord_main_channel_id": "123"}
        )
        assert ch.is_configured() is True

    def test_bot_alt_field_name(self):
        # 兼容 discord_channel_id（不是 discord_main_channel_id）
        ch = DiscordChannel({"discord_bot_token": "T", "discord_channel_id": "456"})
        assert ch.is_configured() is True

    def test_neither(self):
        assert DiscordChannel({}).is_configured() is False

    def test_bot_missing_channel_id(self):
        ch = DiscordChannel({"discord_bot_token": "T"})
        assert ch.is_configured() is False

    def test_invalid_webhook_url(self):
        ch = DiscordChannel({"discord_webhook_url": "not-a-url"})
        # 单独 webhook 失败但若有 bot 仍 ok；这里两个都缺
        assert ch.is_configured() is False


# ─── send: Webhook 模式 ────────────────────────────────────────


def _ok_response(status: int = 204):
    r = MagicMock()
    r.status_code = status
    r.text = ""
    return r


def _fail_response(status: int):
    r = MagicMock()
    r.status_code = status
    r.text = "rate limited"
    return r


@pytest.fixture
def webhook_only():
    return DiscordChannel({"discord_webhook_url": "https://discord.com/api/webhooks/x"})


class TestSendWebhook:
    def test_unconfigured_returns_failure(self):
        ch = DiscordChannel({})
        with patch("src.notify.channels.discord.requests.post") as mock_post:
            r = ch.send("x")
        assert r.success is False
        assert "未配置" in r.error
        mock_post.assert_not_called()

    def test_webhook_204_success(self, webhook_only):
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_ok_response(204)
        ) as mock_post:
            r = webhook_only.send("hi")
        assert r.success is True
        assert r.message == "Discord Webhook 已发送"
        # payload 含 username + avatar_url
        payload = mock_post.call_args.kwargs["json"]
        assert payload["content"] == "hi"
        assert "username" in payload
        assert "avatar_url" in payload

    def test_webhook_200_also_success(self, webhook_only):
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_ok_response(200)
        ):
            assert webhook_only.send("hi").success is True

    def test_webhook_non_2xx_failure(self, webhook_only):
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_fail_response(429)
        ):
            r = webhook_only.send("hi")
        assert r.success is False
        assert "429" in r.error

    def test_webhook_timeout(self, webhook_only):
        import requests

        with patch(
            "src.notify.channels.discord.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            r = webhook_only.send("x")
        assert r.success is False
        assert "超时" in r.error


# ─── send: Bot 模式 ────────────────────────────────────────────


@pytest.fixture
def bot_only():
    return DiscordChannel(
        {"discord_bot_token": "BOT_TOKEN", "discord_main_channel_id": "999"}
    )


class TestSendBot:
    def test_bot_uses_v10_api(self, bot_only):
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_ok_response(200)
        ) as mock_post:
            r = bot_only.send("hi")
        assert r.success is True
        assert r.message == "Discord Bot 已发送"

        url = mock_post.call_args.args[0]
        assert "discord.com/api/v10/channels/999/messages" in url

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bot BOT_TOKEN"
        assert headers["Content-Type"] == "application/json"

        payload = mock_post.call_args.kwargs["json"]
        assert payload == {"content": "hi"}

    def test_bot_201_treated_as_failure(self, bot_only):
        # 旧实现严格只接受 200
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_fail_response(201)
        ):
            r = bot_only.send("hi")
        assert r.success is False

    def test_bot_4xx_failure(self, bot_only):
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_fail_response(401)
        ):
            r = bot_only.send("hi")
        assert r.success is False
        assert "401" in r.error


# ─── 双配置时 webhook 优先 ─────────────────────────────────────


class TestPreference:
    def test_webhook_preferred_over_bot(self):
        ch = DiscordChannel(
            {
                "discord_webhook_url": "https://discord.com/api/webhooks/W",
                "discord_bot_token": "BOT",
                "discord_main_channel_id": "999",
            }
        )
        with patch(
            "src.notify.channels.discord.requests.post", return_value=_ok_response(204)
        ) as mock_post:
            ch.send("hi")
        # 仅一次请求；URL 应是 webhook（不是 v10/channels/...）
        assert mock_post.call_count == 1
        url = mock_post.call_args.args[0]
        assert "webhooks/W" in url
        assert "v10/channels" not in url
