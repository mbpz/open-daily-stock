"""TelegramChannel 单元测试（增强后）。"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.notify.channels.telegram import (
    TelegramChannel,
    _convert_to_telegram_markdown,
    _split_chunks,
)


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_with_token_and_chat_id(self):
        ch = TelegramChannel({"telegram_bot_token": "T", "telegram_chat_id": "123"})
        assert ch.is_configured() is True

    def test_missing_token(self):
        assert TelegramChannel({"telegram_chat_id": "1"}).is_configured() is False

    def test_missing_chat_id(self):
        assert TelegramChannel({"telegram_bot_token": "T"}).is_configured() is False


# ─── _convert_to_telegram_markdown ─────────────────────────────


class TestMarkdownConversion:
    def test_strips_headings(self):
        assert _convert_to_telegram_markdown("# 大\n## 中") == "大\n中"

    def test_double_star_to_single_star(self):
        assert _convert_to_telegram_markdown("**粗**") == "*粗*"

    def test_escapes_brackets_and_parens(self):
        out = _convert_to_telegram_markdown("[link](url)")
        assert out == r"\[link\]\(url\)"

    def test_combined(self):
        md = "# 标题\n**粗**与[斜](url)"
        out = _convert_to_telegram_markdown(md)
        assert "标题" in out
        assert "*粗*" in out
        assert r"\[斜\]" in out
        assert r"\(url\)" in out


# ─── _split_chunks ─────────────────────────────────────────────


class TestSplitChunks:
    def test_short_one_chunk(self):
        assert _split_chunks("a\nb", 4096) == ["a\nb"]

    def test_split_by_dash(self):
        # 每段 2000 字符；3 段超 4096 → 至少 2 块
        section = "x" * 2000
        content = f"{section}\n---\n{section}\n---\n{section}"
        chunks = _split_chunks(content, 4096)
        assert len(chunks) >= 2

    def test_no_separator_returns_single_oversize_chunk(self):
        # 旧行为：无 \n---\n 分隔时整段返回（让 API 拒收）
        long = "x" * 5000
        chunks = _split_chunks(long, 4096)
        assert chunks == [long]


# ─── send 行为 ──────────────────────────────────────────────────


@pytest.fixture
def configured_channel():
    return TelegramChannel({"telegram_bot_token": "BOT", "telegram_chat_id": "CHAT"})


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"ok": True}
    return r


def _api_error_response(description: str):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"ok": False, "description": description}
    return r


def _http_error_response(status: int):
    r = MagicMock()
    r.status_code = status
    r.text = ""
    r.json.return_value = {}
    return r


class TestSendShort:
    def test_unconfigured_no_request(self):
        ch = TelegramChannel({})
        with patch("src.notify.channels.telegram.requests.post") as mock_post:
            r = ch.send("x")
        assert r.success is False
        assert "未配置" in r.error
        mock_post.assert_not_called()

    def test_short_message_sends_markdown(self, configured_channel):
        with patch(
            "src.notify.channels.telegram.requests.post", return_value=_ok_response()
        ) as mock_post:
            r = configured_channel.send("**粗**")

        assert r.success is True
        assert r.channel == "TelegramChannel"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["chat_id"] == "CHAT"
        assert payload["parse_mode"] == "Markdown"
        assert payload["disable_web_page_preview"] is True
        # **粗** → *粗*
        assert payload["text"] == "*粗*"
        # URL 应为 sendMessage
        assert "sendMessage" in mock_post.call_args.args[0]


class TestParseFallback:
    def test_parse_error_retries_as_plain_text(self, configured_channel):
        # 第一次返回 parse error → 同请求内回退纯文本
        responses = [
            _api_error_response("Bad Request: can't parse entities"),
            _ok_response(),
        ]
        with patch(
            "src.notify.channels.telegram.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("# 标题")

        assert r.success is True
        assert mock_post.call_count == 2
        # 第二次应是纯文本（无 parse_mode）
        plain_payload = mock_post.call_args_list[1].kwargs["json"]
        assert "parse_mode" not in plain_payload
        # 纯文本应是原始内容（未转换）
        assert plain_payload["text"] == "# 标题"

    def test_non_parse_error_does_not_fallback(self, configured_channel):
        # 非 parse 错误 → 直接 raise，触发 tenacity retry
        with patch(
            "src.notify.channels.telegram.requests.post",
            return_value=_api_error_response("chat not found"),
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is False
        assert "chat not found" in r.error
        assert mock_post.call_count == 3  # tenacity stop_after_attempt(3)

    def test_plain_fallback_also_fails(self, configured_channel):
        # parse 失败 + 纯文本也失败 → raise 让 retry
        responses = [
            _api_error_response("can't parse"),
            _api_error_response("plain also fail"),
        ] * 3  # 3 retry × 2 请求 = 6
        with patch(
            "src.notify.channels.telegram.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is False
        assert mock_post.call_count == 6


class TestRetry:
    def test_http_500_retries_three_times(self, configured_channel):
        with patch(
            "src.notify.channels.telegram.requests.post",
            return_value=_http_error_response(500),
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is False
        assert "HTTP 500" in r.error
        assert mock_post.call_count == 3

    def test_recovers_on_second_attempt(self, configured_channel):
        responses = [_http_error_response(500), _ok_response()]
        with patch(
            "src.notify.channels.telegram.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is True
        assert mock_post.call_count == 2


class TestChunking:
    def test_long_message_splits_with_dash(self, configured_channel):
        section = "x" * 2000
        long_content = f"{section}\n---\n{section}\n---\n{section}"
        with patch(
            "src.notify.channels.telegram.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send(long_content)
        assert r.success is True
        assert "已发送" in r.message
        assert mock_post.call_count >= 2
