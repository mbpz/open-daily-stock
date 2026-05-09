"""分析页面"""
import flet as ft
import asyncio
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR, WARNING_COLOR, ACCENT_COLOR
from src.i18n import _


class AnalyzePage(ft.Container):
    """股票分析页面"""

    def __init__(self, app, pipeline=None):
        super().__init__()
        self.app = app
        self._pipeline = pipeline
        self._progress_ring = None
        self._status_text = None

        header = ft.Text(_("股票分析"), size=24, weight=ft.FontWeight.BOLD)

        self._stock_input = ft.TextField(
            hint_text="如: 600519",
            width=200,
        )

        self._progress_ring = ft.ProgressRing(width=30, height=30, visible=False)
        self._status_text = ft.Text("", color="#a0a0a0", visible=False)

        input_row = ft.Row([
            ft.Text(_("股票代码:"), width=100),
            self._stock_input,
            ft.Container(width=20),
            ft.Button(
                "开始分析",
                icon=ft.Icons.PLAY_ARROW,
                on_click=self._start_analysis,
                bgcolor=ACCENT_COLOR,
                color=ft.Colors.WHITE,
            ),
            self._progress_ring,
            self._status_text,
        ])

        # Verdict badge and sentiment bar area
        self._verdict_badge = ft.Container(
            content=ft.Text("", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            padding=15,
            border_radius=30,
        )

        self._sentiment_bar = ft.Container(
            content=ft.Row([
                ft.Container(width=5, bgcolor=ERROR_COLOR),
                ft.Container(expand=True, bgcolor="#333333"),
            ]),
            height=20,
            border_radius=10,
        )

        self._sentiment_container = ft.Column([
            ft.Text(_("AI 情绪评分"), size=12, color="#a0a0a0"),
            self._sentiment_bar,
            ft.Text("0", size=10, color="#a0a0a0"),
        ], visible=False)

        self._catalysts_section = ft.Container(
            content=ft.Column([], spacing=5),
            padding=10,
            bgcolor="#1a3a2a",
            border_radius=10,
            visible=False,
        )

        self._risks_section = ft.Container(
            content=ft.Column([], spacing=5),
            padding=10,
            bgcolor="#3a1a1a",
            border_radius=10,
            visible=False,
        )

        self._result_area = ft.Container(
            content=ft.Text(_("分析结果将显示在这里"), color="#a0a0a0"),
            padding=20,
            bgcolor=CARD_BG,
            border_radius=10,
            visible=True,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                input_row,
                ft.Container(height=10),
                ft.Row([
                    self._verdict_badge,
                    ft.Container(width=20),
                    ft.Column([
                        ft.Text(_("AI 情绪评分"), size=12, color="#a0a0a0"),
                        self._sentiment_bar,
                    ], expand=True),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Container(height=10),
                self._sentiment_container,
                ft.Container(height=10),
                self._catalysts_section,
                ft.Container(height=5),
                self._risks_section,
                self._result_area,
            ], scroll=ft.ScrollMode.AUTO),
            padding=10,
        )

    def _start_analysis(self, e):
        """开始分析"""
        code = self._stock_input.value.strip()
        if not code:
            self._show_result(_("请输入股票代码"), is_error=True)
            return

        if self._pipeline is None:
            self._show_result(_("分析服务未初始化"), is_error=True)
            return

        # Show progress indicators
        self._progress_ring.visible = True
        self._status_text.value = f"{_('正在分析 ')}{code}..."
        self._status_text.visible = True
        self._progress_ring.update()
        self._status_text.update()

        self._result_area.content = ft.Text(f"{_('正在分析 ')}{code}...", color="#a0a0a0")
        self._result_area.update()

        # Run analysis in background task
        self.app.page.run_task(self._run_analysis_async, code)

    def _update_progress(self, stage: str, percent: int, message: str):
        """Update progress callback"""
        self._status_text.value = message
        self._status_text.update()

    async def _run_analysis_async(self, code: str):
        """Run analysis asynchronously"""
        try:
            # Run synchronous pipeline in thread pool to avoid blocking
            results = await asyncio.to_thread(self._pipeline.run, [code], progress_callback=self._update_progress)
            if results and len(results) > 0:
                result = results[0]
                self._show_result(self._format_result(result))
            else:
                self._show_result(f"{_('未能获取 的分析结果')}{code}", is_error=True)
        except Exception as ex:
            self._show_result(f"{_('分析失败: ')}{str(ex)}", is_error=True)
        finally:
            self._progress_ring.visible = False
            self._status_text.visible = False
            self._progress_ring.update()
            self._status_text.update()

    def _format_result(self, result) -> str:
        """Format analysis result for display"""
        # Determine verdict
        score = result.sentiment_score or 50
        if score >= 60:
            verdict = _("看涨")
            verdict_color = SUCCESS_COLOR
        elif score >= 40:
            verdict = _("中性")
            verdict_color = WARNING_COLOR
        else:
            verdict = _("看跌")
            verdict_color = ERROR_COLOR

        # Update verdict badge
        self._verdict_badge.content = ft.Text(verdict, size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self._verdict_badge.bgcolor = verdict_color
        self._verdict_badge.update()

        # Update sentiment bar
        bar_width = min(score, 100)
        bar_color = SUCCESS_COLOR if score >= 60 else WARNING_COLOR if score >= 40 else ERROR_COLOR
        self._sentiment_bar.content = ft.Row([
            ft.Container(width=bar_width, bgcolor=bar_color),
            ft.Container(expand=True, bgcolor="#333333"),
        ])
        self._sentiment_container.visible = True
        self._sentiment_container.update()

        # Update catalysts and risks
        catalysts = []
        risks = []

        if hasattr(result, 'bullish_catalysts') and result.bullish_catalysts:
            catalysts = result.bullish_catalysts
        if hasattr(result, 'risk_factors') and result.risk_factors:
            risks = result.risk_factors

        # Build catalysts section
        self._catalysts_section.content = ft.Column([
            ft.Text(f"📈 {_('看涨因素')}", size=14, weight=ft.FontWeight.BOLD, color=SUCCESS_COLOR),
            *[ft.Text(f"• {c}", size=12, color="#a0a0a0") for c in catalysts[:5]],
        ] if catalysts else [ft.Text(f"📈 {_('看涨因素')}: {_('暂无')}", size=12, color="#666666")])
        self._catalysts_section.visible = True

        # Build risks section
        self._risks_section.content = ft.Column([
            ft.Text(f"📉 {_('风险因素')}", size=14, weight=ft.FontWeight.BOLD, color=ERROR_COLOR),
            *[ft.Text(f"• {r}", size=12, color="#a0a0a0") for r in risks[:5]],
        ] if risks else [ft.Text(f"📉 {_('风险因素')}: {_('暂无')}", size=12, color="#666666")])
        self._risks_section.visible = True

        self._catalysts_section.update()
        self._risks_section.update()

        # Original text content
        lines = [
            f"{_('股票代码: ')}{result.code}",
            f"{_('股票名称: ')}{result.name}",
            f"",
            f"{_('综合评分:')}{score}/100",
            f"{_('趋势预测:')}{result.trend_prediction}",
            f"{_('操作建议:')}{result.operation_advice}",
            f"{_('置信度:')}{result.confidence_level}",
        ]
        if result.trend_analysis:
            lines.append(f"")
            lines.append(f"{_('走势分析:')}{result.trend_analysis}")
        if result.short_term_outlook:
            lines.append(f"{_('短期展望:')}{result.short_term_outlook}")
        if result.technical_analysis:
            lines.append(f"{_('技术分析:')}{result.technical_analysis}")

        # Hide plain text result area since we have structured display
        self._result_area.visible = False

        return "\n".join(lines)

    def _show_result(self, message: str, is_error: bool = False):
        """显示结果"""
        # Show plain text for errors
        self._result_area.visible = True
        color = ERROR_COLOR if is_error else SUCCESS_COLOR
        self._result_area.content = ft.Text(message, color=color)
        self._result_area.update()