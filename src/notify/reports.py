"""报告生成模块 — Markdown 日报/仪表盘/精简摘要。

迁自 src/notification.py 的 5 个 generate_*() 方法（~570 行）：
- generate_daily_report (L402)
- generate_dashboard_report (L620)
- generate_wechat_dashboard (L902)
- generate_wechat_summary (L1037)
- generate_single_stock_report (L1101)
- _get_signal_level (L595) — 公共 helper

**架构定位**：纯"内容格式化"，不依赖任何 channel 实现。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from src.analyzer import AnalysisResult


def _get_signal_level(result: AnalysisResult) -> Tuple[str, str, str]:
    """根据操作建议获取信号等级、emoji、颜色标签。

    Returns:
        (信号文字, emoji, 颜色标记)
    """
    advice = result.operation_advice
    score = result.sentiment_score

    if advice in ["强烈买入"] or score >= 80:
        return ("强烈买入", "\U0001f49a", "强买")  # 💚
    if advice in ["买入", "加仓"] or score >= 65:
        return ("买入", "\U0001f7e2", "买入")  # 🟢
    if advice in ["持有"] or 55 <= score < 65:
        return ("持有", "\U0001f7e1", "持有")  # 🟡
    if advice in ["观望"] or 45 <= score < 55:
        return ("观望", "⚪", "观望")  # ⚪
    if advice in ["减仓"] or 35 <= score < 45:
        return ("减仓", "\U0001f7e0", "减仓")  # 🟠
    if advice in ["卖出", "强烈卖出"] or score < 35:
        return ("卖出", "\U0001f534", "卖出")  # 🔴
    return ("观望", "⚪", "观望")  # ⚪


# ---------------------------------------------------------------------------
# generate_daily_report
# ---------------------------------------------------------------------------


def generate_daily_report(
    results: List[AnalysisResult],
    report_date: Optional[str] = None,
) -> str:
    """生成 Markdown 格式日报（详细版，含技术面/基本面/消息面分段）。"""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    report_lines = [
        f"# \U0001f4c5 {report_date} 股票智能分析报告",  # 📅
        "",
        f"> 共分析 **{len(results)}** 只股票 | 报告生成时间：{datetime.now().strftime('%H:%M:%S')}",
        "",
        "---",
        "",
    ]

    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

    # 统计
    buy_count = sum(1 for r in results if r.operation_advice in ["买入", "加仓", "强烈买入"])
    sell_count = sum(1 for r in results if r.operation_advice in ["卖出", "减仓", "强烈卖出"])
    hold_count = sum(1 for r in results if r.operation_advice in ["持有", "观望"])
    avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0

    report_lines.extend([
        "## \U0001f4ca 操作建议汇总",  # 📊
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| \U0001f7e2 建议买入/加仓 | **{buy_count}** 只 |",
        f"| \U0001f7e1 建议持有/观望 | **{hold_count}** 只 |",
        f"| \U0001f534 建议减仓/卖出 | **{sell_count}** 只 |",
        f"| \U0001f4c8 平均看多评分 | **{avg_score:.1f}** 分 |",
        "",
        "---",
        "",
        "## \U0001f4c8 个股详细分析",
        "",
    ])

    for result in sorted_results:
        emoji = result.get_emoji()
        confidence_stars = (
            result.get_confidence_stars() if hasattr(result, "get_confidence_stars") else "⭐⭐"
        )

        report_lines.extend([
            f"### {emoji} {result.name} ({result.code})",
            "",
            f"**操作建议：{result.operation_advice}** | **综合评分：{result.sentiment_score}分** | **趋势预测：{result.trend_prediction}** | **置信度：{confidence_stars}**",
            "",
        ])

        if hasattr(result, "key_points") and result.key_points:
            report_lines.append(f"**\U0001f3af 核心看点**：{result.key_points}")
            report_lines.append("")

        if hasattr(result, "buy_reason") and result.buy_reason:
            report_lines.append(f"**\U0001f4a1 操作理由**：{result.buy_reason}")
            report_lines.append("")

        if hasattr(result, "trend_analysis") and result.trend_analysis:
            report_lines.extend(["#### \U0001f4c9 走势分析", result.trend_analysis, ""])

        outlook_lines = []
        if hasattr(result, "short_term_outlook") and result.short_term_outlook:
            outlook_lines.append(f"- **短期（1-3日）**：{result.short_term_outlook}")
        if hasattr(result, "medium_term_outlook") and result.medium_term_outlook:
            outlook_lines.append(f"- **中期（1-2周）**：{result.medium_term_outlook}")
        if outlook_lines:
            report_lines.extend(["#### \U0001f52e 市场展望", *outlook_lines, ""])

        tech_lines = []
        if result.technical_analysis:
            tech_lines.append(f"**综合**：{result.technical_analysis}")
        if hasattr(result, "ma_analysis") and result.ma_analysis:
            tech_lines.append(f"**均线**：{result.ma_analysis}")
        if hasattr(result, "volume_analysis") and result.volume_analysis:
            tech_lines.append(f"**量能**：{result.volume_analysis}")
        if hasattr(result, "pattern_analysis") and result.pattern_analysis:
            tech_lines.append(f"**形态**：{result.pattern_analysis}")
        if tech_lines:
            report_lines.extend(["#### \U0001f4ca 技术面分析", *tech_lines, ""])

        fund_lines = []
        if hasattr(result, "fundamental_analysis") and result.fundamental_analysis:
            fund_lines.append(result.fundamental_analysis)
        if hasattr(result, "sector_position") and result.sector_position:
            fund_lines.append(f"**板块地位**：{result.sector_position}")
        if hasattr(result, "company_highlights") and result.company_highlights:
            fund_lines.append(f"**公司亮点**：{result.company_highlights}")
        if fund_lines:
            report_lines.extend(["#### \U0001f3e2 基本面分析", *fund_lines, ""])

        news_lines = []
        if result.news_summary:
            news_lines.append(f"**新闻摘要**：{result.news_summary}")
        if hasattr(result, "market_sentiment") and result.market_sentiment:
            news_lines.append(f"**市场情绪**：{result.market_sentiment}")
        if hasattr(result, "hot_topics") and result.hot_topics:
            news_lines.append(f"**相关热点**：{result.hot_topics}")
        if news_lines:
            report_lines.extend(["#### \U0001f4f0 消息面/情绪面", *news_lines, ""])

        if result.analysis_summary:
            report_lines.extend(["#### \U0001f4dd 综合分析", result.analysis_summary, ""])

        if hasattr(result, "risk_warning") and result.risk_warning:
            report_lines.append(f"⚠️ **风险提示**：{result.risk_warning}")
            report_lines.append("")

        if hasattr(result, "search_performed") and result.search_performed:
            report_lines.append("*\U0001f50d 已执行联网搜索*")
        if hasattr(result, "data_sources") and result.data_sources:
            report_lines.append(f"*\U0001f4cb 数据来源：{result.data_sources}*")

        if not result.success and result.error_message:
            report_lines.extend(["", f"❌ **分析异常**：{result.error_message[:100]}"])

        report_lines.extend(["", "---", ""])

    report_lines.extend(["", f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"])
    return "\n".join(report_lines)


# ---------------------------------------------------------------------------
# generate_dashboard_report
# ---------------------------------------------------------------------------


def generate_dashboard_report(
    results: List[AnalysisResult],
    report_date: Optional[str] = None,
) -> str:
    """生成决策仪表盘格式日报（市场概览+核心结论+数据透视+作战计划）。"""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

    buy_count = sum(1 for r in results if r.operation_advice in ["买入", "加仓", "强烈买入"])
    sell_count = sum(1 for r in results if r.operation_advice in ["卖出", "减仓", "强烈卖出"])
    hold_count = sum(1 for r in results if r.operation_advice in ["持有", "观望"])

    report_lines = [
        f"# \U0001f3af {report_date} 决策仪表盘",  # 🎯
        "",
        f"> 共分析 **{len(results)}** 只股票 | \U0001f7e2买入:{buy_count} \U0001f7e1观望:{hold_count} \U0001f534卖出:{sell_count}",
        "",
    ]

    # 分析结果摘要
    if results:
        report_lines.extend(["## \U0001f4ca 分析结果摘要", ""])
        for r in sorted_results:
            emoji = r.get_emoji()
            report_lines.append(
                f"{emoji} **{r.name}({r.code})**: {r.operation_advice} | "
                f"评分 {r.sentiment_score} | {r.trend_prediction}"
            )
        report_lines.extend(["", "---", ""])

    for result in sorted_results:
        signal_text, signal_emoji, signal_tag = _get_signal_level(result)
        dashboard = result.dashboard if hasattr(result, "dashboard") and result.dashboard else {}

        stock_name = (
            result.name
            if result.name and not result.name.startswith("股票")
            else f"股票{result.code}"
        )

        report_lines.append(f"## {signal_emoji} {stock_name} ({result.code})")
        report_lines.append("")

        # 舆情与基本面概览
        intel = dashboard.get("intelligence", {}) if dashboard else {}
        if intel:
            report_lines.extend(["### \U0001f4f0 重要信息速览", ""])
            if intel.get("sentiment_summary"):
                report_lines.append(f"**\U0001f4ad 舆情情绪**: {intel['sentiment_summary']}")
            if intel.get("earnings_outlook"):
                report_lines.append(f"**\U0001f4ca 业绩预期**: {intel['earnings_outlook']}")
            risk_alerts = intel.get("risk_alerts", [])
            if risk_alerts:
                report_lines.append("")
                report_lines.append("**\U0001f6a8 风险警报**:")
                for alert in risk_alerts:
                    report_lines.append(f"- {alert}")
            catalysts = intel.get("positive_catalysts", [])
            if catalysts:
                report_lines.append("")
                report_lines.append("**✨ 利好催化**:")
                for cat in catalysts:
                    report_lines.append(f"- {cat}")
            if intel.get("latest_news"):
                report_lines.append("")
                report_lines.append(f"**\U0001f4e2 最新动态**: {intel['latest_news']}")
            report_lines.append("")

        # 核心结论
        core = dashboard.get("core_conclusion", {}) if dashboard else {}
        one_sentence = core.get("one_sentence", result.analysis_summary)
        time_sense = core.get("time_sensitivity", "本周内")
        pos_advice = core.get("position_advice", {})

        report_lines.extend([
            "### \U0001f4cc 核心结论",
            "",
            f"**{signal_emoji} {signal_text}** | {result.trend_prediction}",
            "",
            f"> **一句话决策**: {one_sentence}",
            "",
            f"⏰ **时效性**: {time_sense}",
            "",
        ])

        if pos_advice:
            report_lines.extend([
                "| 持仓情况 | 操作建议 |",
                "|---------|---------|",
                f"| \U0001f195 **空仓者** | {pos_advice.get('no_position', result.operation_advice)} |",
                f"| \U0001f4bc **持仓者** | {pos_advice.get('has_position', '继续持有')} |",
                "",
            ])

        # 数据透视
        data_persp = dashboard.get("data_perspective", {}) if dashboard else {}
        if data_persp:
            trend_data = data_persp.get("trend_status", {})
            price_data = data_persp.get("price_position", {})
            vol_data = data_persp.get("volume_analysis", {})
            chip_data = data_persp.get("chip_structure", {})

            report_lines.extend(["### \U0001f4ca 数据透视", ""])

            if trend_data:
                is_bullish = "✅ 是" if trend_data.get("is_bullish", False) else "❌ 否"
                report_lines.append(
                    f"**均线排列**: {trend_data.get('ma_alignment', 'N/A')} | 多头排列: {is_bullish} | 趋势强度: {trend_data.get('trend_score', 'N/A')}/100"
                )
                report_lines.append("")

            if price_data:
                bias_status = price_data.get("bias_status", "N/A")
                bias_emoji = "✅" if bias_status == "安全" else ("⚠️" if bias_status == "警戒" else "\U0001f6a8")
                report_lines.extend([
                    "| 价格指标 | 数值 |",
                    "|---------|------|",
                    f"| 当前价 | {price_data.get('current_price', 'N/A')} |",
                    f"| MA5 | {price_data.get('ma5', 'N/A')} |",
                    f"| MA10 | {price_data.get('ma10', 'N/A')} |",
                    f"| MA20 | {price_data.get('ma20', 'N/A')} |",
                    f"| 乖离率(MA5) | {price_data.get('bias_ma5', 'N/A')}% {bias_emoji}{bias_status} |",
                    f"| 支撑位 | {price_data.get('support_level', 'N/A')} |",
                    f"| 压力位 | {price_data.get('resistance_level', 'N/A')} |",
                    "",
                ])

            if vol_data:
                report_lines.append(
                    f"**量能**: 量比 {vol_data.get('volume_ratio', 'N/A')} ({vol_data.get('volume_status', '')}) | 换手率 {vol_data.get('turnover_rate', 'N/A')}%"
                )
                report_lines.append(f"\U0001f4a1 *{vol_data.get('volume_meaning', '')}*")
                report_lines.append("")

            if chip_data:
                chip_health = chip_data.get("chip_health", "N/A")
                chip_emoji = "✅" if chip_health == "健康" else ("⚠️" if chip_health == "一般" else "\U0001f6a8")
                report_lines.append(
                    f"**筹码**: 获利比例 {chip_data.get('profit_ratio', 'N/A')} | 平均成本 {chip_data.get('avg_cost', 'N/A')} | 集中度 {chip_data.get('concentration', 'N/A')} {chip_emoji}{chip_health}"
                )
                report_lines.append("")

        # 作战计划
        battle = dashboard.get("battle_plan", {}) if dashboard else {}
        if battle:
            report_lines.extend(["### \U0001f3af 作战计划", ""])
            sniper = battle.get("sniper_points", {})
            if sniper:
                report_lines.extend([
                    "**\U0001f4cd 狙击点位**",
                    "",
                    "| 点位类型 | 价格 |",
                    "|---------|------|",
                    f"| \U0001f3af 理想买入点 | {sniper.get('ideal_buy', 'N/A')} |",
                    f"| \U0001f535 次优买入点 | {sniper.get('secondary_buy', 'N/A')} |",
                    f"| \U0001f6d1 止损位 | {sniper.get('stop_loss', 'N/A')} |",
                    f"| \U0001f38a 目标位 | {sniper.get('take_profit', 'N/A')} |",
                    "",
                ])
            position = battle.get("position_strategy", {})
            if position:
                report_lines.extend([
                    f"**\U0001f4b0 仓位建议**: {position.get('suggested_position', 'N/A')}",
                    f"- 建仓策略: {position.get('entry_plan', 'N/A')}",
                    f"- 风控策略: {position.get('risk_control', 'N/A')}",
                    "",
                ])
            checklist = battle.get("action_checklist", []) if battle else []
            if checklist:
                report_lines.extend(["✅ **检查清单**", ""])
                for item in checklist:
                    report_lines.append(f"- {item}")
                report_lines.append("")

        # 无 dashboard 降级显示
        if not dashboard:
            if result.buy_reason:
                report_lines.extend([f"**\U0001f4a1 操作理由**: {result.buy_reason}", ""])
            if result.risk_warning:
                report_lines.extend([f"**⚠️ 风险提示**: {result.risk_warning}", ""])
            if result.ma_analysis or result.volume_analysis:
                report_lines.extend(["### \U0001f4ca 技术面", ""])
                if result.ma_analysis:
                    report_lines.append(f"**均线**: {result.ma_analysis}")
                if result.volume_analysis:
                    report_lines.append(f"**量能**: {result.volume_analysis}")
                report_lines.append("")
            if result.news_summary:
                report_lines.extend(["### \U0001f4f0 消息面", result.news_summary, ""])

        report_lines.extend(["---", ""])

    report_lines.extend(["", f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"])
    return "\n".join(report_lines)


# ---------------------------------------------------------------------------
# generate_wechat_dashboard
# ---------------------------------------------------------------------------


def generate_wechat_dashboard(results: List[AnalysisResult]) -> str:
    """企业微信决策仪表盘精简版（控制在 ~4000 字符内）。"""
    report_date = datetime.now().strftime("%Y-%m-%d")
    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

    buy_count = sum(1 for r in results if r.operation_advice in ["买入", "加仓", "强烈买入"])
    sell_count = sum(1 for r in results if r.operation_advice in ["卖出", "减仓", "强烈卖出"])
    hold_count = sum(1 for r in results if r.operation_advice in ["持有", "观望"])

    lines = [
        f"## \U0001f3af {report_date} 决策仪表盘",
        "",
        f"> {len(results)}只股票 | \U0001f7e2买入:{buy_count} \U0001f7e1观望:{hold_count} \U0001f534卖出:{sell_count}",
        "",
    ]

    for result in sorted_results:
        signal_text, signal_emoji, _ = _get_signal_level(result)
        dashboard = result.dashboard if hasattr(result, "dashboard") and result.dashboard else {}
        core = dashboard.get("core_conclusion", {}) if dashboard else {}
        battle = dashboard.get("battle_plan", {}) if dashboard else {}
        intel = dashboard.get("intelligence", {}) if dashboard else {}

        stock_name = (
            result.name
            if result.name and not result.name.startswith("股票")
            else f"股票{result.code}"
        )

        lines.append(f"### {signal_emoji} **{signal_text}** | {stock_name}({result.code})")
        lines.append("")

        one_sentence = core.get("one_sentence", result.analysis_summary) if core else result.analysis_summary
        if one_sentence:
            lines.append(f"\U0001f4cc **{one_sentence[:80]}**")
            lines.append("")

        info_lines = []
        if intel.get("earnings_outlook"):
            info_lines.append(f"\U0001f4ca 业绩: {intel['earnings_outlook'][:60]}")
        if intel.get("sentiment_summary"):
            info_lines.append(f"\U0001f4ad 舆情: {intel['sentiment_summary'][:50]}")
        if info_lines:
            lines.extend(info_lines)
            lines.append("")

        risks = intel.get("risk_alerts", []) if intel else []
        if risks:
            lines.append("\U0001f6a8 **风险**:")
            for risk in risks[:2]:
                risk_text = risk[:50] + "..." if len(risk) > 50 else risk
                lines.append(f"   • {risk_text}")
            lines.append("")

        catalysts = intel.get("positive_catalysts", []) if intel else []
        if catalysts:
            lines.append("✨ **利好**:")
            for cat in catalysts[:2]:
                cat_text = cat[:50] + "..." if len(cat) > 50 else cat
                lines.append(f"   • {cat_text}")
            lines.append("")

        sniper = battle.get("sniper_points", {}) if battle else {}
        if sniper:
            ideal_buy = sniper.get("ideal_buy", "")
            stop_loss = sniper.get("stop_loss", "")
            take_profit = sniper.get("take_profit", "")
            points = []
            if ideal_buy:
                points.append(f"\U0001f3af买点:{ideal_buy[:15]}")
            if stop_loss:
                points.append(f"\U0001f6d1止损:{stop_loss[:15]}")
            if take_profit:
                points.append(f"\U0001f38a目标:{take_profit[:15]}")
            if points:
                lines.append(" | ".join(points))
                lines.append("")

        pos_advice = core.get("position_advice", {}) if core else {}
        if pos_advice:
            no_pos = pos_advice.get("no_position", "")
            has_pos = pos_advice.get("has_position", "")
            if no_pos:
                lines.append(f"\U0001f195 空仓者: {no_pos[:50]}")
            if has_pos:
                lines.append(f"\U0001f4bc 持仓者: {has_pos[:50]}")
            lines.append("")

        checklist = battle.get("action_checklist", []) if battle else []
        if checklist:
            failed = [c for c in checklist if c.startswith("❌") or c.startswith("⚠️")]
            if failed:
                lines.append("**检查未通过项**:")
                for check in failed[:3]:
                    lines.append(f"   {check[:40]}")
                lines.append("")

        lines.extend(["---", ""])

    lines.append(f"*生成时间: {datetime.now().strftime('%H:%M')}*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generate_wechat_summary
# ---------------------------------------------------------------------------


def generate_wechat_summary(results: List[AnalysisResult]) -> str:
    """企业微信精简版日报（控制在 ~4000 字符内）。"""
    report_date = datetime.now().strftime("%Y-%m-%d")
    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)

    buy_count = sum(1 for r in results if r.operation_advice in ["买入", "加仓", "强烈买入"])
    sell_count = sum(1 for r in results if r.operation_advice in ["卖出", "减仓", "强烈卖出"])
    hold_count = sum(1 for r in results if r.operation_advice in ["持有", "观望"])
    avg_score = sum(r.sentiment_score for r in results) / len(results) if results else 0

    lines = [
        f"## \U0001f4c5 {report_date} 股票分析报告",
        "",
        f"> 共 **{len(results)}** 只 | \U0001f7e2买入:{buy_count} \U0001f7e1持有:{hold_count} \U0001f534卖出:{sell_count} | 均分:{avg_score:.0f}",
        "",
    ]

    for result in sorted_results:
        emoji = result.get_emoji()
        lines.append(f"### {emoji} {result.name}({result.code})")
        lines.append(f"**{result.operation_advice}** | 评分:{result.sentiment_score} | {result.trend_prediction}")

        if hasattr(result, "buy_reason") and result.buy_reason:
            reason = result.buy_reason[:80] + "..." if len(result.buy_reason) > 80 else result.buy_reason
            lines.append(f"\U0001f4a1 {reason}")

        if hasattr(result, "key_points") and result.key_points:
            points = result.key_points[:60] + "..." if len(result.key_points) > 60 else result.key_points
            lines.append(f"\U0001f3af {points}")

        if hasattr(result, "risk_warning") and result.risk_warning:
            risk = result.risk_warning[:50] + "..." if len(result.risk_warning) > 50 else result.risk_warning
            lines.append(f"⚠️ {risk}")

        lines.append("")

    lines.extend([
        "---",
        "*AI生成，仅供参考，不构成投资建议*",
        f"*详细报告见 reports/report_{report_date.replace('-', '')}.md*",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generate_single_stock_report
# ---------------------------------------------------------------------------


def generate_single_stock_report(result: AnalysisResult) -> str:
    """单只股票报告（单股推送模式）。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    signal_text, signal_emoji, _ = _get_signal_level(result)
    dashboard = result.dashboard if hasattr(result, "dashboard") and result.dashboard else {}
    core = dashboard.get("core_conclusion", {}) if dashboard else {}
    battle = dashboard.get("battle_plan", {}) if dashboard else {}
    intel = dashboard.get("intelligence", {}) if dashboard else {}

    stock_name = (
        result.name
        if result.name and not result.name.startswith("股票")
        else f"股票{result.code}"
    )

    lines = [
        f"## {signal_emoji} {stock_name} ({result.code})",
        "",
        f"> {ts} | 评分: **{result.sentiment_score}** | {result.trend_prediction}",
        "",
    ]

    one_sentence = core.get("one_sentence", result.analysis_summary) if core else result.analysis_summary
    if one_sentence:
        lines.extend(["### \U0001f4cc 核心结论", "", f"**{signal_text}**: {one_sentence}", ""])

    info_added = False
    if intel:
        if intel.get("earnings_outlook"):
            if not info_added:
                lines.extend(["### \U0001f4f0 重要信息", ""])
                info_added = True
            lines.append(f"\U0001f4ca **业绩预期**: {intel['earnings_outlook'][:100]}")
        if intel.get("sentiment_summary"):
            if not info_added:
                lines.extend(["### \U0001f4f0 重要信息", ""])
                info_added = True
            lines.append(f"\U0001f4ad **舆情情绪**: {intel['sentiment_summary'][:80]}")
        risks = intel.get("risk_alerts", [])
        if risks:
            if not info_added:
                lines.extend(["### \U0001f4f0 重要信息", ""])
                info_added = True
            lines.append("\U0001f6a8 **风险警报**:")
            for risk in risks[:3]:
                lines.append(f"- {risk[:80]}")
        if info_added:
            lines.append("")

    pos_advice = core.get("position_advice", {}) if core else {}
    if pos_advice:
        lines.extend(["### \U0001f4b0 持仓建议", ""])
        if pos_advice.get("no_position"):
            lines.append(f"- 空仓者：{pos_advice['no_position'][:80]}")
        if pos_advice.get("has_position"):
            lines.append(f"- 持仓者：{pos_advice['has_position'][:80]}")
        lines.append("")

    sniper = battle.get("sniper_points", {}) if battle else {}
    if sniper:
        pts = []
        if sniper.get("ideal_buy"):
            pts.append(f"🎯买点:{sniper['ideal_buy'][:15]}")
        if sniper.get("stop_loss"):
            pts.append(f"🛑止损:{sniper['stop_loss'][:15]}")
        if sniper.get("take_profit"):
            pts.append(f"🎊目标:{sniper['take_profit'][:15]}")
        if pts:
            lines.extend(["### 📍 狙击点位", "", " | ".join(pts), ""])

    lines.extend(["---", ""])
    return "\n".join(lines)
