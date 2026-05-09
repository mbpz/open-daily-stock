"""行情页面"""
import flet as ft
import asyncio
from datetime import datetime
from gui.theme import SUCCESS_COLOR, ERROR_COLOR, TEXT_SECONDARY, CARD_BG, CARD_BORDER, WARNING_COLOR
from src.i18n import _


def get_market_status() -> dict:
    """Get market status for A股, HK, US markets"""
    now = datetime.now()
    # Use a fixed date for timezone handling
    cn_tz = __import__('datetime').timezone(__import__('datetime').timedelta(hours=8))
    now_cn = now.astimezone(cn_tz)
    current_time = now_cn.strftime("%H:%M")
    day_of_week = now_cn.weekday()  # 0=Monday, 6=Sunday

    status = {}

    # A股: 9:30-11:30, 13:00-15:00 CST (Mon-Fri)
    if day_of_week < 5:
        if "09:30" <= current_time <= "11:30" or "13:00" <= current_time <= "15:00":
            status['A股'] = ('🟢', _('交易中'))
        elif "09:00" <= current_time < "09:30" or "11:30" < current_time < "13:00":
            status['A股'] = ('🟡', _('盘前'))
        else:
            status['A股'] = ('⚪', _('已休市'))
    else:
        status['A股'] = ('⚪', _('已休市'))

    # HK: 9:30-12:00, 13:00-16:00 HKT (Mon-Fri)
    hk_tz = __import__('datetime').timezone(__import__('datetime').timedelta(hours=9))
    now_hk = now.astimezone(hk_tz)
    hk_time = now_hk.strftime("%H:%M")
    if day_of_week < 5:
        if "09:30" <= hk_time <= "12:00" or "13:00" <= hk_time <= "16:00":
            status['港股'] = ('🟢', _('交易中'))
        elif "09:00" <= hk_time < "09:30" or "12:00" < hk_time < "13:00":
            status['港股'] = ('🟡', _('盘前'))
        else:
            status['港股'] = ('⚪', _('已休市'))
    else:
        status['港股'] = ('⚪', _('已休市'))

    # US: 9:30-16:00 EST (Mon-Fri)
    est_tz = __import__('datetime').timezone(__import__('datetime').timedelta(hours=-5))
    now_est = now.astimezone(est_tz)
    us_time = now_est.strftime("%H:%M")
    if day_of_week < 5:
        if "09:30" <= us_time <= "16:00":
            status['美股'] = ('🟢', _('交易中'))
        elif "04:00" <= us_time < "09:30":
            status['美股'] = ('🟡', _('盘前'))
        else:
            status['美股'] = ('⚪', _('已休市'))
    else:
        status['美股'] = ('⚪', _('已休市'))

    return status


def format_volume_display(volume: float, code: str) -> str:
    """Format volume for display based on market type"""
    if volume is None or volume == '':
        return '---'
    try:
        v = float(volume)
        # A股/港股 use 万 (ten thousands)
        if code.startswith('hk') or (len(code) == 6 and code.isdigit() and not code.startswith('9')):
            if v >= 100000000:
                return f"{v/100000000:.1f}亿"
            elif v >= 10000:
                return f"{v/10000:.0f}万"
            return f"{v:.0f}"
        else:
            # US stocks use M/B notation
            if v >= 1000000000:
                return f"{v/1000000000:.1f}B"
            elif v >= 1000000:
                return f"{v/1000000:.1f}M"
            elif v >= 1000:
                return f"{v/1000:.1f}K"
            return f"{v:.0f}"
    except (ValueError, TypeError):
        return '---'


class MarketsPage(ft.Container):
    """行情展示页面"""

    def __init__(self, app, service_client):
        super().__init__()
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
        """生命周期钩子 - 页面挂载时触发异步数据获取"""
        self.app.page.run_task(self._fetch_and_update)

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
        """异步获取数据并更新界面"""
        markets = self._client.get_markets()
        self.table.rows.clear()
        self._load_data(markets)
        self.update()
        self.app.update_status(datetime.now().strftime("%H:%M:%S"))

    def _schedule_flash_clear(self):
        """Schedule flash clear after 300ms"""
        import threading
        def clear():
            import time
            time.sleep(0.3)
            self._flash_indices = set()
            self.app.page.run_task(self._fetch_and_update)
        t = threading.Thread(target=clear)
        t.daemon = True
        t.start()

    def _refresh(self, e):
        """刷新数据"""
        self.app.page.run_task(self._fetch_and_update)