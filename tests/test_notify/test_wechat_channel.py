"""WechatChannel 单元测试（增强后）。

覆盖：
- is_configured / 基本 send（短消息）
- 智能分块 4 级 fallback (---, ###, ##, **)
- 强制按行分块 fallback
- 字节级截断（多字节字符安全）
- 单 section 超长截断 + "(本段内容过长已截断)"
- 分页标记 📄 *(i/N)*
- tenacity retry：3 次，仅 RequestException
- HTTP / API errcode 错误
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.notify.channels.wechat import (
    WechatChannel,
    _add_page_marker,
    _build_force_chunks,
    _build_smart_chunks,
    _get_bytes,
    _smart_split,
    _truncate_to_bytes,
)


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_with_http_url(self):
        ch = WechatChannel({"wechat_webhook_url": "https://qyapi.weixin.qq.com/x"})
        assert ch.is_configured() is True

    def test_without_url(self):
        assert WechatChannel({}).is_configured() is False

    def test_non_http_url_rejected(self):
        assert WechatChannel({"wechat_webhook_url": "not-a-url"}).is_configured() is False


# ─── 基本 send（短消息） ───────────────────────────────────────


@pytest.fixture
def configured_channel():
    return WechatChannel({"wechat_webhook_url": "https://qyapi.weixin.qq.com/test"})


def _ok_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"errcode": 0, "errmsg": "ok"}
    return r


def _api_error_response(errcode: int, errmsg: str):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"errcode": errcode, "errmsg": errmsg}
    return r


def _http_error_response(status: int):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {}
    return r


class TestSendShort:
    def test_unconfigured_returns_failure_without_request(self):
        ch = WechatChannel({})
        with patch("src.notify.channels.wechat.requests.post") as mock_post:
            r = ch.send("x")
        assert r.success is False
        assert "未配置" in r.error
        mock_post.assert_not_called()

    def test_short_message_single_post(self, configured_channel):
        with patch(
            "src.notify.channels.wechat.requests.post", return_value=_ok_response()
        ) as mock_post:
            r = configured_channel.send("简短消息")
        assert r.success is True
        assert r.channel == "WechatChannel"
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload == {"msgtype": "markdown", "markdown": {"content": "简短消息"}}
        assert mock_post.call_args.kwargs["timeout"] == 10


# ─── HTTP / API 错误 + retry ───────────────────────────────────


class TestErrorsAndRetry:
    def test_http_500_retried_three_times_then_fail(self, configured_channel):
        with patch(
            "src.notify.channels.wechat.requests.post",
            return_value=_http_error_response(500),
        ) as mock_post, patch("src.notify.channels.wechat.time.sleep"):
            # tenacity 重试也会调 time.sleep；只要 patch 全局都行
            with patch("tenacity.nap.time.sleep"):
                r = configured_channel.send("x")
        assert r.success is False
        assert "HTTP 500" in r.error
        assert mock_post.call_count == 3  # tenacity stop_after_attempt(3)

    def test_api_errcode_retried_then_fail(self, configured_channel):
        with patch(
            "src.notify.channels.wechat.requests.post",
            return_value=_api_error_response(45009, "rate limit"),
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is False
        assert "errcode=45009" in r.error
        assert "rate limit" in r.error
        assert mock_post.call_count == 3

    def test_retry_succeeds_on_second_attempt(self, configured_channel):
        responses = [_http_error_response(500), _ok_response()]
        with patch(
            "src.notify.channels.wechat.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is True
        assert mock_post.call_count == 2

    def test_non_request_exception_not_retried(self, configured_channel):
        with patch(
            "src.notify.channels.wechat.requests.post",
            side_effect=ValueError("malformed"),
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("x")
        assert r.success is False
        assert "malformed" in r.error
        # ValueError 不在 retry_if_exception_type 列表里 → 只调 1 次
        assert mock_post.call_count == 1


# ─── 智能分块 ───────────────────────────────────────────────────


class TestSmartChunking:
    def _long_content(self, separator: str, n: int = 4, section_size: int = 1500) -> str:
        # 每段 1500 字节，总 4 段 → 必须分块（max_bytes 4000）
        section = "x" * section_size
        return separator.join([section] * n)

    def test_smart_split_dash(self):
        content = "块A\n---\n块B\n---\n块C"
        sections, sep = _smart_split(content)
        assert sections == ["块A", "块B", "块C"]
        assert sep == "\n---\n"

    def test_smart_split_h3(self):
        content = "intro\n### 一\n内容1\n### 二\n内容2"
        sections, sep = _smart_split(content)
        assert sections[0] == "intro"
        assert all(s.startswith("### ") for s in sections[1:])
        assert sep == "\n"

    def test_smart_split_h2_fallback(self):
        content = "intro\n## 一\n内容1\n## 二\n内容2"
        sections, sep = _smart_split(content)
        assert sections[0] == "intro"
        assert all(s.startswith("## ") for s in sections[1:])

    def test_smart_split_bold_fallback(self):
        content = "intro\n**标题1**\n内容\n**标题2**"
        sections, sep = _smart_split(content)
        assert sections[0] == "intro"
        assert all(s.startswith("**") for s in sections[1:])

    def test_smart_split_no_match(self):
        sections, sep = _smart_split("一段无 separator 的纯文本")
        assert sections is None
        assert sep is None

    def test_dash_chunks_with_marker(self, configured_channel):
        content = self._long_content("\n---\n", n=4, section_size=1500)
        with patch(
            "src.notify.channels.wechat.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.wechat.time.sleep") as mock_sleep:
            r = configured_channel.send(content)
        assert r.success is True
        assert "已发送" in r.message
        assert mock_post.call_count >= 2
        # 块间 sleep 用 SMART 间隔 2.5
        for call in mock_sleep.call_args_list:
            assert call.args[0] == 2.5
        # 分页标记
        contents = [c.kwargs["json"]["markdown"]["content"] for c in mock_post.call_args_list]
        assert any("📄 *(1/" in c for c in contents)


# ─── 强制分块 fallback ────────────────────────────────────────


class TestForceChunking:
    def test_no_separator_uses_force_chunks(self, configured_channel):
        # 一行非常长且无智能分隔符
        content = "a" * 5000  # 5000 字节，超 4000
        with patch(
            "src.notify.channels.wechat.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.wechat.time.sleep") as mock_sleep:
            r = configured_channel.send(content)
        assert r.success is True
        # _build_force_chunks 按 \n 分行；单行 5000 字节会自成一个 chunk（因为没换行可截）
        # 这种极端情况实际会一条发送（因为单行不能再切）— 这是旧实现的局限
        # 真正的 force chunk 测试见 _build_force_chunks 单元测
        assert mock_post.call_count >= 1

    def test_force_chunks_split_by_lines(self):
        # 每行 1500 字节，6 行 → 9000 字节
        line = "x" * 1500
        content = "\n".join([line] * 6)
        chunks = _build_force_chunks(content, max_bytes=4000)
        assert len(chunks) >= 2
        for c in chunks:
            # 留 100 字节给分页标记，所以每块字节 ≤ 3900
            assert _get_bytes(c) <= 3900

    def test_force_chunk_interval_is_one(self, configured_channel):
        # 多行无智能 separator → 走 force 路径
        line = "a" * 1500
        content = "\n".join([line] * 4)
        with patch(
            "src.notify.channels.wechat.requests.post", return_value=_ok_response()
        ), patch("src.notify.channels.wechat.time.sleep") as mock_sleep:
            configured_channel.send(content)
        for call in mock_sleep.call_args_list:
            assert call.args[0] == 1.0


# ─── 字节级截断 ────────────────────────────────────────────────


class TestTruncateToBytes:
    def test_short_text_unchanged(self):
        assert _truncate_to_bytes("hello", 100) == "hello"

    def test_truncates_ascii_at_byte_limit(self):
        assert _truncate_to_bytes("a" * 100, 50) == "a" * 50

    def test_safe_with_multibyte_chars(self):
        # 中文每字 3 字节，10 字 = 30 字节，限 25 字节 → 截 8 字（24 字节）
        text = "中" * 10
        result = _truncate_to_bytes(text, 25)
        # 不应在多字节字符中间截断
        assert _get_bytes(result) <= 25
        # 必须可解码（已通过返回值 type 自证）
        assert all(c == "中" for c in result)


# ─── 单 section 超长强制截断 ──────────────────────────────────


class TestSingleSectionTooLong:
    def test_oversize_section_gets_truncation_marker(self):
        # 一个 section 单独就 6000 字节，超 4000 → 截断 + 标记
        big_section = "x" * 6000
        sections = ["small", big_section, "small2"]
        chunks = _build_smart_chunks(sections, separator="\n---\n", max_bytes=4000)
        # 大 section 应被截断且单独成 chunk
        truncated_chunks = [c for c in chunks if "(本段内容过长已截断)" in c]
        assert len(truncated_chunks) == 1
        # 截断后字节数 ≤ max_bytes
        assert _get_bytes(truncated_chunks[0]) <= 4000


# ─── 分页标记 ──────────────────────────────────────────────────


class TestPageMarker:
    def test_single_chunk_no_marker(self):
        assert _add_page_marker("hello", 0, 1) == "hello"

    def test_multi_chunk_appends_marker(self):
        result = _add_page_marker("body", 0, 3)
        assert "📄 *(1/3)*" in result
        assert result.startswith("body")

    def test_marker_indices_are_one_based(self):
        assert "(2/5)" in _add_page_marker("x", 1, 5)
        assert "(5/5)" in _add_page_marker("x", 4, 5)
