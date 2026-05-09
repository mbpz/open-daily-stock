"""Markets module showing real-time stock quotes with auto-poll."""
from textual.widgets import Static
from tui.data.wrapper import DataProviderWrapper, MarketData
from src.i18n import _
from src.shared.style import format_volume as _format_volume
from src.shared.market_status import get_all_market_statuses, MarketStatus


def get_market_status_legacy() -> dict:
    """Get market status for A股, HK, US markets - legacy function."""
    status_dict = get_all_market_statuses()
    return {market: (emoji, text) for market, (emoji, text) in status_dict.items()}


class MarketsView(Static):
    """Display stock market data with auto-refresh."""
    def __init__(self, data_provider: DataProviderWrapper):
        super().__init__()
        self._dp = data_provider
        self._previous_prices = {}  # code -> price
        self._flashed_codes = set()

    def compose(self):
        # Market status indicators
        status = get_market_status_legacy()
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
            volume_str = _format_volume(m.volume, code)

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