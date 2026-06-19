"""CustomChannel 单元测试（增强后）。

覆盖：
- URL 识别：DingTalk / Discord / Slack / Bark / 通用
- _build_payload 各服务格式
- _chunk_markdown_by_bytes：3 级 fallback (--- / ### / 按行)
- _split_by_bytes 字节硬切兜底
- 多 URL 循环 + "至少一个成功"语义
- DingTalk 分块路径
- Bearer Token header
- json.dumps(ensure_ascii=False) 中文不转义
- tenacity retry 3 次
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.notify.channels.custom import (
    CustomChannel,
    _build_payload,
    _chunk_markdown_by_bytes,
    _is_bark_webhook,
    _is_dingtalk_webhook,
    _is_discord_webhook,
    _is_slack_webhook,
    _split_by_bytes,
)
from src.notify._chunking import get_bytes


# ─── URL 识别 ──────────────────────────────────────────────────


class TestUrlDetection:
    def test_dingtalk_detection(self):
        assert _is_dingtalk_webhook("https://oapi.dingtalk.com/robot/send?token=x")
        assert _is_dingtalk_webhook("https://my.dingtalk.com/x")
        assert not _is_dingtalk_webhook("https://discord.com/x")
        assert not _is_dingtalk_webhook("")
        assert not _is_dingtalk_webhook(None)

    def test_discord_detection(self):
        assert _is_discord_webhook("https://discord.com/api/webhooks/x")
        assert _is_discord_webhook("https://discordapp.com/api/webhooks/x")
        assert not _is_discord_webhook("https://discord.com/channels/x")  # 非 webhooks 路径

    def test_slack_detection(self):
        assert _is_slack_webhook("https://hooks.slack.com/services/x")

    def test_bark_detection(self):
        assert _is_bark_webhook("https://api.day.app/xxx/title/body")


# ─── _build_payload ────────────────────────────────────────────


class TestBuildPayload:
    def test_dingtalk_uses_msgtype_markdown(self):
        p = _build_payload("https://oapi.dingtalk.com/robot/send", "正文")
        assert p["msgtype"] == "markdown"
        assert p["markdown"]["title"] == "股票分析报告"
        assert p["markdown"]["text"] == "正文"

    def test_discord_payload_short(self):
        p = _build_payload("https://discord.com/api/webhooks/x", "短文")
        assert p == {"content": "短文"}

    def test_discord_payload_truncated_at_1900(self):
        long_text = "x" * 3000
        p = _build_payload("https://discord.com/api/webhooks/x", long_text)
        assert p["content"].endswith("...")
        assert len(p["content"]) <= 1900 + 3

    def test_slack_payload(self):
        p = _build_payload("https://hooks.slack.com/services/x", "hi")
        assert p == {"text": "hi", "mrkdwn": True}

    def test_bark_payload_truncated(self):
        p = _build_payload("https://api.day.app/xxx", "x" * 5000)
        assert p["title"] == "股票分析报告"
        assert len(p["body"]) == 4000
        assert p["group"] == "stock"

    def test_generic_payload_multikey(self):
        p = _build_payload("https://my-custom-webhook.example.com/x", "hello")
        # 多键兼容大多数服务
        assert p["text"] == "hello"
        assert p["content"] == "hello"
        assert p["message"] == "hello"
        assert p["body"] == "hello"


# ─── _chunk_markdown_by_bytes ──────────────────────────────────


class TestChunkMarkdownByBytes:
    def test_dash_separator(self):
        section = "x" * 8000
        content = f"{section}\n---\n{section}\n---\n{section}"
        chunks = _chunk_markdown_by_bytes(content, max_bytes=18500)
        assert len(chunks) >= 2
        for c in chunks:
            assert get_bytes(c) <= 18500 + 100  # 容许小冗余

    def test_h3_separator(self):
        section = "x" * 8000
        content = f"intro\n### A\n{section}\n### B\n{section}"
        chunks = _chunk_markdown_by_bytes(content, max_bytes=15000)
        assert len(chunks) >= 2

    def test_no_separator_falls_back_to_lines(self):
        # 多行无智能分隔
        line = "x" * 5000
        content = "\n".join([line] * 5)
        chunks = _chunk_markdown_by_bytes(content, max_bytes=10000)
        assert len(chunks) >= 2

    def test_single_oversize_section_split_by_bytes(self):
        # 单段就 30000 字节，无 separator → 走 _split_by_bytes
        content = "x" * 30000
        chunks = _chunk_markdown_by_bytes(content, max_bytes=10000)
        assert len(chunks) >= 3
        for c in chunks:
            assert get_bytes(c) <= 10000

    def test_chinese_safe(self):
        # 中文每字 3 字节，确保不在多字节字符中间截断
        content = "中" * 5000  # 15000 字节
        chunks = _chunk_markdown_by_bytes(content, max_bytes=2000)
        for c in chunks:
            assert all(ch == "中" for ch in c)


class TestSplitByBytes:
    def test_short_input(self):
        assert _split_by_bytes("hi", 100) == ["hi"]

    def test_long_split_into_pieces(self):
        text = "x" * 1000
        parts = _split_by_bytes(text, 100)
        assert len(parts) == 10
        assert "".join(parts) == text


# ─── send: 单 URL 通用路径 ─────────────────────────────────────


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.text = ""
    return r


def _fail_response(status: int):
    r = MagicMock()
    r.status_code = status
    r.text = ""
    return r


class TestIsConfigured:
    def test_empty_list(self):
        assert CustomChannel({"custom_webhook_urls": []}).is_configured() is False

    def test_with_url(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        assert ch.is_configured() is True

    def test_string_wrapped_to_list(self):
        ch = CustomChannel({"custom_webhook_urls": "https://x.com"})
        # 单字符串包装成 list
        assert ch.webhook_urls == ["https://x.com"]


class TestSendGeneric:
    def test_unconfigured(self):
        ch = CustomChannel({})
        with patch("src.notify.channels.custom.requests.post") as mock_post:
            r = ch.send("x")
        assert r.success is False
        mock_post.assert_not_called()

    def test_generic_url_uses_multikey_payload(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://my.webhook.example/x"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = ch.send("正文")
        assert r.success is True
        # body 是 ensure_ascii=False 后 utf-8 编码
        body = mock_post.call_args.kwargs["data"]
        decoded = body.decode("utf-8")
        payload = json.loads(decoded)
        assert payload["text"] == "正文"
        assert payload["content"] == "正文"
        assert payload["message"] == "正文"
        assert payload["body"] == "正文"

    def test_chinese_not_escaped_to_unicode(self):
        # ensure_ascii=False — body 含中文字符而非 \uXXXX
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            ch.send("茅台")
        body = mock_post.call_args.kwargs["data"]
        # 字节序列含 utf-8 编码的"茅台"，不含 \\u 转义
        assert "茅".encode("utf-8") in body
        assert b"\\u" not in body

    def test_headers_include_user_agent(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            ch.send("hi")
        headers = mock_post.call_args.kwargs["headers"]
        assert "Content-Type" in headers
        assert "User-Agent" in headers

    def test_bearer_token_added_when_present(self):
        ch = CustomChannel(
            {
                "custom_webhook_urls": ["https://x.com"],
                "custom_webhook_bearer_token": "TOK",
            }
        )
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            ch.send("hi")
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer TOK"

    def test_bearer_token_absent_no_auth_header(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            ch.send("hi")
        headers = mock_post.call_args.kwargs["headers"]
        assert "Authorization" not in headers


class TestMultiUrl:
    def test_at_least_one_success_returns_success(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://a.com", "https://b.com"]})
        # URL 1: 一次 ok；URL 2: retry × 3 都失败
        responses = [
            _ok_response(),  # URL 1 first attempt success
            _fail_response(500),  # URL 2 attempt 1
            _fail_response(500),  # URL 2 attempt 2
            _fail_response(500),  # URL 2 attempt 3
        ]
        with patch(
            "src.notify.channels.custom.requests.post", side_effect=responses
        ), patch("tenacity.nap.time.sleep"):
            r = ch.send("hi")
        assert r.success is True
        assert "1/2" in r.message

    def test_all_fail_returns_failure(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://a.com", "https://b.com"]})
        with patch(
            "src.notify.channels.custom.requests.post",
            return_value=_fail_response(500),
        ), patch("tenacity.nap.time.sleep"):
            r = ch.send("hi")
        assert r.success is False
        assert "所有" in r.error or "2 个" in r.error


class TestRetry:
    def test_http_500_retries_three_times(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_fail_response(500)
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = ch.send("x")
        assert r.success is False
        assert mock_post.call_count == 3

    def test_recovers_on_retry(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://x.com"]})
        responses = [_fail_response(500), _ok_response()]
        with patch(
            "src.notify.channels.custom.requests.post", side_effect=responses
        ), patch("tenacity.nap.time.sleep"):
            r = ch.send("x")
        assert r.success is True


# ─── DingTalk 分块路径 ────────────────────────────────────────


class TestDingtalk:
    def test_short_dingtalk_one_chunk(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://oapi.dingtalk.com/robot/send"]})
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.custom.time.sleep"), patch(
            "tenacity.nap.time.sleep"
        ):
            r = ch.send("短文")
        assert r.success is True
        # 验证 payload 是 dingtalk markdown 格式
        body = mock_post.call_args.kwargs["data"].decode("utf-8")
        payload = json.loads(body)
        assert payload["msgtype"] == "markdown"
        assert payload["markdown"]["title"] == "股票分析报告"

    def test_long_dingtalk_chunked_with_marker(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://oapi.dingtalk.com/robot/send"]})
        section = "x" * 8000
        long_content = f"{section}\n---\n{section}\n---\n{section}"
        with patch(
            "src.notify.channels.custom.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.custom.time.sleep"), patch(
            "tenacity.nap.time.sleep"
        ):
            r = ch.send(long_content)
        assert r.success is True
        assert mock_post.call_count >= 2
        # 至少一次 payload 含分页 marker
        bodies = [c.kwargs["data"].decode("utf-8") for c in mock_post.call_args_list]
        assert any("📄 *(1/" in b for b in bodies)

    def test_partial_dingtalk_chunk_failure_returns_failure(self):
        ch = CustomChannel({"custom_webhook_urls": ["https://oapi.dingtalk.com/x"]})
        section = "x" * 8000
        long_content = f"{section}\n---\n{section}\n---\n{section}"
        # 让第二批失败（注意 retry × 3）
        responses = (
            [_ok_response()]  # chunk 1 success
            + [_fail_response(500)] * 3  # chunk 2 retry × 3 失败
            + [_ok_response()]  # chunk 3 success
        )
        with patch(
            "src.notify.channels.custom.requests.post", side_effect=responses
        ), patch("src.notify.channels.custom.time.sleep"), patch("tenacity.nap.time.sleep"):
            r = ch.send(long_content)
        # send_dingtalk_chunked 仅在全部 chunk 都成功时返回 True；只有 1 个 url 全失败 →
        # send 整体失败
        assert r.success is False
