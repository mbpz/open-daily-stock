# -*- coding: utf-8 -*-
"""NotificationService facade 集成测试（新契约：send / send_to_channel / is_available）。"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_config_wechat_only():
    """仅配置企业微信。"""
    config = MagicMock()
    config.wechat_webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"
    config.feishu_webhook_url = None
    config.email_sender = None
    config.email_password = None
    config.email_receivers = []
    config.telegram_bot_token = None
    config.telegram_chat_id = None
    config.pushover_user_key = None
    config.pushover_api_token = None
    config.pushplus_token = None
    config.custom_webhook_urls = []
    config.custom_webhook_bearer_token = None
    config.discord_bot_token = None
    config.discord_main_channel_id = None
    config.discord_webhook_url = None
    config.discord_channel_id = None
    config.wechat_max_bytes = 4000
    config.feishu_max_bytes = 20000
    return config


@pytest.fixture
def mock_config_none():
    """全未配置。"""
    config = MagicMock()
    config.wechat_webhook_url = None
    config.feishu_webhook_url = None
    config.email_sender = None
    config.email_password = None
    config.email_receivers = []
    config.telegram_bot_token = None
    config.telegram_chat_id = None
    config.pushover_user_key = None
    config.pushover_api_token = None
    config.pushplus_token = None
    config.custom_webhook_urls = []
    config.custom_webhook_bearer_token = None
    config.discord_bot_token = None
    config.discord_main_channel_id = None
    config.discord_webhook_url = None
    config.discord_channel_id = None
    config.wechat_max_bytes = 4000
    config.feishu_max_bytes = 20000
    return config


class TestNotificationServiceFacade:
    def test_import_from_notification_still_works(self):
        """向后兼容：从 src.notification import 仍可用。"""
        from src.notify import NotificationService, BotMessage, NotificationChannel
        assert NotificationService is not None
        assert BotMessage is not None
        assert NotificationChannel is not None

    def test_is_available_with_wechat_only(self, mock_config_wechat_only):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_wechat_only):
            svc = NotificationService()
        assert svc.is_available() is True
        assert "wechat" in svc.get_available_channels()

    def test_not_available_with_none(self, mock_config_none):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_none):
            svc = NotificationService()
        assert svc.is_available() is False
        assert svc.get_available_channels() == []

    def test_send_with_wechat_makes_http_request(self, mock_config_wechat_only):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_wechat_only):
            svc = NotificationService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

        with patch("requests.post", return_value=mock_response) as mock_post:
            results = svc.send("测试内容")

        assert len(results) >= 1
        assert all(r.success for r in results)
        mock_post.assert_called()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["msgtype"] == "markdown"
        assert "测试内容" in payload["markdown"]["content"]

    def test_send_to_channel_wechat(self, mock_config_wechat_only):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_wechat_only):
            svc = NotificationService()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

        with patch("requests.post", return_value=mock_response):
            r = svc.send_to_channel("wechat", "hi")
        assert r.success is True

    def test_send_to_channel_unknown_returns_failure(self, mock_config_wechat_only):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_wechat_only):
            svc = NotificationService()
        r = svc.send_to_channel("nonexistent", "hi")
        assert r.success is False
        assert "不存在" in r.error or "未配置" in r.error

    def test_send_when_none_configured_logs_warning(self, mock_config_none):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_none):
            svc = NotificationService()
        results = svc.send("hello")
        assert results == []

    def test_has_channel(self, mock_config_wechat_only):
        from src.notify.service import NotificationService

        with patch("src.notify.service.get_config", return_value=mock_config_wechat_only):
            svc = NotificationService()
        assert svc.has_channel("wechat") is True
        assert svc.has_channel("feishu") is False

    def test_get_notification_service_singleton(self):
        from src.notify.singletons import get_notification_service

        with patch("src.notify.service.get_config", return_value=MagicMock(
            wechat_webhook_url=None, feishu_webhook_url=None,
            email_sender=None, email_password=None, email_receivers=[],
            telegram_bot_token=None, telegram_chat_id=None,
            pushover_user_key=None, pushover_api_token=None,
            pushplus_token=None, custom_webhook_urls=[],
            custom_webhook_bearer_token=None, discord_bot_token=None,
            discord_main_channel_id=None, discord_webhook_url=None,
            discord_channel_id=None, wechat_max_bytes=4000, feishu_max_bytes=20000,
        )):
            svc = get_notification_service()
        assert svc is not None
        assert svc.is_available() is False
