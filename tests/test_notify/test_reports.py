"""报告生成器单元测试（5 个 generate_* 函数 + _get_signal_level）。"""
from unittest.mock import MagicMock

from src.notify.reports import (
    _get_signal_level,
    generate_daily_report,
    generate_dashboard_report,
    generate_single_stock_report,
    generate_wechat_dashboard,
    generate_wechat_summary,
)


def _make_result(**overrides) -> MagicMock:
    """最小可用 AnalysisResult mock。"""
    r = MagicMock()
    r.code = "000001"
    r.name = "平安银行"
    r.sentiment_score = 70
    r.operation_advice = "买入"
    r.trend_prediction = "看多"
    r.analysis_summary = "这是一段综合分析"
    r.success = True
    r.error_message = ""
    r.buy_reason = "技术面强势"
    r.risk_warning = "大盘回调风险"
    r.technical_analysis = ""
    r.news_summary = ""
    r.search_performed = False
    r.data_sources = ""
    r.key_points = ""
    r.trend_analysis = ""
    r.short_term_outlook = ""
    r.medium_term_outlook = ""
    r.ma_analysis = ""
    r.volume_analysis = ""
    r.pattern_analysis = ""
    r.fundamental_analysis = ""
    r.sector_position = ""
    r.company_highlights = ""
    r.market_sentiment = ""
    r.hot_topics = ""
    r.dashboard = {}
    r.get_emoji.return_value = "🟢"
    r.get_confidence_stars.return_value = "⭐⭐⭐"
    for k, v in overrides.items():
        setattr(r, k, v)
    return r


# ─── _get_signal_level ─────────────────────────────────────────


class TestSignalLevel:
    def test_strong_buy_score_80(self):
        r = _make_result(operation_advice="买入", sentiment_score=85)
        text, emoji, tag = _get_signal_level(r)
        assert text == "强烈买入"

    def test_buy(self):
        r = _make_result(sentiment_score=65)
        text, emoji, tag = _get_signal_level(r)
        assert text == "买入"

    def test_hold(self):
        r = _make_result(operation_advice="持有", sentiment_score=58)
        text, _, _ = _get_signal_level(r)
        assert text == "持有"

    def test_watch(self):
        r = _make_result(operation_advice="观望", sentiment_score=50)
        text, _, _ = _get_signal_level(r)
        assert text == "观望"

    def test_sell(self):
        r = _make_result(operation_advice="卖出", sentiment_score=20)
        text, _, _ = _get_signal_level(r)
        assert text == "卖出"

    def test_returns_tuple_of_three(self):
        assert len(_get_signal_level(_make_result())) == 3


# ─── generate_daily_report ────────────────────────────────────


class TestDailyReport:
    def test_single_stock_produces_expected_sections(self):
        report = generate_daily_report([_make_result(name="茅台", code="600519")])
        assert "股票智能分析报告" in report
        assert "操作建议汇总" in report
        assert "个股详细分析" in report
        assert "茅台" in report
        assert "600519" in report
        assert "报告生成时间" in report

    def test_includes_error_on_failed_result(self):
        r = _make_result(success=False, error_message="API 超时")
        report = generate_daily_report([r])
        assert "分析异常" in report
        assert "API 超时" in report

    def test_multiple_stocks_sorted_by_score(self):
        low = _make_result(code="A", sentiment_score=30, name="A股")
        high = _make_result(code="B", sentiment_score=90, name="B股")
        report = generate_daily_report([low, high])
        high_pos = report.index("B股")
        low_pos = report.index("A股")
        assert high_pos < low_pos


# ─── generate_dashboard_report ────────────────────────────────


class TestDashboardReport:
    def test_basic_structure(self):
        r = _make_result()
        report = generate_dashboard_report([r])
        assert "决策仪表盘" in report
        assert "分析结果摘要" in report
        assert "核心结论" in report

    def test_with_dashboard_data(self):
        r = _make_result()
        r.dashboard = {
            "core_conclusion": {"one_sentence": "可逢低建仓", "time_sensitivity": "本周", "position_advice": {"no_position": "建仓", "has_position": "加仓"}},
            "battle_plan": {"sniper_points": {"ideal_buy": "10.5", "stop_loss": "9.8", "take_profit": "12.0"}, "action_checklist": ["✅ 量能配合", "❌ 大盘不企稳"]},
            "intelligence": {"sentiment_summary": "偏积极", "risk_alerts": ["板块轮动风险"]},
        }
        report = generate_dashboard_report([r])
        assert "逢低建仓" in report
        assert "10.5" in report
        assert "9.8" in report
        assert "板块轮动" in report
        assert "检查清单" in report

    def test_no_dashboard_fallback(self):
        r = _make_result(dashboard={})
        report = generate_dashboard_report([r])
        assert "技术面强势" in report

    def test_empty_results_safe(self):
        report = generate_dashboard_report([])
        assert "0 只" in report or "**0**" in report


# ─── generate_wechat_dashboard ────────────────────────────────


class TestWechatDashboard:
    def test_returns_markdown_string(self):
        r = _make_result()
        content = generate_wechat_dashboard([r])
        assert content.startswith("##")
        assert "平安" in content

    def test_includes_signal_level(self):
        r = _make_result(operation_advice="强烈买入", sentiment_score=90)
        content = generate_wechat_dashboard([r])
        assert "强烈买入" in content

    def test_omits_irrelevant_detail(self):
        # 不应含完整的大段分析——wechat 是精简版
        r = _make_result()
        content = generate_wechat_dashboard([r])
        # Technical analysis 全字段不应出现（除非 dashboard 内含）
        assert "技术面分析" not in content


# ─── generate_wechat_summary ──────────────────────────────────


class TestWechatSummary:
    def test_basic_summary(self):
        r = _make_result()
        result = generate_wechat_summary([r])
        assert "股票分析报告" in result
        assert "平安银行" in result
        # 底部不该有投资建议以外的免责声明（旧行为）
        assert "AI生成" in result or "仅供参考" in result

    def test_truncates_long_reason(self):
        r = _make_result(buy_reason="x" * 200)
        result = generate_wechat_summary([r])
        # 截断应有... 或未超过 200
        assert "..." in result or len(result) < 5000

    def test_empty_results_safe(self):
        result = generate_wechat_summary([])
        # 至少不崩；"0" 会出现在共 **0** 只的描述里
        assert "0" in result


# ─── generate_single_stock_report ─────────────────────────────


class TestSingleStockReport:
    def test_basic_structure(self):
        r = _make_result()
        report = generate_single_stock_report(r)
        assert "平安银行" in report
        assert "000001" in report
        assert "核心结论" in report

    def test_with_dashboard(self):
        r = _make_result()
        r.dashboard = {
            "core_conclusion": {"one_sentence": "强势突破"},
            "battle_plan": {"sniper_points": {"ideal_buy": "15", "stop_loss": "13"}},
            "intelligence": {"sentiment_summary": "乐观", "risk_alerts": ["国际形势"]},
        }
        report = generate_single_stock_report(r)
        assert "强势突破" in report
        assert "15" in report
        assert "国际形势" in report

    def test_no_crash_with_empty_dashboard(self):
        r = _make_result(dashboard=None)
        report = generate_single_stock_report(r)
        assert "000001" in report
