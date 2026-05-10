"""Main Textual app with module routing."""
import sys
import asyncio
from textual.app import App
from textual.binding import Binding
from textual.timer import Timer
from textual.widgets import Static
from tui.widgets.header import Header
from tui.widgets.footer import Footer
from tui.widgets.nav import Nav
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView
from tui.widgets.strategies import StrategiesView
from tui.widgets.notification_center import NotificationCenterPanel
from tui.widgets.toast import ToastContainer, get_toast_container
from tui.data.wrapper import DataProviderWrapper
from tui.data.task_store import TaskStore
from src.config import get_config
from src.service_client import ServiceClient
from src.i18n import _
from src.shared.theme import get_current_theme
from src.notification_center import get_notification_center, Notification
import json
from typing import Optional

MODULES = [MarketsView, TasksView, AnalyzeView, ConfigView, LogsView, StrategiesView]

# 默认按键映射（当 config.json 未配置 keybindings 时使用）
_DEFAULT_KEYBINDINGS = {
    "q": "quit",
    "1": "markets",
    "2": "tasks",
    "3": "analyze",
    "4": "config",
    "5": "logs",
    "6": "strategies",
    "tab": "next_module",
    "r": "refresh",
    "?": "help",
    "t": "toggle_theme",
    "n": "notifications",
}

# 动作名称 → Textual action 映射
_ACTION_MAP = {
    "quit": "quit",
    "markets": "switch(0)",
    "tasks": "switch(1)",
    "analyze": "switch(2)",
    "config": "switch(3)",
    "logs": "switch(4)",
    "strategies": "switch(5)",
    "next_module": "next_module",
    "refresh": "refresh",
    "help": "help",
    "toggle_theme": "toggle_theme",
    "notifications": "notifications",
}

# 动作名称 → 显示标签
_ACTION_LABELS = {
    "quit": _("退出"),
    "markets": _("行情"),
    "tasks": _("任务"),
    "analyze": _("分析"),
    "config": _("配置"),
    "logs": _("日志"),
    "strategies": _("策略"),
    "notifications": _("通知"),
    "next_module": _("下一模块"),
    "refresh": _("刷新"),
    "help": _("帮助"),
    "toggle_theme": _("切换主题"),
}

# 主题 CSS (derived from shared theme on first access)
def _build_theme_css() -> dict:
    """Build theme CSS from shared theme constants."""
    t = get_current_theme()
    return {
        "screen_bg": t["bg"],
        "text": t["fg"],
        "card_bg": t["bg_card"],
        "accent": t["accent"],
        "danger": t["danger"],
        "warning": t["warning"],
        "border": t["border"],
    }

# Bootstrap with dark theme as default (get_current_theme needs config loaded)
_THEME_CSS = {
    "dark": {
        "screen_bg": "#1e1e1e",
        "text": "#e0e0e0",
        "card_bg": "#2d2d2d",
        "accent": "#4CAF50",
        "danger": "#F44336",
        "warning": "#FFC107",
        "border": "#404040",
    },
    "light": {
        "screen_bg": "#ffffff",
        "text": "#1e1e1e",
        "card_bg": "#f5f5f5",
        "accent": "#2E7D32",
        "danger": "#C62828",
        "warning": "#F57F17",
        "border": "#d0d0d0",
    },
}


def _build_bindings(keybindings: dict) -> list:
    """从按键配置构建 Textual Binding 列表。

    支持两种 action 格式：
    - "switch(N)" / "next_module" 等 Textual 原生 action
    - "module_N" 等自定义语义名称 → 通过 _ACTION_MAP 转换
    """
    bindings = []
    for key, action_name in keybindings.items():
        # 将配置中的 action 名称映射为实际的 Textual action
        textual_action = _ACTION_MAP.get(action_name, action_name)
        label = _ACTION_LABELS.get(action_name, action_name)
        bindings.append(Binding(key, textual_action, label))
    return bindings


def _flatten_config_keybindings(keybindings: dict) -> dict:
    """将嵌套格式的 keybindings 展平为 key->action_name 格式。

    config.json 中的嵌套格式: {section: {action: key}}
    展平后: {key: action_name} 用于 Textual Binding 构建。

    对于多 section 中 key 冲突的情况，global section 优先。
    """
    flat = {}
    # 先处理 global（最高优先级），再处理其他 section
    section_order = ["global", "markets", "analysis", "tasks"]
    for section in section_order:
        if section in keybindings and isinstance(keybindings[section], dict):
            for action_name, key in keybindings[section].items():
                flat[key] = action_name
    # 处理不在已知 section 列表中的 section
    for section, bindings in keybindings.items():
        if section not in section_order and isinstance(bindings, dict):
            for action_name, key in bindings.items():
                if key not in flat:
                    flat[key] = action_name
    return flat


class HelpPanel(Static):
    """帮助面板 - 动态显示当前按键绑定"""
    def __init__(self, on_close, keybindings: dict = None):
        self._on_close = on_close
        self._keybindings = keybindings or _DEFAULT_KEYBINDINGS
        content = self._build_content()
        super().__init__(content=content)
        self.display = False

    def _build_content(self) -> str:
        """根据当前按键配置构建帮助文本"""
        lines = [
            _('TUI 快捷键'),
            _('─────────────'),
        ]
        for key, action in self._keybindings.items():
            label = _ACTION_LABELS.get(action, action)
            display_key = key.upper() if len(key) == 1 else key.capitalize()
            lines.append(f"{display_key:<8}{label}")
        lines.extend([
            "",
            _('按 ? 或 Escape 关闭'),
        ])
        return "\n".join(lines)

    def update_keybindings(self, keybindings: dict):
        """热更新按键绑定显示"""
        self._keybindings = keybindings
        self.update(self._build_content())

    def on_key(self, event):
        if event.key == "?" or event.key == "escape":
            self._on_close()


def _make_analyze_callback(app: 'TUIApp'):
    """Create the on_analyze callback for AnalyzeView."""
    def on_analyze(stock_code: str, progress_callback=None):
        app._task_store.add_task(stock_code)
        if progress_callback:
            asyncio.create_task(app._run_analysis_with_progress(stock_code, progress_callback))

    return on_analyze


def _make_deep_analyze_callback(app: 'TUIApp'):
    """Create the on_deep_analyze callback for AnalyzeView (P5-5)."""
    def on_deep_analyze(stock_code: str, progress_callback=None):
        app._task_store.add_task(stock_code)
        if progress_callback:
            asyncio.create_task(app._run_deep_analysis_with_progress(stock_code, progress_callback))

    return on_deep_analyze


class TUIApp(App):
    CSS = """
    Screen { background: #1a1a2e; }
    Screen.light { background: #f5f5f5; }
    """

    def __init__(self, on_analyze_callback=None):
        config = get_config()

        # Support --demo CLI flag to enter demo mode (P5-4)
        if "--demo" in sys.argv:
            config.set_demo_mode(enabled=True)

        # 从配置构建动态按键绑定（向后兼容：缺失时使用默认值）
        kb = config.keybindings if config.keybindings else _DEFAULT_KEYBINDINGS

        # 检测是否为新版嵌套格式 (section -> {action: key})
        if isinstance(kb, dict) and kb and all(isinstance(v, dict) for v in kb.values()):
            self._keybindings = _flatten_config_keybindings(kb)
        else:
            # 旧版 flat 格式 (key -> action) 或空
            self._keybindings = dict(kb) if kb else dict(_DEFAULT_KEYBINDINGS)

        # 确保 toggle_theme 键绑定存在
        if "t" not in self._keybindings:
            self._keybindings["t"] = "toggle_theme"

        # 构建 BINDINGS
        self.BINDINGS = _build_bindings(self._keybindings)
        # P5-7: Always add Ctrl+K command palette shortcut
        self.BINDINGS.append(Binding("ctrl+k", "command_palette", _("命令面板")))

        super().__init__()

        self._client = ServiceClient()
        self._current = 0
        self._refresh_task: Optional[asyncio.Task] = None
        self._on_analyze_callback = on_analyze_callback or _make_analyze_callback(self)
        self._on_deep_analyze_callback = _make_deep_analyze_callback(self)
        self._markets = self._client.get_markets()
        self._dp = DataProviderWrapper(poll_interval=30)
        self._dp.set_stocks(config.stock_list)
        self._task_store = TaskStore()
        self._poll_timer: Timer | None = None

        self._theme = config.theme or "dark"

        # 检测是否需要首次启动引导
        self._show_wizard = config.is_first_time_setup()
        self._wizard_completed = False
        self._wizard_skipped = False
        self._help_visible = False
        self._notifications_visible = False

    def _get_theme_css(self) -> str:
        """Get CSS variables for current theme."""
        theme = _THEME_CSS.get(self._theme, _THEME_CSS["dark"])
        return theme

    def compose(self):
        if self._show_wizard and not self._wizard_completed:
            from tui.widgets.wizard import WizardView
            def on_wizard_complete():
                self._wizard_completed = True
                self._refresh_main_view()
            def on_wizard_skip():
                self._wizard_completed = True
                self._wizard_skipped = True
                self.action_switch(0)
            yield WizardView(on_complete_callback=on_wizard_complete, on_skip_callback=on_wizard_skip)
            return

        config = get_config()
        yield Header()
        yield Nav(active=0)
        yield Footer(last_update="---", demo_mode=config.is_demo_mode())
        yield MarketsView(self._dp)
        yield TasksView(self._task_store)
        yield AnalyzeView(self._on_analyze_callback, self._on_deep_analyze_callback)
        yield ConfigView()
        yield LogsView()
        yield StrategiesView(self._client)
        yield HelpPanel(self._close_help, self._keybindings)
        yield NotificationCenterPanel(self._close_notifications)
        yield get_toast_container()

    def on_mount(self):
        if self._show_wizard and not self._wizard_completed:
            return
        self._apply_theme()
        self._start_polling()
        # Register toast listener for new notifications
        self._nc = get_notification_center()
        self._nc.add_listener(self._on_notification)
        # Hide notification panel initially
        self._notifications_panel = self.query_one(NotificationCenterPanel)
        self._notifications_panel.display = False
        self._toast_container = self.query_one(ToastContainer)
        self._toast_container.display = False

    def _apply_theme(self):
        """Apply current theme CSS to screen."""
        theme = self._get_theme_css()
        screen = self.screen
        screen.styles.background = theme["screen_bg"]
        # 设置 CSS class 以触发 Screen CSS 变量
        if self._theme == "light":
            screen.add_class("light")
            screen.remove_class("dark")
        else:
            screen.add_class("dark")
            screen.remove_class("light")

    def action_toggle_theme(self):
        """切换主题（dark <-> light）"""
        self._theme = "light" if self._theme == "dark" else "dark"
        self._apply_theme()

        # 持久化到 config.json
        config = get_config()
        config.theme = self._theme
        config.save_json_config({"theme": self._theme})

        # 刷新导航和页脚颜色（它们有自己的样式）
        try:
            nav = self.query(Nav).first()
            if nav:
                nav.apply_theme(self._theme)
        except Exception:
            pass
        try:
            footer = self.query(Footer).first()
            if footer:
                footer.apply_theme(self._theme)
        except Exception:
            pass
        try:
            header = self.query(Header).first()
            if header:
                header.apply_theme(self._theme)
        except Exception:
            pass

    def _refresh_main_view(self):
        """刷新主视图（在引导完成后调用）"""
        self._wizard_completed = True
        for widget in list(self.children):
            widget.remove()
        for w in self.compose():
            self.mount(w)
        self._apply_theme()
        self._start_polling()

    def _start_polling(self):
        """Start auto-poll timer."""
        async def poll():
            try:
                await self._dp.fetch_all()
                markets = self.query(MarketsView).first()
                markets.refresh()
                footer = self.query(Footer).first()
                footer.set_last_update(self._dp.get_last_update() or "---")
            except Exception:
                pass

        if self._poll_timer:
            self._poll_timer.stop()
        self._poll_timer = self.set_interval(self._dp.poll_interval, poll)

    def action_switch(self, idx: int):
        self._current = idx
        self.query(Nav).first().set_active(idx)
        for i, w in enumerate(self.query(MODULES).nodes):
            w.display = i == idx

    def action_next_module(self):
        self._current = (self._current + 1) % len(MODULES)
        self.action_switch(self._current)

    def action_refresh(self):
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
        async def refresh():
            try:
                await self._dp.fetch_all()
                markets = self.query(MarketsView).first()
                markets.refresh()
                footer = self.query(Footer).first()
                footer.set_last_update(self._dp.get_last_update() or "---")
            except Exception:
                pass
        self._refresh_task = asyncio.create_task(refresh())

    def action_help(self):
        self._toggle_help()

    def action_command_palette(self):
        """P5-7: Open the command palette modal (Ctrl+K)."""
        from tui.widgets.command_palette import CommandPalette
        self.push_screen(CommandPalette(self))

    def _toggle_help(self):
        self._help_visible = not self._help_visible
        self.query_one(HelpPanel).display = self._help_visible

    def _close_help(self):
        self._help_visible = False
        self.query_one(HelpPanel).display = False

    def action_notifications(self):
        """Toggle notification center panel."""
        self._notifications_visible = not self._notifications_visible
        self._notifications_panel.display = self._notifications_visible
        if self._notifications_visible:
            self._notifications_panel._render()
            self._update_header_badge()

    def _close_notifications(self):
        self._notifications_visible = False
        self._notifications_panel.display = False
        self._update_header_badge()

    def _on_notification(self, notification: Notification):
        """Handle incoming notification -- show toast."""
        try:
            self._toast_container.display = True
            self._toast_container.show_toast(notification)
        except Exception:
            pass
        self._update_header_badge()

    def _update_header_badge(self):
        """Update unread count badge in header."""
        try:
            header = self.query_one(Header)
            count = self._nc.get_unread_count()
            header.set_unread_badge(count)
        except Exception:
            pass

    async def _run_analysis_with_progress(self, stock_code: str, progress_callback):
        """Run analysis with streaming when WebSocket is available.

        P5-1: Tries streaming via WsClient -> DataService WebSocket first.
        Falls back to the blocking pipeline (stdio) if WebSocket is unavailable.
        """
        from tui.widgets.analyze import AnalyzeView
        import logging
        _log = logging.getLogger(__name__)

        analyze_view = self.query_one(AnalyzeView)

        # === Primary path: WebSocket streaming (P5-1) ===
        try:
            from src.ws_client import WsClient
            ws = WsClient()
            await ws.connect()
            _log.info(f"Streaming analysis via WebSocket for {stock_code}")

            analyze_view.start_stream()
            if progress_callback:
                progress_callback("stream_start", 10, _("正在流式分析..."))

            async for event in ws.analyze_stream(stock_code):
                etype = event.get("type")
                if etype == "stream_chunk":
                    analyze_view.append_stream_chunk(event.get("chunk", ""))
                elif etype == "stream_done":
                    result_data = event.get("result", {})
                    # Build an AnalysisResult from the dict returned by WS
                    from src.analyzer import AnalysisResult
                    result = AnalysisResult(**result_data) if result_data else None
                    if result:
                        analyze_view.finish_stream(result)
                        if progress_callback:
                            progress_callback("analysis_completed", 100, _("分析完成"))
                    await ws.close()
                    return
                elif etype == "stream_error":
                    _log.warning(f"Stream error for {stock_code}: {event.get('message')}")
                    break

            await ws.close()
        except Exception as e:
            _log.info(f"WebSocket streaming unavailable ({e}), falling back to pipeline")

        # === Fallback: blocking pipeline via stdio ===
        from src.core.pipeline import StockAnalysisPipeline
        try:
            pipeline = StockAnalysisPipeline(progress_callback=progress_callback)
            result = await asyncio.to_thread(pipeline.process_single_stock, stock_code)
            if result:
                analyze_view.finish_stream(result)
                if progress_callback:
                    progress_callback("analysis_completed", 100, _("分析完成"))
            else:
                if progress_callback:
                    progress_callback("analysis_failed", 100, _("分析失败"))
        except Exception as e:
            if progress_callback:
                progress_callback("analysis_error", 100, f"{_('错误: ')}{e}")

    # ============================================================
    # P5-5: Deep Analysis with progress
    # ============================================================

    async def _run_deep_analysis_with_progress(self, stock_code: str, progress_callback=None):
        """Run deep multi-agent analysis via WebSocket or pipeline fallback."""
        from tui.widgets.analyze import AnalyzeView
        import logging
        _log = logging.getLogger(__name__)

        analyze_view = self.query_one(AnalyzeView)

        # === Primary: WebSocket ===
        try:
            from src.ws_client import WsClient
            ws = WsClient()
            await ws.connect()

            if progress_callback:
                progress_callback("deep_agents", 15, _("技术面分析中..."))

            await ws._ws.send(json.dumps({"action": "deep_analyze", "code": stock_code}))
            resp = await ws._ws.recv()
            resp_data = json.loads(resp)
            await ws.close()

            if resp_data.get("status") == "ok":
                result = resp_data.get("result")
                if result:
                    if progress_callback:
                        progress_callback("deep_complete", 100, _("深度分析完成"))
                    analyze_view.finish_deep_analysis(result)
                    return

                # Poll for task result
                task_id = resp_data.get("task_id")
                if task_id:
                    import asyncio
                    for i in range(30):
                        await asyncio.sleep(1)
                        try:
                            await ws.connect()
                            await ws._ws.send(json.dumps({"action": "get_task", "task_id": task_id}))
                            tr = await ws._ws.recv()
                            td = json.loads(tr)
                            await ws.close()

                            if td.get("status") == "ok":
                                tdata = td.get("data", {})
                                status = tdata.get("status")
                                if status == "completed":
                                    if progress_callback:
                                        progress_callback("deep_complete", 100, _("深度分析完成"))
                                    analyze_view.finish_deep_analysis(tdata.get("result", {}))
                                    return
                                elif status == "failed":
                                    analyze_view.finish_deep_error(tdata.get("error", _("未知错误")))
                                    return
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass

                    analyze_view.finish_deep_error(_("深度分析超时"))
                    return
        except Exception as e:
            _log.info(f"WS deep analysis unavailable ({e}), falling back to pipeline")

        # === Fallback: pipeline via stdio ===
        from src.core.pipeline import StockAnalysisPipeline
        try:
            if progress_callback:
                progress_callback("deep_pipeline", 20, _("深度分析执行中..."))

            pipeline = StockAnalysisPipeline(progress_callback=progress_callback)
            result = await asyncio.to_thread(
                pipeline.analyze_stock_deep, stock_code
            )
            if result:
                if progress_callback:
                    progress_callback("deep_complete", 100, _("深度分析完成"))
                analyze_view.finish_deep_analysis(result)
            else:
                analyze_view.finish_deep_error(_("分析失败"))
        except Exception as e:
            analyze_view.finish_deep_error(str(e))
