"""Main Textual app with module routing."""
import asyncio
from textual.app import App
from textual.binding import Binding
from textual.timer import Timer
from tui.widgets.header import Header
from tui.widgets.footer import Footer
from tui.widgets.nav import Nav
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView
from tui.data.wrapper import DataProviderWrapper
from tui.data.task_store import TaskStore
from src.config import get_config
from src.core.pipeline import StockAnalysisPipeline
from typing import Optional

MODULES = [MarketsView, TasksView, AnalyzeView, ConfigView, LogsView]


def _make_analyze_callback(app: 'TUIApp'):
    """Create the on_analyze callback for AnalyzeView."""
    def on_analyze(stock_code: str):
        app._task_store.add_task(stock_code)
        # Full pipeline integration will be done in Task 7
        # For now, just add to task store and show "analyzing" state
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
        self._current = 0
        self._refresh_task: Optional[asyncio.Task] = None
        self._on_analyze_callback = on_analyze_callback or _make_analyze_callback(self)
        config = get_config()
        self._dp = DataProviderWrapper(poll_interval=30)
        self._dp.set_stocks(config.stock_list)
        self._task_store = TaskStore()
        self._poll_timer: Timer | None = None

        # 检测是否需要首次启动引导
        self._show_wizard = config.is_first_time_setup()
        self._wizard_completed = False
        self._wizard_skipped = False

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

    def on_mount(self):
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
            await self._dp.fetch_all()
            markets = self.query(MarketsView).first()
            markets.refresh()
            footer = self.query(Footer).first()
            footer.set_last_update(self._dp.get_last_update() or "---")

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
            await self._dp.fetch_all()
            markets = self.query(MarketsView).first()
            markets.refresh()
            footer = self.query(Footer).first()
            footer.set_last_update(self._dp.get_last_update() or "---")
        self._refresh_task = asyncio.create_task(refresh())
