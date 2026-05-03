"""分析页面"""
import flet as ft
import asyncio
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR, ACCENT_COLOR
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
                ft.Container(height=20),
                self._result_area,
            ]),
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
        lines = [
            f"{_('股票代码: ')}{result.code}",
            f"{_('股票名称: ')}{result.name}",
            f"",
            f"{_('综合评分:')}{result.sentiment_score}/100",
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
        return "\n".join(lines)

    def _show_result(self, message: str, is_error: bool = False):
        """显示结果"""
        color = ERROR_COLOR if is_error else SUCCESS_COLOR
        self._result_area.content = ft.Text(message, color=color)
        self._result_area.update()