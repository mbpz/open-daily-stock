"""Main Textual app with module routing."""
import asyncio
from textual.app import App
from textual.binding import Binding
from textual.widgets import Static
from tui.widgets.header import Header
from tui.widgets.footer import Footer
from tui.widgets.nav import Nav
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView
from tui.data.wrapper import DataProviderWrapper
from src.config import get_config

MODULES = [MarketsView, TasksView, AnalyzeView, ConfigView, LogsView]

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
    Screen { background: "#1a1a2e"; }
    """

    def __init__(self):
        super().__init__()
        self._current = 0
        self._dp = DataProviderWrapper(poll_interval=30)
        # Load stocks from config
        config = get_config()
        self._dp.set_stocks(config.stock_list)

    def compose(self):
        yield Header()
        yield Nav(active=0)
        # Pass data provider to MarketsView
        yield MarketsView(data_provider=self._dp)
        yield Footer(last_update="---")

    def on_mount(self):
        """Set up auto-poll timer after mount."""
        self._start_polling()

    def _start_polling(self):
        """Start the auto-poll timer."""
        async def poll():
            await self._dp.fetch_all()
            self.update_markets_view()

        async def poll_loop():
            while True:
                await asyncio.sleep(self._dp._poll_interval)
                try:
                    await self._dp.fetch_all()
                    self.update_markets_view()
                except Exception as e:
                    print(f"Poll error: {e}")

        asyncio.create_task(poll_loop())

    def update_markets_view(self):
        """Refresh the markets view display."""
        # Find and refresh the MarketsView
        for widget in self.screen.query(MarketsView):
            widget.refresh()
            break

    def action_switch(self, idx: int):
        self._current = idx
        self.mount(*[w() if w is not MarketsView else MarketsView(data_provider=self._dp) for w in MODULES])

    def action_next_module(self):
        self._current = (self._current + 1) % len(MODULES)
        self.action_switch(self._current)

    def action_refresh(self):
        """Manual refresh - fetch data and update display."""
        async def do_refresh():
            await self._dp.fetch_all()
            self.update_markets_view()
        asyncio.create_task(do_refresh())