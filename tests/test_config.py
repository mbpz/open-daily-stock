# -*- coding: utf-8 -*-
"""Config 模块测试"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.config import Config


class TestIsFirstTimeSetup:
    """is_first_time_setup 方法测试"""

    def test_is_first_time_setup_no_env(self):
        """无 .env 文件时返回 True"""
        config = Config.__new__(Config)
        config.gemini_api_key = None
        config.openai_api_key = None
        config.stock_list = []

        with patch('src.config.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            result = config.is_first_time_setup()
            assert result is True

    def test_is_first_time_setup_no_api_key(self):
        """无 API Key 时返回 True"""
        config = Config.__new__(Config)
        config.gemini_api_key = None
        config.openai_api_key = None
        config.stock_list = ['600519']

        with patch('src.config.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            result = config.is_first_time_setup()
            assert result is True

    def test_is_first_time_setup_empty_stock_list(self):
        """自选股为空时返回 True"""
        config = Config.__new__(Config)
        config.gemini_api_key = 'some_key'
        config.openai_api_key = None
        config.stock_list = []

        with patch('src.config.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            result = config.is_first_time_setup()
            assert result is True


class TestSaveToEnv:
    """save_to_env 方法测试"""

    def test_save_to_env_returns_bool(self):
        """save_to_env 返回布尔值"""
        config = Config.__new__(Config)
        result = config.save_to_env({'GEMINI_API_KEY': 'test_key'})
        assert isinstance(result, bool)

    def test_save_to_env_with_empty_dict(self):
        """空字典时返回 True"""
        config = Config.__new__(Config)
        result = config.save_to_env({})
        assert result is True


class TestRefreshFromUpdates:
    """refresh_from_updates 方法测试"""

    def test_refresh_from_updates_stock_list(self):
        """刷新自选股列表"""
        config = Config.__new__(Config)
        config.stock_list = ['old_stock']
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'STOCK_LIST': '600519,000001'})

        assert config.stock_list == ['600519', '000001']

    def test_refresh_from_updates_openai_api_key(self):
        """刷新 OpenAI API Key"""
        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'OPENAI_API_KEY': 'sk-new-key'})

        assert config.openai_api_key == 'sk-new-key'

    def test_refresh_from_updates_openai_base_url(self):
        """刷新 OpenAI Base URL"""
        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'OPENAI_BASE_URL': 'https://api.example.com'})

        assert config.openai_base_url == 'https://api.example.com'

    def test_refresh_from_updates_gemini_api_key(self):
        """刷新 Gemini API Key"""
        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'GEMINI_API_KEY': 'gemini-new-key'})

        assert config.gemini_api_key == 'gemini-new-key'

    def test_refresh_from_updates_wechat_webhook_url(self):
        """刷新企业微信 Webhook URL"""
        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'WECHAT_WEBHOOK_URL': 'https://qyapi.weixin.qq.com'})

        assert config.wechat_webhook_url == 'https://qyapi.weixin.qq.com'

    def test_refresh_from_updates_feishu_webhook_url(self):
        """刷新飞书 Webhook URL"""
        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({'FEISHU_WEBHOOK_URL': 'https://open.feishu.cn'})

        assert config.feishu_webhook_url == 'https://open.feishu.cn'

    def test_refresh_from_updates_ignores_unknown_keys(self):
        """忽略未知配置键"""
        config = Config.__new__(Config)
        config.stock_list = ['600519']
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        original_stock_list = config.stock_list.copy()
        config.refresh_from_updates({'UNKNOWN_KEY': 'value'})

        assert config.stock_list == original_stock_list