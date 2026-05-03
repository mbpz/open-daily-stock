"""Markets module showing real-time stock quotes with auto-poll."""
from textual.widgets import Static
from tui.data.wrapper import DataProviderWrapper, MarketData
from src.i18n import _

class MarketsView(Static):
    """Display stock market data with auto-refresh."""
    def __init__(self, data_provider: DataProviderWrapper):
        super().__init__()
        self._dp = data_provider

    def compose(self):
        # 跳过引导后的提示条
        app = self.app
        if getattr(app, '_wizard_skipped', False):
            yield Static(_("⚠️ 请先配置（按 4 进入 Config）"), id="wizard-warning")
        yield Static(_("实时行情"), id="markets-title")
        # 数据显示
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
            lines.append(
                f"  {m.code:<10} {m.name:<8} {m.price:>10.2f} {emoji}{sign}{m.change:>5.2f}% {m.volume:>10}"
            )
        return "\n".join(lines)

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.background = "#1a1a2e"
        self.styles.color = "#e8e8e8"
        self.styles.padding = (1, 1)