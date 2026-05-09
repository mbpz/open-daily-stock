"""通知格式化器"""
from typing import List
from datetime import datetime


class BaseFormatter:
    """格式化器基类"""

    def format_single_result(self, result) -> str:
        """格式化单个分析结果"""
        raise NotImplementedError

    def format_multiple_results(self, results: List) -> str:
        """格式化多个分析结果"""
        raise NotImplementedError

    def format_summary(self, results: List, buy_count: int, hold_count: int, sell_count: int) -> str:
        """格式化汇总信息"""
        raise NotImplementedError


class MarkdownFormatter(BaseFormatter):
    """Markdown 格式报告"""

    def format_single_result(self, result) -> str:
        emoji = result.get_emoji()
        lines = [
            f"## {emoji} {result.name}({result.code})",
            f"**评分**: {result.sentiment_score}/100",
            f"**趋势**: {result.trend_prediction}",
            f"**建议**: {result.operation_advice}",
            f"**置信度**: {result.get_confidence_stars()}",
            "",
            f"{result.analysis_summary[:200]}",
            "",
            "---",
        ]
        return "\n".join(lines)

    def format_multiple_results(self, results: List) -> str:
        lines = ["# 📊 股票分析报告", ""]
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            lines.append(self.format_single_result(r))
        return "\n".join(lines)

    def format_summary(self, results: List, buy_count: int, hold_count: int, sell_count: int) -> str:
        return f"**汇总**: 买入 {buy_count} | 持有 {hold_count} | 卖出 {sell_count}"


class SimpleFormatter(BaseFormatter):
    """精简格式（企业微信等字符限制场景）"""

    MAX_LENGTH = 4000

    def format_single_result(self, result) -> str:
        emoji = result.get_emoji()
        return (
            f"{emoji} {result.name}({result.code}) "
            f"{result.operation_advice} {result.sentiment_score}分"
        )

    def format_multiple_results(self, results: List) -> str:
        lines = [f"📊 {datetime.now().strftime('%Y-%m-%d')} 分析报告", ""]
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            lines.append(self.format_single_result(r))
        return "\n".join(lines)[:self.MAX_LENGTH]

    def format_summary(self, results: List, buy_count: int, hold_count: int, sell_count: int) -> str:
        return f"汇总: 🟢{buy_count} 🟡{hold_count} 🔴{sell_count}"


class DashboardFormatter(BaseFormatter):
    """决策仪表盘格式"""

    def format_single_result(self, result) -> str:
        lines = [
            f"## 📊 {result.name}({result.code})",
            f"**操作**: {result.operation_advice} {result.get_emoji()}",
            f"**评分**: {result.sentiment_score}/100 ({result.confidence_level}置信度)",
            "",
        ]

        if result.dashboard:
            core = result.dashboard.get("core_conclusion", {})
            if core:
                lines.append(f"**结论**: {core.get('one_sentence', '')}")

            battle = result.dashboard.get("battle_plan", {})
            sniper = battle.get("sniper_points", {})
            if sniper:
                lines.append("")
                if sniper.get("ideal_buy"):
                    lines.append(f"  🎯 买点: {sniper['ideal_buy']}")
                if sniper.get("stop_loss"):
                    lines.append(f"  🛑 止损: {sniper['stop_loss']}")
                if sniper.get("take_profit"):
                    lines.append(f"  🎊 目标: {sniper['take_profit']}")

        lines.append("")
        lines.append(f"_{result.analysis_summary[:100]}_")
        return "\n".join(lines)

    def format_multiple_results(self, results: List) -> str:
        lines = ["# 🚀 决策仪表盘", ""]
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            lines.append(self.format_single_result(r))
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def format_summary(self, results: List, buy_count: int, hold_count: int, sell_count: int) -> str:
        avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0
        return (
            f"📈 今日扫描 {len(results)} 只股票 | "
            f"🟢买入 {buy_count} | 🟡持有 {hold_count} | 🔴卖出 {sell_count} | "
            f"平均评分 {avg_score:.0f}"
        )