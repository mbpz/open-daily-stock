"""PushPlusChannel 单元测试。"""
from unittest.mock import MagicMock, patch

import pytest

from src.notify.channels.pushplus import PushPlusChannel


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_with_token(self):
        assert PushPlusChannel({"pushplus_token": "tok"}).is_configured() is True

    def test_without_token(self):
        assert PushPlusChannel({}).is_configured() is False

    def test_empty_token(self):
        assert PushPlusChannel({"pushplus_token": ""}).is_configured() is False


# ─── send 行为 ──────────────────────────────────────────────────


@pytest.fixture
def configured_channel():
    return PushPlusChannel({"pushplus_token": "TOKEN"})


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"code": 200, "msg": "ok"}
    return r


def _api_error_response(msg: str):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"code": 999, "msg": msg}
    return r


def _http_error_response(status: int):
    r = MagicMock()
    r.status_code = status
    return r


class TestSend:
    def test_unconfigured_returns_failure_without_request(self):
        ch = PushPlusChannel({})
        with patch("src.notify.channels.pushplus.requests.post") as mock_post:
            result = ch.send("x")
        assert result.success is False
        assert "未配置" in result.error
        mock_post.assert_not_called()

    def test_default_payload(self, configured_channel):
        with patch(
            "src.notify.channels.pushplus.requests.post", return_value=_ok_response()
        ) as mock_post:
            result = configured_channel.send("正文")

        assert result.success is True
        assert result.channel == "PushPlusChannel"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["token"] == "TOKEN"
        assert payload["content"] == "正文"
        assert payload["template"] == "markdown"
        assert "股票分析报告" in payload["title"]
        assert mock_post.call_args.kwargs["timeout"] == 10

    def test_custom_title_and_template(self, configured_channel):
        with patch(
            "src.notify.channels.pushplus.requests.post", return_value=_ok_response()
        ) as mock_post:
            configured_channel.send("x", title="自定义", template="html")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["title"] == "自定义"
        assert payload["template"] == "html"

    def test_http_error_returns_failure(self, configured_channel):
        with patch(
            "src.notify.channels.pushplus.requests.post",
            return_value=_http_error_response(503),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "HTTP 503" in result.error

    def test_api_error_code_returns_failure(self, configured_channel):
        with patch(
            "src.notify.channels.pushplus.requests.post",
            return_value=_api_error_response("token expired"),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "token expired" in result.error

    def test_timeout_returns_failure(self, configured_channel):
        import requests

        with patch(
            "src.notify.channels.pushplus.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "超时" in result.error

    def test_unexpected_exception(self, configured_channel):
        with patch(
            "src.notify.channels.pushplus.requests.post",
            side_effect=RuntimeError("boom"),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "boom" in result.error
