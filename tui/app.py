"""Main Textual app with module routing."""
import asyncio
from textual.app import App
from textual.binding import Binding
from textual.timer import Timer
from textual.widgets import Static
from tui.widgets.nav import Nav
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView
from tui.data.wrapper import DataProviderWrapper
from tui.data.task_store import TaskStore
from src.config import get_config
from src.service_client import ServiceClient
from typing import Optional

MODULES = [MarketsView, TasksView, AnalyzeView, ConfigView, LogsView]


class HelpPanel(Static):
    """帮助面板"""
    def __init__(self, on_close):
        self._on_close = on_close
        content = """
        TUI 快捷键
        ─────────────
        1-5     切换模块
        Tab     下一个模块
        r       刷新行情
        ?       显示帮助
        q       退出

        按 ? 或 Escape 关闭
        """
        super().__init__(content=content)
        self.display = False

    def on_key(self, event):
        if event.key == "?" or event.key == "escape":
            self._on_close()


def _make_analyze_callback(app: 'TUIApp'):
    """Create the on_analyze callback for AnalyzeView."""
    def on_analyze(stock_code: str, progress_callback=None):
        app._task_store.add_task(stock_code)
        # Run analysis with progress callback
        if progress_callback:
            asyncio.create_task(app._run_analysis_with_progress(stock_code, progress_callback))
        else:
            # Fallback: just add to task store
            pass

    return on_analyze


class TUIApp(App):
    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("1", "switch(0)", ""),
        Binding("2", "switch(1)", ""),
        Binding("3", "switch(2)", ""),
        Binding("4", "switch(3)", ""),
        Binding("5", "switch(4)", ""),
        Binding("tab", "next_module", ""),
        Binding("r", "refresh", "刷新"),
        Binding("?", "help", "帮助"),
    ]
    CSS = """
    Screen { background: #1a1a2e; }
    """

    def __init__(self, on_analyze_callback=None):
        super().__init__()
        self._client = ServiceClient()
        self._current = 0
        self._refresh_task: Optional[asyncio.Task] = None
        self._on_analyze_callback = on_analyze_callback or _make_analyze_callback(self)
        config = get_config()
        self._markets = self._client.get_markets()
        self._dp = DataProviderWrapper(poll_interval=30)
        self._dp.set_stocks(config.stock_list)
        self._task_store = TaskStore()
        self._poll_timer: Timer | None = None

        # 检测是否需要首次启动引导
        self._show_wizard = config.is_first_time_setup()
        self._wizard_completed = False
        self._wizard_skipped = False
        self._help_visible = False

    def compose(self):
        if self._show_wizard and not self._wizard_completed:
            from tui.widgets.wizard import WizardView
            def on_wizard_complete():
                self._wizard_completed = True
                self._refresh_main_view()
            def on_wizard_skip():
                self._wizard_completed = True
                self._wizard_skipped = True  # 标记用户跳过了引导
                self.action_switch(0)  # 进入 Markets
            yield WizardView(on_complete_callback=on_wizard_complete, on_skip_callback=on_wizard_skip)
            return

        # 正常视图
        yield Header()
        yield Nav(active=0)
        yield Footer(last_update="---")
        yield MarketsView(self._dp)
        yield TasksView(self._task_store)
        yield AnalyzeView(self._on_analyze_callback)
        yield ConfigView()
        yield LogsView()
        yield HelpPanel(self._close_help)

    def on_mount(self):
        if self._show_wizard and not self._wizard_completed:
            return  # Don't start polling during wizard
        self._start_polling()

    def _refresh_main_view(self):
        """刷新主视图（在引导完成后调用）"""
        self._wizard_completed = True
        for widget in list(self.children):
            widget.remove()
        for w in self.compose():
            self.mount(w)
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
                pass  # Ignore poll errors during view transitions

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

    def _toggle_help(self):
        self._help_visible = not self._help_visible
        self.query_one(HelpPanel).display = self._help_visible

    def _close_help(self):
        self._help_visible = False
        self.query_one(HelpPanel).display = False

    async def _run_analysis_with_progress(self, stock_code: str, progress_callback):
        """Run analysis with progress reporting."""
        from src.core.pipeline import StockAnalysisPipeline
        try:
            pipeline = StockAnalysisPipeline(progress_callback=progress_callback)
            result = await asyncio.to_thread(pipeline.process_single_stock, stock_code)
            if result:
                progress_callback("analysis_completed", 100, "分析完成")
            else:
                progress_callback("analysis_failed", 100, "分析失败")
        except Exception as e:
            progress_callback("analysis_error", 100, f"错误: {e}")
