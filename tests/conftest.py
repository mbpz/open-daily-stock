"""pytest shared fixtures"""
import pytest
import os
from pathlib import Path

# 设置测试环境变量
os.environ["TESTING"] = "true"

# 设置默认语言为中文（测试期望中文界面）
from src.i18n import set_language
set_language("zh_CN")

@pytest.fixture
def test_env_file(tmp_path):
    """创建临时测试 .env 文件"""
    env_file = tmp_path / ".env"
    return env_file

@pytest.fixture
def mock_config():
    """Mock 配置对象"""
    from unittest.mock import MagicMock
    config = MagicMock()
    config.stock_list = ["000001", "600519"]
    config.openai_api_key = None
    config.gemini_api_key = None
    config.openai_base_url = None
    config.openai_model = "gpt-4o-mini"
    config.wechat_webhook_url = None
    config.feishu_webhook_url = None
    return config

@pytest.fixture
def sample_stock_data():
    """样例股票数据"""
    return {
        "000001": {
            "name": "平安银行",
            "price": 12.50,
            "change": 0.85,
            "volume": "15.2万",
        },
        "600519": {
            "name": "贵州茅台",
            "price": 1680.00,
            "change": -1.25,
            "volume": "3.2万",
        },
    }