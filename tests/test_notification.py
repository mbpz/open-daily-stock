# -*- coding: utf-8 -*-
"""NotificationService 模块测试"""
import pytest
from unittest.mock import patch, MagicMock, Mock


class TestWechatWebhookFormat:
    """企业微信 Webhook 格式验证测试"""

    def test_wechat_webhook_format(self):
        """验证企业微信 Webhook 请求格式正确"""
        from src.notification import NotificationService

        mock_config = MagicMock()
        mock_config.wechat_webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"
        mock_config.feishu_webhook_url = None
        mock_config.email_sender = None
        mock_config.email_password = None
        mock_config.email_receivers = []
        mock_config.telegram_bot_token = None
        mock_config.telegram_chat_id = None
        mock_config.pushover_user_key = None
        mock_config.pushover_api_token = None
        mock_config.pushplus_token = None
        mock_config.custom_webhook_urls = []
        mock_config.custom_webhook_bearer_token = None
        mock_config.discord_bot_token = None
        mock_config.discord_main_channel_id = None
        mock_config.discord_webhook_url = None
        mock_config.wechat_max_bytes = 4000
        mock_config.feishu_max_bytes = 20000

        with patch('src.notification.get_config', return_value=mock_config):
            service = NotificationService()

        test_content = "测试消息内容"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errcode": 0, "errmsg": "ok"}

        with patch('requests.post', return_value=mock_response) as mock_post:
            result = service.send_to_wechat(test_content)

        assert result is True
        mock_post.assert_called_once()

        call_args = mock_post.call_args
        assert call_args[0][0] == mock_config.wechat_webhook_url
        payload = call_args[1]['json']
        assert payload['msgtype'] == 'markdown'
        assert 'markdown' in payload
        assert payload['markdown']['content'] == test_content


class TestFeishuWebhookFormat:
    """飞书 Webhook 格式验证测试"""

    def test_feishu_webhook_format(self):
        """验证飞书 Webhook 请求格式正确"""
        from src.notification import NotificationService

        mock_config = MagicMock()
        mock_config.wechat_webhook_url = None
        mock_config.feishu_webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/test-hook"
        mock_config.email_sender = None
        mock_config.email_password = None
        mock_config.email_receivers = []
        mock_config.telegram_bot_token = None
        mock_config.telegram_chat_id = None
        mock_config.pushover_user_key = None
        mock_config.pushover_api_token = None
        mock_config.pushplus_token = None
        mock_config.custom_webhook_urls = []
        mock_config.custom_webhook_bearer_token = None
        mock_config.discord_bot_token = None
        mock_config.discord_main_channel_id = None
        mock_config.discord_webhook_url = None
        mock_config.wechat_max_bytes = 4000
        mock_config.feishu_max_bytes = 20000

        with patch('src.notification.get_config', return_value=mock_config):
            service = NotificationService()

        test_content = "测试消息内容"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": 0, "msg": "success"}

        with patch('requests.post', return_value=mock_response) as mock_post:
            result = service.send_to_feishu(test_content)

        assert result is True
        mock_post.assert_called_once()

        call_args = mock_post.call_args
        assert call_args[0][0] == mock_config.feishu_webhook_url
        payload = call_args[1]['json']
        assert payload['msg_type'] == 'interactive'
        assert 'card' in payload


class TestNotificationSkipWhenDisabled:
    """未配置时跳过通知测试"""

    def test_notification_skip_when_disabled(self):
        """验证未配置 Webhook 时跳过发送"""
        from src.notification import NotificationService

        mock_config = MagicMock()
        mock_config.wechat_webhook_url = None
        mock_config.feishu_webhook_url = None
        mock_config.email_sender = None
        mock_config.email_password = None
        mock_config.email_receivers = []
        mock_config.telegram_bot_token = None
        mock_config.telegram_chat_id = None
        mock_config.pushover_user_key = None
        mock_config.pushover_api_token = None
        mock_config.pushplus_token = None
        mock_config.custom_webhook_urls = []
        mock_config.custom_webhook_bearer_token = None
        mock_config.discord_bot_token = None
        mock_config.discord_main_channel_id = None
        mock_config.discord_webhook_url = None
        mock_config.wechat_max_bytes = 4000
        mock_config.feishu_max_bytes = 20000

        with patch('src.notification.get_config', return_value=mock_config):
            service = NotificationService()

        with patch('requests.post') as mock_post:
            wechat_result = service.send_to_wechat("测试消息")
            feishu_result = service.send_to_feishu("测试消息")

        assert wechat_result is False
        assert feishu_result is False
        mock_post.assert_not_called()