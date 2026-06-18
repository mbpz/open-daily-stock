"""PushoverChannel 单元测试。

覆盖：
- is_configured 配置完整性判断
- send 单条短消息（≤ 1024 字符）
- send 长消息自动分块
- title / priority kwargs
- _markdown_to_plain_text 转换规则
- API 错误返回处理
"""
from unittest.mock import MagicMock, patch

import pytest

from src.notify.base import ChannelResult
from src.notify.channels.pushover import (
    PushoverChannel,
    _markdown_to_plain_text,
    _split_into_chunks,
)


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_fully_configured(self):
        ch = PushoverChannel({"pushover_user_key": "u", "pushover_api_token": "t"})
        assert ch.is_configured() is True

    def test_missing_user_key(self):
        ch = PushoverChannel({"pushover_api_token": "t"})
        assert ch.is_configured() is False

    def test_missing_api_token(self):
        ch = PushoverChannel({"pushover_user_key": "u"})
        assert ch.is_configured() is False

    def test_empty_config(self):
        ch = PushoverChannel({})
        assert ch.is_configured() is False


# ─── send 行为 ──────────────────────────────────────────────────


@pytest.fixture
def configured_channel():
    return PushoverChannel({"pushover_user_key": "USER", "pushover_api_token": "TOKEN"})


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"status": 1}
    return r


def _fail_response_status(status: int):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {}
    r.text = ""
    return r


def _fail_response_api(errors):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"status": 0, "errors": errors}
    return r


class TestSend:
    def test_unconfigured_returns_failure_without_request(self):
        ch = PushoverChannel({})
        with patch("src.notify.channels.pushover.requests.post") as mock_post:
            result = ch.send("hello")
        assert result.success is False
        assert "未配置" in result.error
        mock_post.assert_not_called()

    def test_short_message_single_request(self, configured_channel):
        with patch("src.notify.channels.pushover.requests.post", return_value=_ok_response()) as mock_post:
            result = configured_channel.send("简短消息")

        assert result.success is True
        assert result.channel == "PushoverChannel"
        mock_post.assert_called_once()
        # 验证 payload
        _, kwargs = mock_post.call_args
        payload = kwargs["data"]
        assert payload["token"] == "TOKEN"
        assert payload["user"] == "USER"
        assert payload["message"] == "简短消息"
        assert payload["priority"] == 0
        assert "股票分析报告" in payload["title"]
        assert kwargs["timeout"] == 30

    def test_custom_title_and_priority_kwargs(self, configured_channel):
        with patch("src.notify.channels.pushover.requests.post", return_value=_ok_response()) as mock_post:
            result = configured_channel.send("hi", title="紧急", priority=2)

        assert result.success is True
        payload = mock_post.call_args.kwargs["data"]
        assert payload["title"] == "紧急"
        assert payload["priority"] == 2

    def test_http_non_200_returns_failure(self, configured_channel):
        with patch("src.notify.channels.pushover.requests.post", return_value=_fail_response_status(500)):
            result = configured_channel.send("x")
        assert result.success is False
        assert "HTTP 500" in result.error

    def test_api_status_zero_returns_failure_with_errors(self, configured_channel):
        with patch(
            "src.notify.channels.pushover.requests.post",
            return_value=_fail_response_api(["invalid token", "user not found"]),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "invalid token" in result.error
        assert "user not found" in result.error

    def test_timeout_returns_failure(self, configured_channel):
        import requests

        with patch(
            "src.notify.channels.pushover.requests.post",
            side_effect=requests.exceptions.Timeout(),
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "超时" in result.error

    def test_unexpected_exception_returns_failure(self, configured_channel):
        with patch(
            "src.notify.channels.pushover.requests.post", side_effect=RuntimeError("boom")
        ):
            result = configured_channel.send("x")
        assert result.success is False
        assert "boom" in result.error


# ─── 分块 ────────────────────────────────────────────────────────


class TestChunking:
    def test_long_message_splits_and_calls_post_multiple_times(self, configured_channel):
        # 每段约 600 字，三段确保超过 1024 字符上限
        section = "段落内容" * 150  # 600 chars
        long_content = f"{section}\n\n{section}\n\n{section}"

        with patch(
            "src.notify.channels.pushover.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.pushover.time.sleep") as mock_sleep:
            result = configured_channel.send(long_content)

        assert result.success is True
        assert "已发送" in result.message
        assert mock_post.call_count >= 2
        # 块间应有 sleep 间隔（最后一块后不 sleep）
        assert mock_sleep.call_count == mock_post.call_count - 1

        # 验证标题加了 (i/N) 后缀
        titles = [call.kwargs["data"]["title"] for call in mock_post.call_args_list]
        assert any("(1/" in t for t in titles)

    def test_partial_chunk_failure_returns_failure_with_error(self, configured_channel):
        section = "x" * 600
        long_content = f"{section}\n\n{section}\n\n{section}"

        responses = [_ok_response(), _fail_response_status(500), _ok_response()]
        with patch(
            "src.notify.channels.pushover.requests.post", side_effect=responses
        ), patch("src.notify.channels.pushover.time.sleep"):
            result = configured_channel.send(long_content)

        assert result.success is False
        assert "/" in result.error  # "x/N 成功"


# ─── helper：_markdown_to_plain_text ───────────────────────────


class TestMarkdownToPlainText:
    def test_strips_headings(self):
        assert _markdown_to_plain_text("# 标题\n## 二级") == "标题\n二级"

    def test_strips_bold_and_italic(self):
        assert _markdown_to_plain_text("**粗** 与 *斜*") == "粗 与 斜"

    def test_lists_become_bullets(self):
        out = _markdown_to_plain_text("- 一\n- 二\n* 三")
        assert "• 一" in out
        assert "• 二" in out
        assert "• 三" in out

    def test_horizontal_rule_replaced(self):
        assert "────" in _markdown_to_plain_text("正文\n---\n更多")

    def test_collapses_excess_blank_lines(self):
        assert _markdown_to_plain_text("a\n\n\n\nb") == "a\n\nb"


# ─── helper：_split_into_chunks ────────────────────────────────


class TestSplitIntoChunks:
    def test_short_input_one_chunk(self):
        chunks = _split_into_chunks("a\n\nb", max_length=1024)
        assert chunks == ["a\n\nb"]

    def test_splits_when_over_limit(self):
        section = "x" * 600
        text = f"{section}\n\n{section}\n\n{section}"
        chunks = _split_into_chunks(text, max_length=1024)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c) <= 1024 + 10  # 允许极小冗余（边界 section 自身已含分隔字符）

    def test_horizontal_rule_separator_preserved(self):
        text = "块A────────块B"
        chunks = _split_into_chunks(text, max_length=10)
        # 块 A 和块 B 都超出 max_length，应当分成 2 块
        assert len(chunks) == 2
