"""Markets module showing real-time stock quotes with auto-poll."""
from textual.widgets import Static
from tui.data.wrapper import DataProviderWrapper, MarketData
from src.i18n import _
from datetime import datetime, timezone, timedelta


def get_market_status() -> dict:
    """Get market status for A股, HK, US markets"""
    now = datetime.now()
    cn_tz = timezone(timedelta(hours=8))
    now_cn = now.astimezone(cn_tz)
    current_time = now_cn.strftime("%H:%M")
    day_of_week = now_cn.weekday()  # 0=Monday, 6=Sunday

    status = {}

    # A股: 9:30-11:30, 13:00-15:00 CST (Mon-Fri)
    if day_of_week < 5:
        if "09:30" <= current_time <= "11:30" or "13:00" <= current_time <= "15:00":
            status['A股'] = ('🟢', '交易中')
        elif "09:00" <= current_time < "09:30" or "11:30" < current_time < "13:00":
            status['A股'] = ('🟡', '盘前')
        else:
            status['A股'] = ('⚪', '已休市')
    else:
        status['A股'] = ('⚪', '已休市')

    # HK: 9:30-12:00, 13:00-16:00 HKT (Mon-Fri)
    hk_tz = timezone(timedelta(hours=9))
    now_hk = now.astimezone(hk_tz)
    hk_time = now_hk.strftime("%H:%M")
    if day_of_week < 5:
        if "09:30" <= hk_time <= "12:00" or "13:00" <= hk_time <= "16:00":
            status['港股'] = ('🟢', '交易中')
        elif "09:00" <= hk_time < "09:30" or "12:00" < hk_time < "13:00":
            status['港股'] = ('🟡', '盘前')
        else:
            status['港股'] = ('⚪', '已休市')
    else:
        status['港股'] = ('⚪', '已休市')

    # US: 9:30-16:00 EST (Mon-Fri)
    est_tz = timezone(timedelta(hours=-5))
    now_est = now.astimezone(est_tz)
    us_time = now_est.strftime("%H:%M")
    if day_of_week < 5:
        if "09:30" <= us_time <= "16:00":
            status['美股'] = ('🟢', '交易中')
        elif "04:00" <= us_time < "09:30":
            status['美股'] = ('🟡', '盘前')
        else:
            status['美股'] = ('⚪', '已休市')
    else:
        status['美股'] = ('⚪', '已休市')

    return status


def _format_volume_display(vol, code: str) -> str:
    """Format volume to wanyij unit."""
    try:
        v = float(vol)
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
        return "---"


class MarketsView(Static):
    """Display stock market data with auto-refresh."""
    def __init__(self, data_provider: DataProviderWrapper):
        super().__init__()
        self._dp = data_provider
        self._previous_prices = {}  # code -> price
        self._flashed_codes = set()

    def compose(self):
        # Market status indicators
        status = get_market_status()
        status_line = "  " + "  ".join([f"{e} {m}" for m, (e, _) in status.items()])

        app = self.app
        if getattr(app, '_wizard_skipped', False):
            yield Static(_("⚠️ 请先配置（按 4 进入 Config）"), id="wizard-warning")
        yield Static(_("实时行情"), id="markets-title")
        yield Static(status_line, id="market-status")
        yield Static(self._render_data(), id="markets-data")

    def _render_data(self) -> str:
        data = self._dp.get_data()
        lines = [_("  代码        名称        最新价      涨跌        成交量  ")]
        lines.append("  " + "-" * 60)
        if not data:
            lines.append(_("  暂无数据，使用 [r] 手动刷新或等待自动更新"))
            return "\n".join(lines)
        for code, m in data.items():
            emoji = "🟢" if m.change > 0 else "🔴" if m.change < 0 else "⚪"
            sign = "+" if m.change > 0 else ""
            volume_str = _format_volume_display(m.volume, code)

            # Check for price change flash
            prev_price = self._previous_prices.get(code)
            price_display = f"{m.price:>10.2f}"
            if prev_price is not None and abs(m.price - prev_price) > 0.01:
                # Flash effect - ANSI highlight
                price_display = f"\033[93m{m.price:>10.2f}\033[0m"

            lines.append(
                f"  {m.code:<10} {m.name:<8} {price_display} {emoji}{sign}{m.change:>5.2f}% {volume_str:>10}"
            )
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)

    def update_data(self):
        """Called when data is refreshed - update flash tracking"""
        data = self._dp.get_data()
        for code, m in data.items():
            self._previous_prices[code] = m.price