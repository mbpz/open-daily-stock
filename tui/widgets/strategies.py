"""Strategy management widget for TUI."""
import json
from textual.widgets import Static, Input, Button
from textual.events import Key
from src.i18n import _


class StrategiesView(Static):
    """TUI strategy management view - list, import, export, run, delete strategies."""

    def __init__(self, service_client=None):
        super().__init__()
        self._client = service_client
        self._strategies = []
        self._selected_idx = 0
        self._mode = "list"  # "list", "import", "export_new"
        self._pending_input = None

    def _load_strategies(self):
        """Load strategies from DataService."""
        try:
            if self._client:
                resp = self._client._send_request("list_strategies")
                if resp.get("status") == "ok":
                    self._strategies = resp.get("data", [])
                else:
                    self._strategies = []
            else:
                self._strategies = []
        except Exception:
            self._strategies = []

    def compose(self):
        if self._mode == "import":
            yield from self._compose_import()
        elif self._mode == "export_new":
            yield from self._compose_export()
        else:
            yield from self._compose_list()

    def _compose_list(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  strategy_platform  (↑↓ select, i import, e export new, r run, d delete)"), id="nav-hint")
        yield Static("=" * 50, id="divider")

        if not self._strategies:
            yield Static(_("  (no_strategies_press_i_import)"), id="no-strategies")
        else:
            for i, strat in enumerate(self._strategies):
                marker = ">" if i == self._selected_idx else " "
                name = strat.get("name", _("unnamed"))
                desc = strat.get("description", "")
                author = strat.get("author", "")
                version = strat.get("version", "1.0")
                entry = strat.get("entry_rule", "")
                exit = strat.get("exit_rule", "")
                params = strat.get("params", {})

                summary_parts = []
                if author:
                    summary_parts.append(f"@{author}")
                if version:
                    summary_parts.append(f"v{version}")
                if entry:
                    summary_parts.append(f"Entry: {entry}")
                if exit:
                    summary_parts.append(f"Exit: {exit}")
                summary = " | ".join(summary_parts) if summary_parts else ""

                params_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:4])
                lines = [f"{marker} {name}"]
                if summary:
                    lines.append(f"    {summary}")
                if desc:
                    lines.append(f"    {desc}")
                if params_str:
                    lines.append(f"    params: {params_str}")
                yield Static("\n".join(lines), id=f"strategy-{i}")

        yield Static("", id="status-line")
        yield Static(_("  i import  e new  r run  d delete  Esc quit"), id="footer-hint")

    def _compose_import(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  import_strategy_json_instructions"), id="nav-hint")
        yield Static("=" * 50, id="divider")
        yield Static(_("  paste_json_and_press_enter"), id="instructions")
        yield Static("", id="import-area")
        yield Static(_("  Esc to cancel"), id="footer-hint")

    def _compose_export(self):
        yield Static("=" * 50, id="header")
        yield Static(_("  create_new_strategy_form"), id="nav-hint")
        yield Static("=" * 50, id="divider")
        yield Static(_("  enter_strategy_details"), id="instructions")
        yield Static("", id="export-input-area")
        yield Static("", id="export-status")
        yield Static(_("  Enter to save, Esc to cancel"), id="footer-hint")

    def on_mount(self):
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)
        self._load_strategies()
        self.focus()

    def _refresh_list(self):
        """Reload and refresh the list view."""
        self._load_strategies()
        self.refresh()

    def _show_status(self, msg: str):
        """Show a status message."""
        try:
            el = self.query_one("#status-line", Static)
            el.update(msg)
        except Exception:
            pass

    def on_key(self, event: Key):
        if self._mode == "import":
            self._handle_import_key(event)
        elif self._mode == "export_new":
            self._handle_export_key(event)
        else:
            self._handle_list_key(event)

    def _handle_list_key(self, event: Key):
        if event.key == "escape":
            return
        elif event.key == "up":
            if self._strategies:
                self._selected_idx = max(0, self._selected_idx - 1)
                self._refresh_list_display()
        elif event.key == "down":
            if self._strategies:
                self._selected_idx = min(len(self._strategies) - 1, self._selected_idx + 1)
                self._refresh_list_display()
        elif event.key == "r":
            self._run_current_strategy()
        elif event.key == "d":
            self._delete_current_strategy()
        elif event.key == "i":
            self._mode = "import"
            self.refresh()
        elif event.key == "e":
            self._mode = "export_new"
            self.refresh()

    def _handle_import_key(self, event: Key):
        if event.key == "escape":
            self._mode = "list"
            self.refresh()
            return
        elif event.key == "enter":
            self._start_import_input()

    def _handle_export_key(self, event: Key):
        if event.key == "escape":
            self._mode = "list"
            self.refresh()
            return
        elif event.key == "enter":
            self._start_export_input()

    def _refresh_list_display(self):
        """Update markers for selected item."""
        for i in range(len(self._strategies)):
            marker = ">" if i == self._selected_idx else " "
            try:
                el = self.query_one(f"#strategy-{i}", Static)
                name = self._strategies[i].get("name", _("unnamed"))
                desc = self._strategies[i].get("description", "")
                author = self._strategies[i].get("author", "")
                version = self._strategies[i].get("version", "1.0")
                entry = self._strategies[i].get("entry_rule", "")
                exit = self._strategies[i].get("exit_rule", "")
                params = self._strategies[i].get("params", {})

                summary_parts = []
                if author:
                    summary_parts.append(f"@{author}")
                if version:
                    summary_parts.append(f"v{version}")
                if entry:
                    summary_parts.append(f"Entry: {entry}")
                if exit:
                    summary_parts.append(f"Exit: {exit}")
                summary = " | ".join(summary_parts) if summary_parts else ""

                params_str = ", ".join(f"{k}={v}" for k, v in list(params.items())[:4])
                lines = [f"{marker} {name}"]
                if summary:
                    lines.append(f"    {summary}")
                if desc:
                    lines.append(f"    {desc}")
                if params_str:
                    lines.append(f"    params: {params_str}")
                el.update("\n".join(lines))
            except Exception:
                pass

    def _start_import_input(self):
        """Show import JSON text input."""
        self.query_one("#import-area", Static).update(_("enter_json_text_below"))
        input_widget = Input(value="", id="import-json-input")
        input_widget.focus()

        try:
            old = self.query_one("#import-area")
            old.remove_children()
            old.remove()
        except Exception:
            pass
        self.mount(input_widget)

        def on_submit(event):
            input_widget.remove()
            self._do_import(event.value)

        input_widget.on_submit = on_submit

    def _do_import(self, json_text: str):
        """Execute strategy import."""
        if not json_text.strip():
            self._show_status(_("import_failed_empty_json"))
            self._mode = "list"
            self.refresh()
            return

        try:
            resp = self._client._send_request("import_strategy", {"data": json_text})
            if resp.get("status") == "ok":
                self._show_status(_("import_success"))
            else:
                self._show_status(f"{_('import_failed')}: {resp.get('message', '')}")
        except Exception as e:
            self._show_status(f"{_('import_failed')}: {str(e)}")

        self._mode = "list"
        self._refresh_list()

    def _start_export_input(self):
        """Show export form input fields in sequence."""
        self._export_step = 0
        self._export_data = {}
        self._export_fields = [
            ("name", _("strategy_name")),
            ("author", _("author")),
            ("description", _("description")),
            ("entry_rule", _("entry_rule_hint")),
            ("exit_rule", _("exit_rule_hint")),
            ("fast_ma", _("fast_ma_value") + " (default: 5)"),
            ("slow_ma", _("slow_ma_value") + " (default: 20)"),
            ("initial_capital", _("initial_capital_value") + " (default: 100000)"),
            ("stop_loss_pct", _("stop_loss_pct_value") + " (default: -5.0)"),
        ]
        self._ask_next_export_field()

    def _ask_next_export_field(self):
        """Ask for the next export field."""
        if self._export_step >= len(self._export_fields):
            self._finalize_export()
            return

        field_key, field_label = self._export_fields[self._export_step]
        self.query_one("#export-input-area", Static).update(f"[{_('step')} {self._export_step + 1}] {field_label} ")
        input_widget = Input(value="", id="export-field-input",
                             placeholder=field_label)
        input_widget.focus()

        try:
            old = self.query_one("#export-input-area")
            old.remove_children()
            old.remove()
        except Exception:
            pass
        self.mount(input_widget)

        def on_submit(event):
            input_widget.remove()
            value = event.value.strip()
            if value:
                self._export_data[field_key] = value
            self._export_step += 1
            self._ask_next_export_field()

        input_widget.on_submit = on_submit

    def _finalize_export(self):
        """Create and export the new strategy."""
        name = self._export_data.get("name", "")
        if not name:
            self._show_status(_("enter_strategy_name"))
            self._mode = "list"
            self.refresh()
            return

        strategy = {
            "name": name,
            "version": "1.0",
            "description": self._export_data.get("description", ""),
            "author": self._export_data.get("author", ""),
            "params": {
                "fast_ma": int(self._export_data.get("fast_ma", "5") or "5"),
                "slow_ma": int(self._export_data.get("slow_ma", "20") or "20"),
                "initial_capital": float(self._export_data.get("initial_capital", "100000") or "100000"),
                "stop_loss_pct": float(self._export_data.get("stop_loss_pct", "-5.0") or "-5.0"),
            },
            "code": "python",
            "indicators": ["ma5", "ma20"],
            "entry_rule": self._export_data.get("entry_rule", ""),
            "exit_rule": self._export_data.get("exit_rule", ""),
        }

        try:
            resp = self._client._send_request("export_strategy", strategy)
            if resp.get("status") == "ok":
                self._show_status(_("export_success"))
            else:
                self._show_status(f"{_('export_failed')}: {resp.get('message', '')}")
        except Exception as e:
            self._show_status(f"{_('export_failed')}: {str(e)}")

        self._mode = "list"
        self._refresh_list()

    def _run_current_strategy(self):
        """Run backtest with current selected strategy."""
        if not self._strategies or not self._client:
            self._show_status(_("no_strategies"))
            return

        strat = self._strategies[self._selected_idx]
        params = strat.get("params", {})
        code = params.get("code", "000001")
        initial_capital = params.get("initial_capital", 100000)
        days = params.get("days", 60)

        try:
            resp = self._client._send_request("run_backtest", {
                "code": code,
                "initial_capital": initial_capital,
                "days": days,
            })
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                msg = (
                    f"{strat.get('name')}: "
                    f"Return={data.get('total_return', 0)}% "
                    f"Sharpe={data.get('sharpe_ratio', 0)} "
                    f"Trades={data.get('num_trades', 0)} "
                    f"Win={data.get('win_rate', 0)}%"
                )
                self._show_status(msg)
            else:
                self._show_status(f"{_('backtest_failed')}: {resp.get('message', '')}")
        except Exception as e:
            self._show_status(f"{_('backtest_failed')}: {str(e)}")

    def _delete_current_strategy(self):
        """Delete the current selected strategy."""
        if not self._strategies:
            return

        strat = self._strategies[self._selected_idx]
        name = strat.get("name", "")

        try:
            resp = self._client._send_request("delete_strategy", {"name": name})
            if resp.get("status") == "ok":
                self._show_status(_("delete_success"))
            else:
                self._show_status(f"{_('delete_failed')}: {resp.get('message', '')}")
        except Exception as e:
            self._show_status(f"{_('delete_failed')}: {str(e)}")

        self._selected_idx = min(self._selected_idx, max(0, len(self._strategies) - 2))
        self._refresh_list()
