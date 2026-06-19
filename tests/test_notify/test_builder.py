"""NotificationBuilder 单元测试。"""
from unittest.mock import MagicMock

from src.notify.builder import NotificationBuilder


class TestBuildSimpleAlert:
    def test_info_type(self):
        result = NotificationBuilder.build_simple_alert("标题", "内容", "info")
        assert "ℹ️" in result
        assert "**标题**" in result
        assert "内容" in result

    def test_warning_type(self):
        assert "⚠️" in NotificationBuilder.build_simple_alert("x", "y", "warning")

    def test_error_type(self):
        assert "❌" in NotificationBuilder.build_simple_alert("x", "y", "error")

    def test_success_type(self):
        assert "✅" in NotificationBuilder.build_simple_alert("x", "y", "success")

    def test_unknown_type_falls_back_to_speaker(self):
        assert "📢" in NotificationBuilder.build_simple_alert("x", "y", "unknown")

    def test_default_type_is_info(self):
        result = NotificationBuilder.build_simple_alert("x", "y")
        assert "ℹ️" in result


class TestBuildStockSummary:
    def _make_result(self, code: str, name: str, score: float, advice: str, emoji: str = "🟢"):
        r = MagicMock()
        r.code = code
        r.name = name
        r.sentiment_score = score
        r.operation_advice = advice
        r.get_emoji.return_value = emoji
        return r

    def test_single_stock(self):
        results = [self._make_result("000001", "平安", 80, "买入")]
        out = NotificationBuilder.build_stock_summary(results)
        assert "📊" in out
        assert "今日自选股摘要" in out
        assert "平安" in out
        assert "000001" in out
        assert "80" in out

    def test_sorted_by_score_desc(self):
        results = [
            self._make_result("A", "低", 30, "卖出"),
            self._make_result("B", "高", 90, "买入"),
            self._make_result("C", "中", 60, "持有"),
        ]
        out = NotificationBuilder.build_stock_summary(results)
        lines = out.split("\n")
        # 第二行应是最高分 (index 1 is first data line)
        data_lines = [l for l in lines if l and not l.startswith("📊")]
        assert "高" in data_lines[0]
        assert "低" in data_lines[-1]

    def test_empty_list(self):
        out = NotificationBuilder.build_stock_summary([])
        assert "📊" in out
        # 不应抛异常
        assert isinstance(out, str)
