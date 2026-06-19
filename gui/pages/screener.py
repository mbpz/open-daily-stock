"""Stock Screener Page - Filter stocks by market cap, PE, industry, price change %."""
import flet as ft
from gui.components.async_task import AsyncTaskMixin
from gui.theme import CARD_BG, CARD_BORDER, ACCENT_COLOR, SUCCESS_COLOR
from src.i18n import _


class ScreenerPage(AsyncTaskMixin, ft.Container):
    """Stock screener page with filter form and results table."""

    def __init__(self, app, service_client=None):
        # Init base container + mixin first
        ft.Container.__init__(self)
        AsyncTaskMixin.__init__(self, app)
        self.app = app
        self._service_client = service_client

        header = ft.Text(_("股票选股器"), size=24, weight=ft.FontWeight.BOLD)

        # Filter section
        self._market_cap_min_field = ft.TextField(
            label=_("最小市值(亿)"),
            width=150,
            hint_text="如: 100",
        )
        self._market_cap_max_field = ft.TextField(
            label=_("最大市值(亿)"),
            width=150,
            hint_text="如: 1000",
        )
        self._pe_min_field = ft.TextField(
            label=_("最小PE"),
            width=120,
            hint_text="如: 5",
        )
        self._pe_max_field = ft.TextField(
            label=_("最大PE"),
            width=120,
            hint_text="如: 50",
        )
        self._change_pct_min_field = ft.TextField(
            label=_("最小涨跌幅(%)"),
            width=130,
            hint_text="如: -5",
        )
        self._change_pct_max_field = ft.TextField(
            label=_("最大涨跌幅(%)"),
            width=130,
            hint_text="如: 10",
        )
        self._industry_field = ft.TextField(
            label=_("行业"),
            width=150,
            hint_text="如: 银行",
        )

        filter_row = ft.Row([
            ft.Column([
                ft.Text(_("市值(亿)"), size=12, color="#a0a0a0"),
                ft.Row([self._market_cap_min_field, ft.Text("-"), self._market_cap_max_field]),
            ]),
            ft.Column([
                ft.Text(_("市盈率(PE)"), size=12, color="#a0a0a0"),
                ft.Row([self._pe_min_field, ft.Text("-"), self._pe_max_field]),
            ]),
            ft.Column([
                ft.Text(_("涨跌幅(%)"), size=12, color="#a0a0a0"),
                ft.Row([self._change_pct_min_field, ft.Text("-"), self._change_pct_max_field]),
            ]),
            ft.Column([
                ft.Text(_("行业"), size=12, color="#a0a0a0"),
                self._industry_field,
            ]),
        ])

        search_btn = ft.Button(
            _("开始筛选"),
            icon=ft.Icons.SEARCH,
            on_click=self._do_screener,
            bgcolor=ACCENT_COLOR,
            color=ft.Colors.WHITE,
        )

        # Results section
        self._results_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(_("代码"))),
                ft.DataColumn(ft.Text(_("名称"))),
                ft.DataColumn(ft.Text(_("最新价"))),
                ft.DataColumn(ft.Text(_("涨跌幅"))),
                ft.DataColumn(ft.Text(_("市盈率"))),
                ft.DataColumn(ft.Text(_("市净率"))),
                ft.DataColumn(ft.Text(_("总市值(亿)"))),
                ft.DataColumn(ft.Text(_("操作"))),
            ],
            rows=[],
        )

        self._results_container = ft.Container(
            content=ft.ListView([self._results_table]),
            padding=10,
            bgcolor=CARD_BG,
            border_radius=10,
            height=400,
            visible=False,
        )

        self._status_text = ft.Text("", color="#a0a0a0")

        filter_section = ft.Container(
            content=ft.Column([
                filter_row,
                ft.Container(height=10),
                search_btn,
                self._status_text,
            ]),
            padding=15,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                filter_section,
                ft.Container(height=20),
                ft.Text(_("筛选结果"), size=18, weight=ft.FontWeight.BOLD),
                self._results_container,
            ]),
            padding=10,
        )

    def _do_screener(self, e):
        """Execute screener with filter criteria — uses AsyncTaskMixin for cancellation."""
        if self._service_client is None:
            self.set_status("⚠️ " + _("服务未连接"))
            return

        criteria = {}
        for field_name, key in [
            ("_market_cap_min_field", "market_cap_min"),
            ("_market_cap_max_field", "market_cap_max"),
            ("_pe_min_field", "pe_min"),
            ("_pe_max_field", "pe_max"),
            ("_change_pct_min_field", "change_pct_min"),
            ("_change_pct_max_field", "change_pct_max"),
        ]:
            value = getattr(self, field_name).value
            if value:
                try:
                    criteria[key] = float(value)
                except ValueError:
                    pass
        if self._industry_field.value:
            criteria["industry"] = self._industry_field.value.strip()

        self.set_status(_("正在筛选..."))
        self.run_async(self._run_screener_async, criteria)

    async def _run_screener_async(self, criteria):
        """Run screener asynchronously — honours cancellation via mixin."""
        try:
            if self.check_cancelled():
                return
            result = await self._service_client.screen_stocks(criteria)
            if self.check_cancelled():
                return
            if result.get("status") == "ok":
                data = result.get("data", [])
                count = result.get("count", len(data))
                self._update_results(data)
                self.set_status(f"✅ 共找到 {count} 只符合条件的股票")
            else:
                self.set_status(f"⚠️ {result.get('message', _('筛选失败'))}")
        except Exception as ex:
            self.set_status(f"⚠️ {_('筛选失败: ')}{str(ex)}")

    def _update_results(self, data):
        """Update results table with filtered stocks"""
        self._results_table.rows = []
        for stock in data[:100]:  # Limit to 100 results
            # Format values
            code = stock.get("code", "")
            name = stock.get("name", "")
            price = stock.get("price")
            change_pct = stock.get("change_pct")
            pe = stock.get("pe")
            pb = stock.get("pb")
            total_mv = stock.get("total_mv")

            # Format display values
            price_str = f"{price:.2f}" if price else "-"
            change_str = f"{change_pct:+.2f}%" if change_pct is not None else "-"
            pe_str = f"{pe:.2f}" if pe else "-"
            pb_str = f"{pb:.2f}" if pb else "-"
            mv_str = f"{total_mv / 1e8:.2f}" if total_mv else "-"

            # Color for change_pct
            change_color = "#ff0000" if change_pct and change_pct < 0 else "#00aa00" if change_pct and change_pct > 0 else "#a0a0a0"

            row = ft.DataRow(cells=[
                ft.DataCell(ft.Text(code)),
                ft.DataCell(ft.Text(name)),
                ft.DataCell(ft.Text(price_str)),
                ft.DataCell(ft.Text(change_str, color=change_color)),
                ft.DataCell(ft.Text(pe_str)),
                ft.DataCell(ft.Text(pb_str)),
                ft.DataCell(ft.Text(mv_str)),
                ft.DataCell(
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE,
                        tooltip=_("加入自选股"),
                        on_click=lambda e, c=code: self._add_to_watchlist(c),
                    )
                ),
            ])
            self._results_table.rows.append(row)

        self._results_container.visible = True
        self._results_container.update()
        self._results_table.update()

    def _add_to_watchlist(self, code):
        """Add stock to watchlist via config update"""
        try:
            from src.config import get_config
            config = get_config()
            if code not in config.stock_list:
                config.stock_list.append(code)
                updates = {"STOCK_LIST": ",".join(config.stock_list)}
                config.save_to_env(updates)
                self.app.page.show_snack_bar(
                    ft.SnackBar(content=ft.Text(f"{code} {_('已加入自选股')}"), open=True)
                )
        except Exception as ex:
            self.app.page.show_snack_bar(
                ft.SnackBar(content=ft.Text(f"{_('加入失败: ')}{str(ex)}"), open=True)
            )