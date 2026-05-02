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

    def test_save_to_env_writes_file_content(self, tmp_path):
        """验证 save_to_env 实际写入文件内容"""
        from unittest.mock import MagicMock, patch, PropertyMock, mock_open

        env_file = tmp_path / '.env'
        env_file_str = str(env_file)

        config = Config.__new__(Config)
        config.stock_list = []
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        # Create mock_env_path that will be returned by Path() / '.env'
        mock_env_path = MagicMock()
        mock_env_path.exists.return_value = False

        # Create mock_parent that will be returned by Path().parent
        mock_parent = MagicMock()
        mock_parent.__truediv__.return_value = mock_env_path

        # Use PropertyMock for .parent so it returns mock_parent
        mock_path_instance = MagicMock()
        type(mock_path_instance).parent = PropertyMock(return_value=mock_parent)

        mock_path = MagicMock(return_value=mock_path_instance)

        # Custom open that writes to env_file when called with the mock path
        original_open = open
        def custom_open(path, mode='r', *args, **kwargs):
            if path is mock_env_path or str(path) == env_file_str:
                return original_open(env_file, mode, *args, **kwargs)
            return original_open(path, mode, *args, **kwargs)

        with patch('src.config.Path', mock_path), \
             patch('src.config.dotenv_values', return_value={}), \
             patch('src.config.open', side_effect=custom_open):
            result = config.save_to_env({'STOCK_LIST': '000001,600519'})

        assert result is True
        assert env_file.exists(), ".env 文件应该存在"
        content = env_file.read_text(encoding='utf-8')
        assert 'STOCK_LIST=000001,600519' in content


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

    def test_refresh_from_updates_multiple_attributes(self):
        """刷新多个配置属性"""
        config = Config.__new__(Config)
        config.stock_list = ['old_stock']
        config.gemini_api_key = None
        config.openai_api_key = None
        config.openai_base_url = None
        config.openai_model = 'gpt-4o-mini'
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None

        config.refresh_from_updates({
            'STOCK_LIST': '600519,000001',
            'OPENAI_API_KEY': 'sk-new-key',
            'GEMINI_API_KEY': 'gemini-new-key',
            'WECHAT_WEBHOOK_URL': 'https://qyapi.weixin.qq.com'
        })

        assert config.stock_list == ['600519', '000001']
        assert config.openai_api_key == 'sk-new-key'
        assert config.gemini_api_key == 'gemini-new-key'
        assert config.wechat_webhook_url == 'https://qyapi.weixin.qq.com'