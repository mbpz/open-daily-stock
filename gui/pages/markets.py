"""行情页面"""
import asyncio
import flet as ft
from datetime import datetime
from gui.components.async_task import AsyncTaskMixin
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER, WARNING_COLOR
from src.i18n import _
from src.shared.style import format_volume as _format_volume
from src.shared.market_status import get_all_market_statuses


def get_market_status_legacy() -> dict:
    """Get market status for A股, HK, US markets - legacy function."""
    status_dict = get_all_market_statuses()
    return {market: (emoji, text) for market, (emoji, text) in status_dict.items()}


def get_market_status() -> dict:
    """Get market status for A股, HK, US markets - uses shared module."""
    return get_market_status_legacy()


def format_volume_display(volume: float, code: str) -> str:
    """Format volume for display based on market type - uses shared module."""
    return _format_volume(volume, code)


class MarketsPage(AsyncTaskMixin, ft.Container):
    """行情展示页面"""

    def __init__(self, app, service_client):
        # Init base container + mixin first (cancellable background tasks)
        ft.Container.__init__(self)
        AsyncTaskMixin.__init__(self, app)
        self.app = app
        self._client = service_client
        self._previous_data = {}
        self._flash_indices = set()

        # Market status indicator row
        status_row = ft.Row([
            ft.Text(_("市场状态:"), size=14, color=TEXT_SECONDARY),
        ])
        self._status_indicators = status_row

        market_status = get_market_status()
        for market, (emoji, text) in market_status.items():
            status_row.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(emoji, size=12),
                        ft.Text(f"{market} {text}", size=12, color=ft.Colors.WHITE),
                    ], spacing=2),
                    padding=5,
                    bgcolor=CARD_BG,
                    border_radius=5,
                )
            )

        # 标题栏
        header = ft.Row([
            ft.Text(_("自选股行情"), size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                on_click=self._refresh,
                tooltip=_("刷新"),
            ),
        ])

        # 行情表格 - 初始显示加载占位
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text(_("代码"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("名称"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("最新价"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("涨跌幅"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("成交量"), weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text(_("操作"), weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
        )

        self._table_container = ft.Container(
            content=ft.ListView([self.table], expand=True),
            padding=10,
            bgcolor=CARD_BG,
            border_radius=10,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                self._status_indicators,
                ft.Container(height=5),
                self._table_container,
            ]),
            padding=10,
        )

    def on_mount(self):
        """Lifecycle hook — fetch initial data via the mixin so it's cancellable."""
        self.run_async(self._fetch_and_update)

    def _show_placeholder(self):
        """显示加载占位符"""
        self.table.rows.clear()
        self.table.rows.append(
            ft.DataRow(cells=[
                ft.DataCell(ft.Text(_("点击刷新获取数据"), color=TEXT_SECONDARY)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
            ])
        )
        self._table_container.update()

    def _load_data(self, markets):
        """加载行情数据"""
        self._flash_indices = set()
        for i, market in enumerate(markets):
            change = market.get('change', 0)
            change_str = f"{change:+.2f}%" if change != 0 else "0.00%"
            change_color = SUCCESS_COLOR if change >= 0 else ERROR_COLOR
            code = market.get('code', '')
            price = market.get('price', 0)

            # Check for price change and set flash
            prev_price = self._previous_data.get(code)
            if prev_price is not None and abs(price - prev_price) > 0.01:
                self._flash_indices.add(i)

            # Format volume (use pre-formatted if available)
            volume_raw = market.get('volume', 0)
            volume_display = market.get('volume_display') or format_volume_display(volume_raw, code)

            self.table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(code)),
                    ft.DataCell(ft.Text(market.get('name', ''))),
                    ft.DataCell(ft.Text(f"{price:.2f}")) if i not in self._flash_indices else ft.DataCell(
                        ft.Container(
                            content=ft.Text(f"{price:.2f}"),
                            bgcolor=WARNING_COLOR,
                            padding=5,
                            border_radius=5,
                        )
                    ),
                    ft.DataCell(ft.Text(change_str, color=change_color)),
                    ft.DataCell(ft.Text(volume_display)),
                    ft.DataCell(
                        ft.IconButton(
                            icon=ft.Icons.SHOW_CHART,
                            tooltip=_("查看K线"),
                            on_click=lambda e, c=code: self._show_chart(c),
                        )
                    ),
                ])
            )

        # Store current prices for next comparison
        for market in markets:
            code = market.get('code', '')
            price = market.get('price', 0)
            self._previous_data[code] = price

        # Flash effect fade out
        if self._flash_indices:
            self._schedule_flash_clear()

    def _show_chart(self, code):
        """打开K线图表页面"""
        self.app.nav_index = 0  # 切换到K线页面
        self.app.nav_rail.selected_index = 0
        self.app.page.run_task(self.app._load_page, "chart")
        # 设置股票代码到chart页面的输入框
        self.app.page.run_task(self._set_chart_code, code)

    async def _set_chart_code(self, code):
        """设置chart页面的股票代码"""
        await asyncio.sleep(0.1)  # 等待页面加载
        if hasattr(self.app, 'content_area') and hasattr(self.app.content_area, 'content'):
            content = self.app.content_area.content
            if hasattr(content, '_code_input'):
                content._code_input.value = code
                content._code_input.update()
                content._show_chart(None)  # 自动触发显示

    async def _fetch_and_update(self):
        """Fetch market data and update the table — honour cancellation."""
        try:
            if self.check_cancelled():
                return
            # run_async already set busy; no progress ring here so no-op.
            markets = self._client.get_markets()
            if self.check_cancelled():
                return
            self.table.rows.clear()
            self._load_data(markets)
            self.update()
            self.app.update_status(datetime.now().strftime("%H:%M:%S"))
        finally:
            # Even if we never had a busy indicator, run_async's done
            # callback will set_idle for us; but be explicit for clarity.
            self.set_idle()

    def _schedule_flash_clear(self):
        """Schedule flash clear after 300ms via the mixin (cancellable)."""
        self.run_async(self._clear_flash_after_delay)

    async def _clear_flash_after_delay(self):
        try:
            await asyncio.sleep(0.3)
            if self.check_cancelled():
                return
            self._flash_indices = set()
            if self._table_container.page is not None:
                self._table_container.update()
        except asyncio.CancelledError:
            pass
        except Exception:
            # Swallow: page teardown is non-fatal
            pass

    def _refresh(self, e):
        """Refresh — delegate to mixin for cancellation + busy state."""
        self.run_async(self._fetch_and_update)