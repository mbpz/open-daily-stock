# tests/test_service_client.py
import pytest
from unittest.mock import patch, MagicMock

class TestServiceClient:
    def test_client_initialization(self):
        """ServiceClient 可以初始化并连接 DataService"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            client = ServiceClient()
            assert client._proc is not None
            mock_popen.assert_called_once()

    def test_hello(self):
        """ServiceClient.hello() 返回版本信息"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout.readline.return_value = '{"status": "ok", "version": "0.3.0"}'
            mock_popen.return_value = mock_proc

            client = ServiceClient()
            resp = client.hello()
            assert resp["version"] == "0.3.0"

    def test_get_markets(self):
        """ServiceClient.get_markets() 返回行情数据"""
        from src.service_client import ServiceClient
        with patch('subprocess.Popen') as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdout.readline.return_value = '{"status": "ok", "data": []}'
            mock_popen.return_value = mock_proc

            client = ServiceClient()
            markets = client.get_markets()
            assert isinstance(markets, list)