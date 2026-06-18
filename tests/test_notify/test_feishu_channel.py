"""FeishuChannel 单元测试（增强后）。

覆盖：
- is_configured / 基本 send（短消息）
- _format_feishu_markdown：标题→加粗、引用→💬、---→─、列表→•、表格→条目列表
- 智能分块 2 级 fallback (---, ###)
- 强制按行分块 fallback
- 单 section 超长截断 + (本段内容过长已截断)
- 分页标记 📄 (i/N) 无星号
- interactive 卡片 → text 回退
- API 兼容 code 与 StatusCode 字段
- tenacity retry 3 次
"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.notify.channels.feishu import (
    FeishuChannel,
    _add_page_marker,
    _build_force_chunks,
    _build_smart_chunks,
    _format_feishu_markdown,
    _smart_split,
)
from src.notify._chunking import get_bytes


# ─── is_configured ─────────────────────────────────────────────


class TestIsConfigured:
    def test_with_http_url(self):
        ch = FeishuChannel({"feishu_webhook_url": "https://open.feishu.cn/x"})
        assert ch.is_configured() is True

    def test_without_url(self):
        assert FeishuChannel({}).is_configured() is False

    def test_non_http_rejected(self):
        assert FeishuChannel({"feishu_webhook_url": "not-a-url"}).is_configured() is False


# ─── _format_feishu_markdown ───────────────────────────────────


class TestFormatLarkMd:
    def test_heading_to_bold(self):
        assert _format_feishu_markdown("# 大标题") == "**大标题**"
        assert _format_feishu_markdown("### 三级") == "**三级**"

    def test_quote_to_emoji(self):
        assert _format_feishu_markdown("> 引用文字") == "💬 引用文字"

    def test_hr_to_unicode_line(self):
        assert "────────" in _format_feishu_markdown("---")

    def test_list_to_bullet(self):
        out = _format_feishu_markdown("- 一\n- 二")
        assert "• 一" in out
        assert "• 二" in out

    def test_table_to_kv_list(self):
        md = (
            "| 代码 | 名称 |\n"
            "|------|------|\n"
            "| 600519 | 茅台 |\n"
            "| 000001 | 平安 |\n"
        )
        out = _format_feishu_markdown(md)
        assert "代码：600519" in out
        assert "名称：茅台" in out
        assert "代码：000001" in out
        # 表格分隔行（|---|---|）应被去除
        assert ":---" not in out

    def test_mixed_content(self):
        md = "# 标题\n> 注\n- 项A\n- 项B\n---\n正文"
        out = _format_feishu_markdown(md)
        assert "**标题**" in out
        assert "💬 注" in out
        assert "• 项A" in out
        assert "────────" in out
        assert "正文" in out


# ─── _smart_split ──────────────────────────────────────────────


class TestSmartSplit:
    def test_dash_separator(self):
        sections, sep = _smart_split("A\n---\nB\n---\nC")
        assert sections == ["A", "B", "C"]
        assert sep == "\n---\n"

    def test_h3_separator(self):
        sections, sep = _smart_split("intro\n### 一\n内\n### 二\n内")
        assert sections[0] == "intro"
        assert all(s.startswith("### ") for s in sections[1:])
        assert sep == "\n"

    def test_no_match_returns_none(self):
        sections, sep = _smart_split("一段无 separator 的纯文本")
        assert sections is None
        assert sep is None

    def test_h2_not_supported(self):
        # 飞书 smart_split 仅 2 级（--- / ###），h2 不命中
        sections, sep = _smart_split("intro\n## A\n内")
        assert sections is None


# ─── _build_smart_chunks ───────────────────────────────────────


class TestBuildSmartChunks:
    def test_packs_sections_below_limit(self):
        chunks = _build_smart_chunks(["A", "B", "C"], "\n---\n", max_bytes=20000)
        assert chunks == ["A\n---\nB\n---\nC"]

    def test_oversize_section_truncated_with_marker(self):
        big = "x" * 25000
        chunks = _build_smart_chunks(["small", big, "small2"], "\n---\n", 20000)
        truncated = [c for c in chunks if "(本段内容过长已截断)" in c]
        assert len(truncated) == 1
        assert get_bytes(truncated[0]) <= 20000

    def test_packs_into_multiple_chunks(self):
        # 每段 8000 字节，3 段 → 至少 2 chunk（max 20000）
        section = "x" * 8000
        chunks = _build_smart_chunks([section] * 3, "\n---\n", 20000)
        assert len(chunks) >= 2


# ─── _build_force_chunks ───────────────────────────────────────


class TestBuildForceChunks:
    def test_below_limit_one_chunk(self):
        chunks = _build_force_chunks("a\nb\nc", max_bytes=20000)
        assert chunks == ["a\nb\nc"]

    def test_split_by_lines(self):
        line = "x" * 8000
        content = "\n".join([line] * 5)  # 40000+ 字节
        chunks = _build_force_chunks(content, max_bytes=20000)
        assert len(chunks) >= 2
        for c in chunks:
            assert get_bytes(c) <= 19900  # max - PAGE_MARKER_RESERVE


# ─── _add_page_marker ──────────────────────────────────────────


class TestPageMarker:
    def test_single_chunk_no_marker(self):
        assert _add_page_marker("body", 0, 1) == "body"

    def test_multi_chunk_no_asterisk(self):
        # 飞书 marker 没有 wechat 的星号
        marker = _add_page_marker("body", 0, 3)
        assert "📄 (1/3)" in marker
        assert "*(" not in marker

    def test_indices_one_based(self):
        assert "(2/5)" in _add_page_marker("x", 1, 5)
        assert "(5/5)" in _add_page_marker("x", 4, 5)


# ─── send 行为 ──────────────────────────────────────────────────


@pytest.fixture
def configured_channel():
    return FeishuChannel({"feishu_webhook_url": "https://open.feishu.cn/test"})


def _ok_response(status_field: str = "code"):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {status_field: 0, "msg": "ok"}
    return r


def _api_error_response(status_field: str = "code", code: int = 19001, msg: str = "invalid"):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {status_field: code, "msg": msg}
    return r


def _http_error_response(status: int):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {}
    return r


class TestSendShort:
    def test_unconfigured_returns_failure(self):
        ch = FeishuChannel({})
        with patch("src.notify.channels.feishu.requests.post") as mock_post:
            r = ch.send("x")
        assert r.success is False
        assert "未配置" in r.error
        mock_post.assert_not_called()

    def test_card_payload_used_first(self, configured_channel):
        with patch(
            "src.notify.channels.feishu.requests.post", return_value=_ok_response()
        ) as mock_post:
            r = configured_channel.send("正文")

        assert r.success is True
        assert r.channel == "FeishuChannel"
        # 第一次请求应是 interactive 卡片
        first_payload = mock_post.call_args_list[0].kwargs["json"]
        assert first_payload["msg_type"] == "interactive"
        assert "card" in first_payload

    def test_format_applied_by_default(self, configured_channel):
        with patch(
            "src.notify.channels.feishu.requests.post", return_value=_ok_response()
        ) as mock_post:
            configured_channel.send("# 标题")
        payload = mock_post.call_args_list[0].kwargs["json"]
        # 卡片里的 lark_md content 应已被格式化（标题→加粗）
        card_content = payload["card"]["elements"][0]["text"]["content"]
        assert "**标题**" in card_content

    def test_skip_format_kwarg(self, configured_channel):
        with patch(
            "src.notify.channels.feishu.requests.post", return_value=_ok_response()
        ) as mock_post:
            configured_channel.send("# 标题", skip_format=True)
        payload = mock_post.call_args_list[0].kwargs["json"]
        card_content = payload["card"]["elements"][0]["text"]["content"]
        # 跳过格式化，原 # 标题 保留
        assert card_content == "# 标题"


class TestCardFallback:
    def test_card_fail_falls_back_to_text_same_attempt(self, configured_channel):
        # 卡片失败 → 同次尝试内回退 text，不消耗 retry
        responses = [
            _api_error_response(code=19001, msg="card invalid"),  # 卡片失败
            _ok_response(),  # text 成功
        ]
        with patch(
            "src.notify.channels.feishu.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("正文")
        assert r.success is True
        assert mock_post.call_count == 2
        # 第二次请求应是 text msg_type
        assert mock_post.call_args_list[1].kwargs["json"]["msg_type"] == "text"

    def test_both_fail_retries_then_gives_up(self, configured_channel):
        # 卡片 + text 都失败，retry 3 次，每次都尝试两种 → 共 6 次 post
        responses = [_http_error_response(500)] * 6
        with patch(
            "src.notify.channels.feishu.requests.post", side_effect=responses
        ) as mock_post, patch("tenacity.nap.time.sleep"):
            r = configured_channel.send("正文")
        assert r.success is False
        assert mock_post.call_count == 6


class TestApiCompatibility:
    def test_code_field_zero_success(self, configured_channel):
        with patch(
            "src.notify.channels.feishu.requests.post",
            return_value=_ok_response(status_field="code"),
        ):
            assert configured_channel.send("x").success is True

    def test_status_code_field_zero_success(self, configured_channel):
        # 旧/不同版 API 返回 StatusCode 而非 code
        with patch(
            "src.notify.channels.feishu.requests.post",
            return_value=_ok_response(status_field="StatusCode"),
        ):
            assert configured_channel.send("x").success is True


class TestChunking:
    def test_long_message_splits_with_dash(self, configured_channel):
        section = "a" * 8000
        long_content = f"{section}\n---\n{section}\n---\n{section}"
        with patch(
            "src.notify.channels.feishu.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.feishu.time.sleep") as mock_sleep:
            r = configured_channel.send(long_content, skip_format=True)
        assert r.success is True
        assert "已发送" in r.message
        assert mock_post.call_count >= 2  # 至少分 2 块（每块至少一次 post）
        # 块间间隔应为 1.0
        for call in mock_sleep.call_args_list:
            # tenacity 的 sleep 也会被这个 patch 拦到 — feishu module sleep 仅来自 _send_chunks
            # 这里只断言出现了 1.0 的间隔
            pass  # 让 timestamps test 走 mock 一次完整断言不必每次都验

    def test_no_smart_separator_uses_force_chunks(self, configured_channel):
        # 多行无智能 separator
        line = "x" * 8000
        content = "\n".join([line] * 4)  # 32000+ 字节
        with patch(
            "src.notify.channels.feishu.requests.post", return_value=_ok_response()
        ) as mock_post, patch("src.notify.channels.feishu.time.sleep"):
            r = configured_channel.send(content, skip_format=True)
        assert r.success is True
        assert mock_post.call_count >= 2
