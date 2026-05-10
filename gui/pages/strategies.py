"""策略管理页面 - Strategy platform/community"""
import json
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR, SUCCESS_COLOR, ERROR_COLOR, WARNING_COLOR, TEXT_SECONDARY
from src.i18n import _


class StrategiesPage(ft.Container):
    """策略管理页面 - import/export/run/delete strategies"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._client = app._client
        self._strategies = []
        self._import_dialog = None
        self._selected_idx = None

        self._build_ui()
        self._load_strategies()

    def _build_ui(self):
        """Build the strategies management UI"""
        header = ft.Text(_("strategy_platform"), size=24, weight=ft.FontWeight.BOLD)

        desc = ft.Text(
            _("strategy_platform_desc"),
            size=14,
            color=TEXT_SECONDARY,
        )

        # Strategy list
        self._list_view = ft.ListView(expand=True, spacing=10)

        # Action buttons
        self._import_btn = ft.Button(
            _("import_strategy"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=self._on_import_click,
            bgcolor=ACCENT_COLOR,
            color=ft.Colors.WHITE,
        )
        self._refresh_btn = ft.Button(
            _("refresh"),
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self._load_strategies(),
        )

        # Import JSON text field (hidden by default)
        self._import_field = ft.TextField(
            hint_text=_("paste_strategy_json"),
            multiline=True,
            min_lines=6,
            max_lines=12,
            visible=False,
            expand=True,
        )
        self._import_confirm_btn = ft.Button(
            _("confirm_import"),
            icon=ft.Icons.CHECK,
            on_click=self._do_import,
            bgcolor=SUCCESS_COLOR,
            color=ft.Colors.WHITE,
            visible=False,
        )
        self._import_cancel_btn = ft.Button(
            _("cancel"),
            icon=ft.Icons.CANCEL,
            on_click=self._cancel_import,
            visible=False,
        )

        # Export form (for creating new strategies)
        self._show_export_form = False
        self._export_name_field = ft.TextField(hint_text=_("strategy_name"), width=200)
        self._export_desc_field = ft.TextField(hint_text=_("description"), width=300)
        self._export_author_field = ft.TextField(hint_text=_("author"), width=150)
        self._export_fast_ma_field = ft.TextField(hint_text=_("fast_ma"), value="5", width=80)
        self._export_slow_ma_field = ft.TextField(hint_text=_("slow_ma"), value="20", width=80)
        self._export_capital_field = ft.TextField(hint_text=_("initial_capital"), value="100000", width=120)
        self._export_stop_loss_field = ft.TextField(hint_text=_("stop_loss_pct"), value="-5.0", width=100)
        self._export_entry_rule_field = ft.TextField(hint_text=_("entry_rule_hint"), width=250)
        self._export_exit_rule_field = ft.TextField(hint_text=_("exit_rule_hint"), width=250)

        self._export_form = ft.Container(
            content=ft.Column([
                ft.Text(_("create_new_strategy"), size=16, weight=ft.FontWeight.BOLD),
                ft.Row([self._export_name_field, self._export_author_field]),
                ft.Row([self._export_desc_field]),
                ft.Row([
                    ft.Text(_("fast_ma") + ":", size=14),
                    self._export_fast_ma_field,
                    ft.Text(_("slow_ma") + ":", size=14),
                    self._export_slow_ma_field,
                    ft.Text(_("initial_capital") + ":", size=14),
                    self._export_capital_field,
                    ft.Text(_("stop_loss_pct") + ":", size=14),
                    self._export_stop_loss_field,
                ]),
                ft.Row([
                    ft.Text(_("entry_rule") + ":", size=14),
                    self._export_entry_rule_field,
                    ft.Text(_("exit_rule") + ":", size=14),
                    self._export_exit_rule_field,
                ]),
                ft.Row([
                    ft.Button(
                        _("save_strategy"),
                        icon=ft.Icons.SAVE,
                        on_click=self._do_export,
                        bgcolor=SUCCESS_COLOR,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Button(
                        _("cancel"),
                        icon=ft.Icons.CANCEL,
                        on_click=self._cancel_export,
                    ),
                ]),
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=False,
        )

        self._export_toggle_btn = ft.Button(
            _("new_strategy"),
            icon=ft.Icons.ADD,
            on_click=self._toggle_export_form,
        )

        # Import area
        self._import_area = ft.Container(
            content=ft.Column([
                ft.Text(_("import_strategy_json"), size=16, weight=ft.FontWeight.BOLD),
                self._import_field,
                ft.Row([self._import_confirm_btn, self._import_cancel_btn]),
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=False,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                desc,
                ft.Divider(height=2, color=CARD_BORDER),
                ft.Row([self._refresh_btn, self._import_btn, self._export_toggle_btn]),
                ft.Container(height=10),
                self._import_area,
                self._export_form,
                ft.Container(height=10),
                ft.Container(
                    content=self._list_view,
                    expand=True,
                    border=ft.border.all(1, CARD_BORDER),
                    border_radius=5,
                    padding=10,
                ),
            ], scroll=ft.ScrollMode.AUTO),
            padding=10,
            expand=True,
        )

    def _load_strategies(self):
        """Load strategies from DataService"""
        try:
            resp = self._client._send_request("list_strategies")
            if resp.get("status") == "ok":
                self._strategies = resp.get("data", [])
            else:
                self._strategies = []
        except Exception:
            self._strategies = []

        self._refresh_list()

    def _refresh_list(self):
        """Refresh the strategy list display"""
        self._list_view.controls.clear()

        if not self._strategies:
            self._list_view.controls.append(
                ft.Text(_("no_strategies"), color=TEXT_SECONDARY, italic=True)
            )
            try:
                self._list_view.update()
            except Exception:
                pass
            return

        for i, strat in enumerate(self._strategies):
            name = strat.get("name", _("unnamed"))
            desc = strat.get("description", "")
            author = strat.get("author", "")
            version = strat.get("version", "1.0")
            params = strat.get("params", {})
            entry = strat.get("entry_rule", "")
            exit = strat.get("exit_rule", "")

            # Build summary line
            summary_parts = []
            if author:
                summary_parts.append(f"@{author}")
            if version:
                summary_parts.append(f"v{version}")
            if entry:
                summary_parts.append(f"{_('entry')}: {entry}")
            if exit:
                summary_parts.append(f"{_('exit')}: {exit}")
            summary_text = " | ".join(summary_parts)

            title_row = ft.Row([
                ft.Text(f"{name}", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(summary_text, size=12, color=TEXT_SECONDARY),
            ])

            desc_row = ft.Container()
            if desc:
                desc_row = ft.Row([ft.Text(desc, size=13, color=TEXT_SECONDARY)])

            params_text = ", ".join(f"{k}={v}" for k, v in params.items())
            params_row = ft.Row([
                ft.Text(f"{_('params')}: {params_text}", size=12, color=TEXT_SECONDARY),
            ])

            action_row = ft.Row([
                ft.Button(
                    _("run_backtest"),
                    icon=ft.Icons.PLAY_ARROW,
                    on_click=lambda e, s=strat: self._run_strategy(s),
                    bgcolor=ACCENT_COLOR,
                    color=ft.Colors.WHITE,
                ),
                ft.Button(
                    _("export_strategy"),
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e, s=strat: self._export_strategy(s),
                ),
                ft.Button(
                    _("delete"),
                    icon=ft.Icons.DELETE,
                    on_click=lambda e, n=name: self._delete_strategy(n),
                    bgcolor=ERROR_COLOR,
                    color=ft.Colors.WHITE,
                ),
            ])

            card = ft.Container(
                content=ft.Column([
                    title_row,
                    desc_row,
                    params_row,
                    action_row,
                ]),
                padding=10,
                bgcolor=CARD_BG,
                border_radius=8,
            )
            self._list_view.controls.append(card)

        try:
            self._list_view.update()
        except Exception:
            pass

    def _run_strategy(self, strategy: dict):
        """Run backtest with strategy parameters"""
        params = strategy.get("params", {})
        code = params.get("code", "000001")
        initial_capital = params.get("initial_capital", 100000)
        fast_ma = params.get("fast_ma", 5)
        slow_ma = params.get("slow_ma", 20)
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
                    f"Strategy: {strategy.get('name')}\n"
                    f"MA({fast_ma},{slow_ma}) | Capital: {initial_capital}\n"
                    f"Return: {data.get('total_return', 0)}% | "
                    f"Sharpe: {data.get('sharpe_ratio', 0)} | "
                    f"Trades: {data.get('num_trades', 0)} | "
                    f"Win Rate: {data.get('win_rate', 0)}%"
                )
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(msg), open=True)
                )
            else:
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"{_('backtest_failed')}: {resp.get('message', '')}"), open=True)
                )
        except Exception as e:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('backtest_failed')}: {str(e)}"), open=True)
            )

    def _export_strategy(self, strategy: dict):
        """Download strategy as JSON file"""
        try:
            json_str = json.dumps(strategy, ensure_ascii=False, indent=2)
            name = strategy.get("name", "strategy")
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").rstrip()

            # Use flet's FilePicker for download
            def save_result(e: ft.FilePickerResultEvent):
                if e.path:
                    try:
                        with open(e.path, "w", encoding="utf-8") as f:
                            f.write(json_str)
                        self.app.page.show_snack_bar(
                            ft.SnackBar(content=ft.Text(_("export_success")), open=True)
                        )
                    except Exception as ex:
                        self.app.page.show_snack_bar(
                            ft.SnackBar(content=ft.Text(f"{_('export_failed')}: {str(ex)}"), open=True)
                        )

            file_picker = ft.FilePicker(on_result=save_result)
            self.app.page.overlay.append(file_picker)
            self.app.page.update()
            file_picker.save_file(
                file_name=f"{safe_name}.json",
                initial_directory=None,
            )
        except Exception as e:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('export_failed')}: {str(e)}"), open=True)
            )

    def _delete_strategy(self, name: str):
        """Delete a strategy"""
        try:
            resp = self._client._send_request("delete_strategy", {"name": name})
            if resp.get("status") == "ok":
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(_("delete_success")), open=True)
                )
                self._load_strategies()
            else:
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"{_('delete_failed')}: {resp.get('message', '')}"), open=True)
                )
        except Exception as e:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('delete_failed')}: {str(e)}"), open=True)
            )

    def _on_import_click(self, e):
        """Show import area"""
        self._import_area.visible = True
        self._import_field.visible = True
        self._import_confirm_btn.visible = True
        self._import_cancel_btn.visible = True
        self._import_area.update()
        self.content.update()

    def _cancel_import(self, e):
        """Hide import area"""
        self._import_area.visible = False
        self._import_field.visible = False
        self._import_confirm_btn.visible = False
        self._import_cancel_btn.visible = False
        self._import_field.value = ""
        self._import_area.update()
        self.content.update()

    def _do_import(self, e):
        """Execute strategy import from JSON text"""
        json_text = self._import_field.value.strip()
        if not json_text:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("paste_strategy_json")), open=True)
            )
            return

        try:
            resp = self._client._send_request("import_strategy", {"data": json_text})
            if resp.get("status") == "ok":
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(_("import_success")), open=True)
                )
                self._cancel_import(e)
                self._load_strategies()
            else:
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"{_('import_failed')}: {resp.get('message', '')}"), open=True)
                )
        except Exception as ex:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('import_failed')}: {str(ex)}"), open=True)
            )

    def _toggle_export_form(self, e):
        """Toggle new strategy form visibility"""
        self._show_export_form = not self._show_export_form
        self._export_form.visible = self._show_export_form
        self._export_form.update()
        self.content.update()

    def _cancel_export(self, e):
        """Hide export form"""
        self._show_export_form = False
        self._export_form.visible = False
        self._export_form.update()
        self.content.update()

    def _do_export(self, e):
        """Create and export a new strategy"""
        name = self._export_name_field.value.strip()
        if not name:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(_("enter_strategy_name")), open=True)
            )
            return

        strategy_data = {
            "name": name,
            "version": "1.0",
            "description": self._export_desc_field.value.strip(),
            "author": self._export_author_field.value.strip(),
            "params": {
                "fast_ma": int(self._export_fast_ma_field.value.strip() or "5"),
                "slow_ma": int(self._export_slow_ma_field.value.strip() or "20"),
                "initial_capital": float(self._export_capital_field.value.strip() or "100000"),
                "stop_loss_pct": float(self._export_stop_loss_field.value.strip() or "-5.0"),
            },
            "code": "python",
            "indicators": ["ma5", "ma20"],
            "entry_rule": self._export_entry_rule_field.value.strip(),
            "exit_rule": self._export_exit_rule_field.value.strip(),
        }

        try:
            resp = self._client._send_request("export_strategy", strategy_data)
            if resp.get("status") == "ok":
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(_("export_success")), open=True)
                )
                self._cancel_export(e)
                self._load_strategies()
                # Clear form
                self._export_name_field.value = ""
                self._export_desc_field.value = ""
                self._export_author_field.value = ""
                self._export_entry_rule_field.value = ""
                self._export_exit_rule_field.value = ""
            else:
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"{_('export_failed')}: {resp.get('message', '')}"), open=True)
                )
        except Exception as ex:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('export_failed')}: {str(ex)}"), open=True)
            )
