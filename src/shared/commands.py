"""Command Registry and Fuzzy Search for P5-7 Command Palette.

Canonical implementation of:
- Command dataclass with attribute access
- Full command registry (25+ commands)
- Fuzzy search with multi-level scoring
- Recent commands tracking (last 10)
- Handler registration and dispatch

Used by both TUI (tui/widgets/command_palette.py) and GUI (gui/pages/command_palette.py).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from collections import OrderedDict


# ---------------------------------------------------------------------------
# Command data model
# ---------------------------------------------------------------------------

@dataclass
class Command:
    """A single user-facing command."""
    id: str                                  # Unique ID, e.g. "markets.refresh"
    name: str                                # Display name
    description: str = ""                    # One-line description
    category: str = ""                       # Category key
    keywords: List[str] = field(default_factory=list)
    needs_input: bool = False                # Whether command needs stock code input
    input_prompt: str = ""                   # Prompt for input


# Category display metadata
CATEGORY_META: Dict[str, Dict[str, str]] = {
    "markets":      {"label": "行情", "icon": "📈", "short": "MKT"},
    "analysis":     {"label": "分析", "icon": "🔍", "short": "ANZ"},
    "portfolio":    {"label": "持仓", "icon": "📊", "short": "POS"},
    "trading":      {"label": "交易", "icon": "💰", "short": "TRD"},
    "strategy":     {"label": "策略", "icon": "🎯", "short": "STG"},
    "config":       {"label": "配置", "icon": "⚙️", "short": "CFG"},
    "navigation":   {"label": "导航", "icon": "🧭", "short": "NAV"},
}


# ---------------------------------------------------------------------------
# Command registry
# ---------------------------------------------------------------------------

def _build_registry() -> Dict[str, Command]:
    """Build the canonical command registry."""
    commands: List[Command] = [
        Command("markets.refresh", "刷新行情", "刷新所有自选股实时行情数据",
                "markets", ["refresh", "market", "实时", "行情", "刷新", "更新"]),
        Command("markets.add_stock", "添加自选股", "将新股票代码加入自选列表",
                "markets", ["add", "stock", "watchlist", "添加", "自选", "股票"],
                needs_input=True, input_prompt="输入股票代码"),
        Command("analyze.quick", "快速分析", "对指定股票执行快速技术面分析",
                "analysis", ["quick", "fast", "scan", "快速", "分析", "技术"],
                needs_input=True, input_prompt="输入股票代码"),
        Command("analyze.deep", "深度分析", "执行完整的多维度深度分析",
                "analysis", ["deep", "full", "detail", "深度", "完整", "全面"],
                needs_input=True, input_prompt="输入股票代码"),
        Command("analyze.stream", "流式分析", "通过WebSocket流式输出分析结果",
                "analysis", ["stream", "streaming", "流式", "实时", "websocket"],
                needs_input=True, input_prompt="输入股票代码"),
        Command("portfolio.add", "添加持仓", "添加模拟持仓记录",
                "portfolio", ["add", "position", "hold", "添加", "持仓"]),
        Command("portfolio.view", "查看持仓", "查看当前所有模拟持仓及盈亏",
                "portfolio", ["view", "list", "holdings", "查看", "持仓", "盈亏"]),
        Command("trading.buy", "模拟买入", "模拟买入指定股票",
                "trading", ["buy", "order", "long", "买入", "买", "开仓"]),
        Command("trading.sell", "模拟卖出", "模拟卖出指定股票",
                "trading", ["sell", "order", "short", "卖出", "卖", "平仓"]),
        Command("trading.summary", "账户摘要", "查看模拟交易账户概况",
                "trading", ["summary", "account", "balance", "摘要", "账户", "资金"]),
        Command("screener.open", "打开选股器", "根据技术指标条件筛选股票",
                "analysis", ["screener", "filter", "scan", "选股", "筛选", "条件"]),
        Command("financials.open", "打开财务报表", "查看股票财务数据",
                "analysis", ["financials", "report", "income", "balance", "财务", "报表", "利润"]),
        Command("strategies.list", "策略列表", "查看已保存的交易策略",
                "strategy", ["list", "view", "all", "策略", "列表", "查看"]),
        Command("strategies.import", "导入策略", "从文件导入交易策略",
                "strategy", ["import", "load", "file", "导入", "加载", "文件"]),
        Command("strategies.export", "导出策略", "导出当前策略到文件",
                "strategy", ["export", "save", "file", "导出", "保存", "文件"]),
        Command("backtest.run", "运行回测", "对策略执行历史数据回测",
                "strategy", ["backtest", "history", "simulate", "回测", "历史", "模拟"],
                needs_input=True, input_prompt="输入股票代码"),
        Command("config.theme_toggle", "切换主题", "切换深色/浅色主题",
                "config", ["theme", "dark", "light", "主题", "深色", "浅色"]),
        Command("config.language", "切换语言", "切换界面语言(中文/英文)",
                "config", ["language", "i18n", "locale", "语言", "英文", "中文"]),
        Command("config.alerts", "告警设置", "管理价格告警规则",
                "config", ["alert", "notification", "alarm", "告警", "通知", "提醒"]),
        Command("nav.markets", "跳转行情", "切换到行情页面",
                "navigation", ["markets", "tab", "go", "行情", "跳转", "切换"]),
        Command("nav.tasks", "跳转任务", "切换到任务页面",
                "navigation", ["tasks", "history", "go", "任务", "跳转", "历史"]),
        Command("nav.analyze", "跳转分析", "切换到分析页面",
                "navigation", ["analyze", "analysis", "go", "分析", "跳转"]),
        Command("nav.config", "跳转设置", "切换到设置页面",
                "navigation", ["config", "settings", "go", "设置", "配置", "跳转"]),
        Command("nav.logs", "跳转日志", "切换到日志页面",
                "navigation", ["logs", "log", "go", "日志", "跳转", "记录"]),
        Command("nav.strategies", "跳转策略", "切换到策略页面",
                "navigation", ["strategies", "strategy", "go", "策略", "跳转"]),
    ]
    return OrderedDict((c.id, c) for c in commands)


_COMMAND_REGISTRY: Optional[Dict[str, Command]] = None


def get_command_registry() -> Dict[str, Command]:
    """Return the canonical command registry (lazy init)."""
    global _COMMAND_REGISTRY
    if _COMMAND_REGISTRY is None:
        _COMMAND_REGISTRY = _build_registry()
    return _COMMAND_REGISTRY


def find_command(command_id: str) -> Optional[Command]:
    """Look up a command by its unique ID."""
    return get_command_registry().get(command_id)


# ---------------------------------------------------------------------------
# Fuzzy search engine (no external dependencies)
# ---------------------------------------------------------------------------

def _score_substring(query: str, target: str) -> float:
    """Return score if query is a substring of target."""
    ql = query.lower()
    tl = target.lower()
    idx = tl.find(ql)
    if idx < 0:
        return 0.0
    position_bonus = 1.0 - (idx / max(len(tl), 1)) * 0.5
    return 6.0 + position_bonus


def _score_prefix(query: str, target: str) -> float:
    """Return score if target starts with query."""
    if target.lower().startswith(query.lower()):
        return 8.0
    return 0.0


def _score_fuzzy(query: str, target: str) -> float:
    """Sequence match: all query chars appear in target in order."""
    ql = query.lower()
    tl = target.lower()
    qi = 0
    last_idx = -1
    gaps = 0
    for ti, tc in enumerate(tl):
        if qi < len(ql) and ql[qi] == tc:
            gaps += ti - last_idx - 1
            last_idx = ti
            qi += 1
    if qi != len(ql):
        return 0.0
    gap_penalty = max(0, gaps - 2) * 0.3
    return max(0.5, 4.0 - gap_penalty)


def search_commands(query: str, registry: Optional[Dict[str, Command]] = None,
                    limit: int = 20) -> List[Tuple[Command, float]]:
    """Fuzzy search commands by query against name, description, and keywords.

    Returns list of (Command, score) sorted by score descending.
    """
    if registry is None:
        registry = get_command_registry()

    query = query.strip()
    if not query:
        return [(cmd, 0.0) for cmd in registry.values()][:limit]

    results: List[Tuple[Command, float]] = []

    for cmd in registry.values():
        best = 0.0

        best = max(best, _score_prefix(query, cmd.name))
        best = max(best, _score_substring(query, cmd.name))
        best = max(best, _score_substring(query, cmd.description) * 0.7)
        best = max(best, _score_fuzzy(query, cmd.name))

        for kw in cmd.keywords:
            kw_score = max(_score_substring(query, kw), _score_prefix(query, kw),
                           _score_fuzzy(query, kw))
            best = max(best, kw_score * 1.1)

        if best > 0:
            results.append((cmd, best))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]


def _score_exact(query: str, target: str) -> float:
    """Alias for _score_substring for API compatibility."""
    return _score_substring(query, target)


def _score_chinese_match(query: str, target: str) -> float:
    """Chinese character matching - optimized for Chinese query against Chinese target."""
    return _score_substring(query, target)


def get_commands_by_category() -> Dict[str, List[Command]]:
    """Return commands grouped by category."""
    registry = get_command_registry()
    categories: Dict[str, List[Command]] = {}
    for cmd in registry.values():
        categories.setdefault(cmd.category, []).append(cmd)
    return categories


# ---------------------------------------------------------------------------
# Recent commands tracking (in-memory, last 10)
# ---------------------------------------------------------------------------

_recent_ids: List[str] = []
_MAX_RECENT = 10


def record_recent_command(command_id: str) -> None:
    """Record a command as recently used (moves to front)."""
    global _recent_ids
    if command_id in _recent_ids:
        _recent_ids.remove(command_id)
    _recent_ids.insert(0, command_id)
    if len(_recent_ids) > _MAX_RECENT:
        _recent_ids[:] = _recent_ids[:_MAX_RECENT]


def get_recent_commands() -> List[Command]:
    """Return recently used commands in order (most recent first)."""
    registry = get_command_registry()
    result = []
    for cid in _recent_ids:
        cmd = registry.get(cid)
        if cmd:
            result.append(cmd)
    return result


# ---------------------------------------------------------------------------
# Handler registration and dispatch
# ---------------------------------------------------------------------------

CommandHandler = Callable[[str, Any], bool]
_handlers: Dict[str, List[CommandHandler]] = {}


def register_handler(command_id: str, handler: CommandHandler) -> None:
    """Register a handler for a specific command ID."""
    _handlers.setdefault(command_id, []).append(handler)


def execute_command(command_id: str, context: Any = None) -> bool:
    """Execute a command by calling all registered handlers.

    Also records the command as recently used.

    Returns:
        True if at least one handler returned True, False otherwise.
    """
    record_recent_command(command_id)

    handlers = _handlers.get(command_id, [])
    if not handlers:
        return False

    any_matched = False
    for h in handlers:
        try:
            if h(command_id, context):
                any_matched = True
        except Exception:
            pass
    return any_matched


# Convenience alias for the command registry
COMMANDS = get_command_registry()
