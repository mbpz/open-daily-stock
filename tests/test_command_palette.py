# -*- coding: utf-8 -*-
"""P5-7: Command Palette 测试

测试共享命令注册表、模糊搜索、命令执行、最近使用追踪。
"""

import pytest
from typing import Dict

from src.shared.commands import (
    Command, CATEGORY_META,
    get_command_registry, get_commands_by_category,
    search_commands, find_command,
    record_recent_command, get_recent_commands,
    execute_command, register_handler,
    _score_exact, _score_prefix, _score_fuzzy, _score_chinese_match,
)


# ============================================================
# Command Registry Tests
# ============================================================

class TestCommandRegistry:
    """测试命令注册表的结构和完整性。"""

    def test_registry_contains_all_required_commands(self):
        """注册表包含规范要求的全部 25 个命令。"""
        registry = get_command_registry()
        required_ids = [
            "markets.refresh", "markets.add_stock",
            "analyze.quick", "analyze.deep", "analyze.stream",
            "portfolio.add", "portfolio.view",
            "trading.buy", "trading.sell", "trading.summary",
            "screener.open", "financials.open",
            "strategies.list", "strategies.import", "strategies.export",
            "backtest.run",
            "config.theme_toggle", "config.language", "config.alerts",
            "nav.markets", "nav.tasks", "nav.analyze",
            "nav.config", "nav.logs", "nav.strategies",
        ]
        for cmd_id in required_ids:
            assert cmd_id in registry, f"Missing command: {cmd_id}"

    def test_command_structure(self):
        """验证 Command 数据类结构正确。"""
        cmd = find_command("markets.refresh")
        assert cmd is not None
        assert cmd.id == "markets.refresh"
        assert cmd.name == "刷新行情"
        assert len(cmd.description) > 0
        assert cmd.category == "markets"
        assert isinstance(cmd.keywords, list)
        assert len(cmd.keywords) > 0

    def test_all_commands_have_valid_category(self):
        """所有命令的 category 都在 CATEGORY_META 中定义。"""
        valid_categories = set(CATEGORY_META.keys())
        for cmd in get_command_registry().values():
            assert cmd.category in valid_categories, \
                f"Command '{cmd.id}' has unknown category '{cmd.category}'"

    def test_no_duplicate_command_ids(self):
        """注册表中没有重复的命令 ID。"""
        registry = get_command_registry()
        ids = list(registry.keys())
        assert len(ids) == len(set(ids))

    def test_commands_grouped_by_category(self):
        """get_commands_by_category 按类别正确分组。"""
        grouped = get_commands_by_category()
        assert "markets" in grouped
        assert "analysis" in grouped
        assert "navigation" in grouped
        # 验证特定命令在对应类别中
        nav_ids = {cmd.id for cmd in grouped["navigation"]}
        assert "nav.markets" in nav_ids
        assert "nav.tasks" in nav_ids


class TestFindCommand:
    """测试 find_command 查找单个命令。"""

    def test_find_existing_command(self):
        cmd = find_command("markets.refresh")
        assert cmd is not None
        assert cmd.id == "markets.refresh"

    def test_find_nonexistent_command(self):
        cmd = find_command("nonexistent.action")
        assert cmd is None


# ============================================================
# Fuzzy Search Scoring Tests
# ============================================================

class TestScoreExact:
    """测试 _score_exact（精确子串匹配）。"""

    def test_exact_substring_match(self):
        score = _score_exact("refresh", "markets.refresh")
        assert score > 0

    def test_no_match_returns_zero(self):
        score = _score_exact("xyz", "markets.refresh")
        assert score == 0.0

    def test_case_insensitive_match(self):
        score = _score_exact("MARKET", "markets.refresh")
        assert score > 0

    def test_earlier_matches_score_higher(self):
        score_early = _score_exact("mar", "markets.refresh")
        score_late = _score_exact("resh", "markets.refresh")
        assert score_early > score_late


class TestScorePrefix:
    """测试 _score_prefix（前缀匹配）。"""

    def test_prefix_match(self):
        score = _score_prefix("刷新", "刷新行情")
        assert score > 0

    def test_prefix_scores_higher_than_substring(self):
        # "刷新" as prefix on "刷新行情" should score higher than "行情" as substring
        prefix_score = _score_prefix("刷新", "刷新行情")
        substring_score = _score_exact("行情", "刷新行情")
        assert prefix_score > substring_score

    def test_no_prefix_match(self):
        score = _score_prefix("行情", "刷新行情")
        assert score == 0.0


class TestScoreFuzzy:
    """测试 _score_fuzzy（模糊字符匹配）。"""

    def test_all_chars_in_order_match(self):
        # Chinese chars '刷' and '新' in "刷新行情" - both exist
        score = _score_fuzzy("刷新", "刷新行情")
        assert score > 0
        # English match
        score = _score_fuzzy("ref", "refresh")
        assert score > 0

    def test_missing_char_returns_zero(self):
        score = _score_fuzzy("xyz", "refresh")
        assert score == 0.0

    def test_more_gaps_penalize(self):
        score_tight = _score_fuzzy("res", "refresh")  # r-0, e-1, s-3 — 1 gap
        score_loose = _score_fuzzy("rfh", "refresh")  # r-0, f-2, h-5 — more gaps
        assert score_tight > score_loose


class TestScoreChinese:
    """测试 _score_chinese_match（中文字符匹配）。"""

    def test_chinese_substring_match(self):
        score = _score_chinese_match("行情", "刷新行情")
        assert score > 0

    def test_chinese_no_match(self):
        score = _score_chinese_match("交易", "刷新行情")
        assert score == 0.0


# ============================================================
# Search Integration Tests
# ============================================================

class TestSearchCommands:
    """测试 search_commands 主搜索函数的集成行为。"""

    def test_empty_query_returns_all(self):
        """空查询返回所有命令。"""
        results = search_commands("")
        # Default limit is 20, so we get at least 20 commands
        assert len(results) >= 20

    def test_chinese_query_finds_matching(self):
        """中文查询找到匹配命令。"""
        results = search_commands("刷新")
        assert len(results) > 0
        # 排名第一的应该是 markets.refresh
        top_id = results[0][0].id
        assert top_id == "markets.refresh"

    def test_english_query_finds_matching(self):
        """英文查询找到匹配命令。"""
        results = search_commands("refresh")
        assert len(results) > 0

    def test_category_query_finds_commands(self):
        """按类别关键词搜索返回相关命令。"""
        results = search_commands("分析")
        assert len(results) > 0
        # Should find analysis commands
        ids = {cmd.id for cmd, _ in results}
        assert "analyze.quick" in ids or "analyze.deep" in ids

    def test_results_sorted_by_score_descending(self):
        """搜索结果按分数降序排列。"""
        results = search_commands("分析")
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

    def test_navigation_search(self):
        """搜索'跳转'返回导航命令。"""
        results = search_commands("跳转")
        nav_results = [(cmd, score) for cmd, score in results
                        if cmd.category == "navigation"]
        assert len(nav_results) > 0

    def test_keyword_search(self):
        """通过关键词搜索返回关联命令。"""
        results = search_commands("深色")  # Matches config.theme_toggle keywords
        has_theme = any(cmd.id == "config.theme_toggle" for cmd, _ in results)
        assert has_theme


# ============================================================
# Recent Commands Tests
# ============================================================

class TestRecentCommands:
    """测试最近使用命令追踪。"""

    def setup_method(self):
        """Reset recent commands before each test."""
        from src.shared import commands
        commands._recent_ids.clear()

    def test_record_single_command(self):
        record_recent_command("markets.refresh")
        recent = get_recent_commands()
        assert len(recent) == 1
        assert recent[0].id == "markets.refresh"

    def test_record_multiple_commands_in_order(self):
        record_recent_command("markets.refresh")
        record_recent_command("analyze.quick")
        record_recent_command("nav.tasks")
        recent = get_recent_commands()
        assert len(recent) == 3
        assert recent[0].id == "nav.tasks"      # Most recent
        assert recent[1].id == "analyze.quick"
        assert recent[2].id == "markets.refresh"

    def test_duplicate_command_moves_to_front(self):
        record_recent_command("markets.refresh")
        record_recent_command("analyze.quick")
        record_recent_command("markets.refresh")  # Duplicate
        recent = get_recent_commands()
        assert len(recent) == 2
        assert recent[0].id == "markets.refresh"  # Moved to front

    def test_max_recent_limit(self):
        """最近命令最多保存 10 条。"""
        # Use actual registered commands
        registered_ids = [
            "markets.refresh", "markets.add_stock", "analyze.quick",
            "analyze.deep", "analyze.stream", "portfolio.add",
            "portfolio.view", "trading.buy", "trading.sell",
            "trading.summary", "screener.open", "financials.open",
            "strategies.list", "strategies.import", "strategies.export",
        ]
        for cid in registered_ids:
            record_recent_command(cid)
        recent = get_recent_commands()
        assert len(recent) == 10
        # Most recent should be the last one recorded
        assert recent[0].id == "strategies.export"


# ============================================================
# Command Execution Tests
# ============================================================

class TestCommandExecution:
    """测试命令执行和处理器注册。"""

    def setup_method(self):
        """Clear handlers before each test."""
        from src.shared import commands
        commands._handlers.clear()

    def test_execute_with_registered_handler(self):
        """已注册处理器的命令执行成功。"""
        executed_commands = []

        def handler(cmd_id, ctx):
            executed_commands.append(cmd_id)
            return True

        register_handler("markets.refresh", handler)
        result = execute_command("markets.refresh")
        assert result is True
        assert executed_commands == ["markets.refresh"]

    def test_execute_unregistered_command(self):
        """未注册处理器的命令返回 False。"""
        result = execute_command("nonexistent.command")
        assert result is False

    def test_execute_records_recent(self):
        """执行命令后记录到最近使用。"""
        from src.shared import commands
        commands._recent_ids.clear()

        register_handler("markets.refresh", lambda cid, ctx: True)
        execute_command("markets.refresh")
        recent = get_recent_commands()
        assert len(recent) == 1
        assert recent[0].id == "markets.refresh"

    def test_multiple_handlers_are_called(self):
        """同一个命令的多个处理器都会被调用。"""
        calls = []

        def handler_1(cid, ctx):
            calls.append("h1")
            return True

        def handler_2(cid, ctx):
            calls.append("h2")
            return True

        register_handler("test.cmd", handler_1)
        register_handler("test.cmd", handler_2)
        execute_command("test.cmd")
        assert "h1" in calls
        assert "h2" in calls

    def test_handler_can_access_context(self):
        """处理器可以接收上下文参数。"""
        contexts = []

        def handler(cmd_id, ctx):
            contexts.append(ctx)
            return True

        register_handler("test.cmd", handler)
        execute_command("test.cmd", context={"key": "value"})
        assert contexts[0] == {"key": "value"}


# ============================================================
# Category Meta Tests
# ============================================================

class TestCategoryMeta:
    """测试 CATEGORY_META 类别元数据。"""

    def test_all_categories_have_label_icon_short(self):
        for cat, meta in CATEGORY_META.items():
            assert "label" in meta, f"Category '{cat}' missing label"
            assert "icon" in meta, f"Category '{cat}' missing icon"
            assert "short" in meta, f"Category '{cat}' missing short"

    def test_required_categories_exist(self):
        required = ["markets", "analysis", "portfolio", "trading", "strategy", "config", "navigation"]
        for cat in required:
            assert cat in CATEGORY_META, f"Missing category: {cat}"
