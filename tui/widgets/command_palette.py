"""TUI Command Palette overlay widget.

P5-7: ModalScreen that provides Ctrl+K fuzzy-search command palette.
Uses the shared commands registry from src.shared.commands for consistency
with the GUI command palette.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListView, ListItem, Label
from textual.binding import Binding

from src.shared.commands import (
    Command, CATEGORY_META,
    search_commands, get_recent_commands, execute_command, record_recent_command,
    get_command_registry,
)


class CommandListItem(ListItem):
    """A single command result in the palette list."""

    def __init__(self, command: Command) -> None:
        super().__init__()
        self.command = command

    def compose(self) -> ComposeResult:
        cmd = self.command
        meta = CATEGORY_META.get(cmd.category, {})
        icon = meta.get("icon", "  ")
        short = meta.get("short", "???")

        yield Label(
            f" {icon}[{short}]  [bold]{cmd.name}[/bold]  "
            f"[dim]{cmd.description}[/dim]"
        )


class CommandPalette(ModalScreen):
    """Modal overlay that shows a fuzzy-searchable list of all commands.

    Triggered by Ctrl+K.  Type to filter commands, then press Enter to execute
    the top result, click a result, or press Escape to dismiss.
    """

    BINDINGS = [
        Binding("escape", "dismiss_palette", "关闭", priority=True),
        Binding("ctrl+k", "dismiss_palette", "关闭", priority=True),
        Binding("enter", "select_command", "执行", priority=True),
    ]

    DEFAULT_CSS = """
    CommandPalette {
        align: center middle;
        background: rgba(0, 0, 0, 0.4);
    }

    CommandPalette #palette-container {
        width: 60;
        max-height: 30;
        background: $panel;
        border: thick $accent;
        padding: 1 2;
    }

    CommandPalette #palette-input {
        width: 100%;
        margin-bottom: 1;
    }

    CommandPalette #palette-results {
        width: 100%;
        height: auto;
        max-height: 20;
    }

    CommandPalette #palette-hint {
        width: 100%;
        color: $text-disabled;
        text-style: italic;
        margin-top: 1;
    }

    CommandPalette Label {
        width: 100%;
    }
    """

    def __init__(self, app=None) -> None:
        super().__init__()
        self._app = app
        self._results: list[Command] = []

    def compose(self) -> ComposeResult:
        yield Vertical(
            Input(placeholder="输入命令... (模糊搜索, 支持中文/英文)", id="palette-input"),
            ListView(id="palette-results"),
            Label("↑↓ 导航  ↵ 执行  Esc 取消  Ctrl+K 关闭", id="palette-hint"),
            id="palette-container",
        )

    def on_mount(self) -> None:
        """Focus the input and show recent commands (or all if none)."""
        inp = self.query_one("#palette-input", Input)
        inp.focus()

        recent = get_recent_commands()
        self._results = recent if recent else list(get_command_registry().values())
        self._show_results(self._results)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-filter results when the user types."""
        query = event.value.strip()
        if not query:
            recent = get_recent_commands()
            self._results = recent if recent else list(get_command_registry().values())
        else:
            scored = search_commands(query)
            self._results = [cmd for cmd, _score in scored][:10]
        self._show_results(self._results)

    def _show_results(self, commands: list) -> None:
        """Replace ListView contents with CommandListItems."""
        list_view = self.query_one("#palette-results", ListView)
        list_view.clear()
        for cmd in commands:
            list_view.append(CommandListItem(cmd))
        list_view.index = 0

    def get_selected_command(self) -> Command | None:
        """Return the currently highlighted Command, or None."""
        list_view = self.query_one("#palette-results", ListView)
        children = list(list_view.children)
        idx = list_view.index
        if idx is not None and 0 <= idx < len(children):
            item = children[idx]
            if hasattr(item, "command"):
                return item.command
        return None

    # ── actions ──

    def action_dismiss_palette(self) -> None:
        """Dismiss the palette without executing."""
        self.dismiss(None)

    def action_select_command(self) -> None:
        """Execute the currently highlighted command on Enter."""
        cmd = self.get_selected_command()
        if cmd is None:
            return
        self._execute(cmd)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Execute the clicked command."""
        item = event.item
        if hasattr(item, "command"):
            self._execute(item.command)

    # ── execution ──

    def _execute(self, cmd: Command) -> None:
        """Execute a command and dismiss the palette."""
        cmd_id = cmd.id

        # Record as recently used
        record_recent_command(cmd_id)

        # Navigation commands: switch TUI module
        nav_map = {
            "nav.markets": 0,
            "nav.tasks": 1,
            "nav.analyze": 2,
            "nav.config": 3,
            "nav.logs": 4,
            "nav.strategies": 5,
        }
        if cmd_id in nav_map and self._app is not None:
            self._app.action_switch(nav_map[cmd_id])
            self.dismiss(cmd_id)
            return

        # Theme toggle
        if cmd_id == "config.theme_toggle" and self._app is not None:
            self._app.action_toggle_theme()
            self.dismiss(cmd_id)
            return

        # Market refresh
        if cmd_id == "markets.refresh" and self._app is not None:
            self._app.action_refresh()
            self.dismiss(cmd_id)
            return

        # Strategy navigation (chart view → strategies tab)
        if cmd_id in ("strategies.list", "strategies.import",
                       "strategies.export", "backtest.run") and self._app is not None:
            self._app.action_switch(5)  # strategies tab
            self.dismiss(cmd_id)
            return

        # Screener / Financials → navigate to analysis tab
        if cmd_id in ("screener.open", "financials.open") and self._app is not None:
            self._app.action_switch(2)  # analyze tab
            self.dismiss(cmd_id)
            return

        # Portfolio / Trading commands → navigate to appropriate tab
        if cmd_id in ("portfolio.add", "portfolio.view",
                       "trading.buy", "trading.sell", "trading.summary") and self._app is not None:
            self._app.action_switch(2)  # analyze tab for now
            self.dismiss(cmd_id)
            return

        # Dispatch through handler registry
        executed = execute_command(cmd_id, self._app)
        self.dismiss(cmd_id if executed else None)
