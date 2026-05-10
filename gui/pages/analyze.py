"""分析页面"""
import json
import flet as ft
import asyncio
from gui.theme import CARD_BG, CARD_BORDER, SUCCESS_COLOR, ERROR_COLOR, WARNING_COLOR, ACCENT_COLOR
from src.i18n import _
from src.config import get_config


class AnalyzePage(ft.Container):
    """股票分析页面"""

    def __init__(self, app, pipeline=None):
        super().__init__()
        self.app = app
        self._pipeline = pipeline
        self._progress_ring = None
        self._status_text = None
        self._streaming = False
        self._stream_buffer = ""

        header = ft.Text(_("股票分析"), size=24, weight=ft.FontWeight.BOLD)

        self._stock_input = ft.TextField(
            hint_text="如: 600519",
            width=200,
        )

        self._progress_ring = ft.ProgressRing(width=30, height=30, visible=False)
        self._status_text = ft.Text("", color="#a0a0a0", visible=False)

        # Streaming progress bar (separate from progress ring)
        self._stream_bar = ft.ProgressBar(width=200, visible=False)

        # Demo mode indicator badge (must be created before _build_demo_banner)
        self._demo_badge = ft.Container(
            content=ft.Text(
                _("演示模式") + " - " + _("使用示例数据"),
                size=12, color=WARNING_COLOR,
            ),
            padding=ft.padding.only(left=10, right=10, top=3, bottom=3),
            bgcolor="#3a3a1a",
            border_radius=10,
            visible=False,
        )

        # Demo banner: shown when no API key is configured
        self._demo_banner = self._build_demo_banner()

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
            ft.Container(width=8),
            ft.Button(
                "深度分析",
                icon=ft.Icons.SCIENCE,
                on_click=self._start_deep_analysis,
                bgcolor="#6a0dad",
                color=ft.Colors.WHITE,
                tooltip="多 Agent 协同分析（技术面+基本面+消息面）",
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
                self._demo_banner,
                self._demo_badge,
                ft.Container(height=5),
                input_row,
                ft.Container(height=5),
                self._stream_bar,
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

    # ================================================================
    # Demo mode methods (P5-4)
    # ================================================================

    def _build_demo_banner(self) -> ft.Container:
        """Build demo banner: 'Try Demo' button or 'Demo Mode' status."""
        config = get_config()

        if config.is_demo_mode():
            # Already in demo mode: show status notice
            self._demo_badge.visible = True
            return ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, color=WARNING_COLOR, size=16),
                    ft.Text(
                        _("演示模式") + " - " + _("AI 分析使用预计算结果，配置 API Key 后解锁实时分析"),
                        size=12, color=WARNING_COLOR,
                    ),
                ]),
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                bgcolor="#3a3a1a",
                border_radius=8,
            )

        if not config.has_api_key():
            # No API key: show "Try Demo" button
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=WARNING_COLOR, size=20),
                        ft.Text(
                            _("未配置 AI API Key，分析功能需要 API Key"),
                            size=13, color="#a0a0a0",
                        ),
                    ], spacing=8),
                    ft.Container(height=8),
                    ft.ElevatedButton(
                        content=ft.Text(_("快速体验（无需 API Key）")),
                        icon=ft.Icons.PLAY_ARROW,
                        on_click=self._start_demo,
                        bgcolor=WARNING_COLOR,
                        color=ft.Colors.BLACK,
                    ),
                ]),
                padding=15,
                bgcolor=CARD_BG,
                border=ft.border.all(1, WARNING_COLOR),
                border_radius=10,
            )

        # Has API key: no banner needed
        return ft.Container(visible=False)

    def _start_demo(self, e):
        """启动演示模式 - 进入演示模式并显示示例分析结果"""
        config = get_config()
        if not config.is_demo_mode():
            config.set_demo_mode(enabled=True)
            # Reload markets page with demo stocks
            if hasattr(self.app, '_refresh_markets'):
                self.app._refresh_markets()

        # Show demo badge
        self._demo_badge.visible = True
        self._demo_badge.update()

        # Hide the demo banner
        self._demo_banner.visible = False
        self._demo_banner.update()

        # Show demo analysis for 600519 (贵州茅台)
        self._stock_input.value = "600519"
        self._stock_input.update()

        # Load demo analysis data directly
        from src.demo_data import DEMO_AI_ANALYSES
        demo = DEMO_AI_ANALYSES.get("600519")
        if demo:
            self._format_demo_result(demo)

    def _format_demo_result(self, result: dict):
        """Display a pre-computed demo analysis result."""
        self._streaming = False
        self._stream_buffer = ""
        self._progress_ring.visible = False
        self._status_text.visible = False
        self._stream_bar.visible = False
        self._progress_ring.update()
        self._status_text.update()
        self._stream_bar.update()

        score = result.get("sentiment_score", 50)
        if score >= 70:
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
            ft.Container(width=max(bar_width, 1), bgcolor=bar_color),
            ft.Container(expand=True, bgcolor="#333333"),
        ])
        self._sentiment_container.visible = True
        self._sentiment_container.update()

        # Catalysts and risks (demo data may not have these)
        self._catalysts_section.content = ft.Column([
            ft.Text(f"  看涨因素", size=14, weight=ft.FontWeight.BOLD, color=SUCCESS_COLOR),
            ft.Text(f"  {result.get('analysis_summary', _('暂无'))}", size=12, color="#a0a0a0"),
        ])
        self._catalysts_section.visible = True

        self._risks_section.content = ft.Column([
            ft.Text(f"  风险因素", size=14, weight=ft.FontWeight.BOLD, color=ERROR_COLOR),
            ft.Text(f"  {result.get('risk_alert', _('暂无'))}", size=12, color="#a0a0a0"),
        ])
        self._risks_section.visible = True

        self._catalysts_section.update()
        self._risks_section.update()

        # Plain text result for reading convenience
        lines = [
            f"{_('股票代码')}: {result.get('code', '---')}",
            f"{_('股票名称')}: {result.get('name', '---')}",
            f"",
            f"{_('综合评分')}: {score}/100",
            f"{_('趋势预测')}: {result.get('trend_prediction', '---')}",
            f"{_('操作建议')}: {result.get('operation_advice', '---')}",
            f"{_('置信度')}: {result.get('confidence', '---')}",
            f"",
            f"{_('支撑位')}: {result.get('support_level', '---')}",
            f"{_('阻力位')}: {result.get('resistance_level', '---')}",
            f"",
            f"{_('分析摘要')}: {result.get('analysis_summary', '---')}",
            f"",
            f"  {_('模型')}: {result.get('model_used', _('演示数据'))}",
        ]

        self._result_area.visible = True
        self._result_area.content = ft.Text(
            "\n".join(lines),
            color="#e8e8e8",
            size=13,
        )
        self._result_area.update()

    # ================================================================
    # Streaming display methods (P5-1)
    # ================================================================

    def start_stream(self):
        """Begin a streaming analysis display.

        Shows a progress bar and initializes the result area for progressive updates.
        """
        self._streaming = True
        self._stream_buffer = ""

        self._progress_ring.visible = True
        self._status_text.value = _("流式分析中...")
        self._status_text.visible = True

        # Show stream progress bar
        self._stream_bar.visible = True
        self._stream_bar.value = None  # Indeterminate mode

        # Clear structured display
        self._verdict_badge.content = ft.Text("", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self._verdict_badge.bgcolor = "#333333"
        self._sentiment_container.visible = False
        self._catalysts_section.visible = False
        self._risks_section.visible = False

        # Initialize result area
        self._result_area.visible = True
        self._result_area.content = ft.Text(
            _("分析中") + " ...\n",
            color="#a0a0a0",
            size=13,
        )

        self._progress_ring.update()
        self._status_text.update()
        self._stream_bar.update()
        self._result_area.update()

    def append_stream_chunk(self, chunk: str):
        """Append a chunk of streaming text to the result area.

        Args:
            chunk: Partial text from the LLM streaming response
        """
        if not self._streaming:
            self.start_stream()

        self._stream_buffer += chunk

        # Show last ~2000 chars of buffer
        display = self._stream_buffer[-2000:]
        if len(self._stream_buffer) > 2000:
            display = "...[earlier]" + display[-1900:]

        # Animated dots based on buffer length
        dot_phase = (len(self._stream_buffer) // 20) % 4
        dots = "." * (dot_phase + 1)

        self._result_area.content = ft.Text(
            display + f"\n\n{_('分析中')}{dots}",
            color="#e8e8e8",
            size=13,
        )
        self._result_area.update()

    def finish_stream(self, result):
        """Complete the streaming display with the final structured result.

        Args:
            result: AnalysisResult object from the analyzer
        """
        self._streaming = False
        self._stream_buffer = ""

        self._progress_ring.visible = False
        self._status_text.visible = False
        self._stream_bar.visible = False

        self._progress_ring.update()
        self._status_text.update()
        self._stream_bar.update()

        # Format and display the result
        self._format_result(result)

    def _start_analysis(self, e):
        """开始分析"""
        code = self._stock_input.value.strip()
        if not code:
            self._show_result(_("请输入股票代码"), is_error=True)
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

    def _start_deep_analysis(self, e):
        """Start deep multi-agent analysis (P5-5)."""
        code = self._stock_input.value.strip()
        if not code:
            self._show_result(_("请输入股票代码"), is_error=True)
            return

        # Show progress with agent status placeholders
        self._progress_ring.visible = True
        self._status_text.value = f"深度分析 {code}: 技术面分析中..."
        self._status_text.visible = True
        self._progress_ring.update()
        self._status_text.update()

        self._result_area.content = ft.Text(
            f"深度分析 {code}\n\n"
            f"  [1/4] 技术面分析中...\n"
            f"  [2/4] 基本面分析中...\n"
            f"  [3/4] 消息面分析中...\n"
            f"  [4/4] 综合分析中...",
            color="#a0a0a0",
        )
        self._result_area.update()

        self.app.page.run_task(self._run_deep_analysis_async, code)

    async def _run_deep_analysis_async(self, code: str):
        """Run deep analysis via WebSocket in background."""
        import logging
        _log = logging.getLogger(__name__)

        try:
            from src.ws_client import WsClient
            ws = WsClient()
            await ws.connect()

            await ws._ws.send(json.dumps({"action": "deep_analyze", "code": code}))

            resp = await ws._ws.recv()
            resp_data = json.loads(resp)

            await ws.close()

            if resp_data.get("status") == "ok":
                result = resp_data.get("result")
                if result:
                    self._update_progress_agent("deep_analyze", "综合分析完成")
                    self._format_deep_result(result)
                    return
                else:
                    task_id = resp_data.get("task_id")
                    self._status_text.value = f"深度分析任务已创建: {task_id[:16]}..."
                    self._status_text.update()

                    # Poll for result
                    import asyncio
                    for _ in range(30):  # Max 30 seconds
                        await asyncio.sleep(1)
                        await ws.connect()
                        await ws._ws.send(json.dumps({"action": "get_task", "task_id": task_id}))
                        task_resp = await ws._ws.recv()
                        task_data = json.loads(task_resp)
                        await ws.close()

                        if task_data.get("status") == "ok":
                            t = task_data.get("data", {})
                            if t.get("status") == "completed":
                                self._format_deep_result(t.get("result", {}))
                                return
                            elif t.get("status") == "failed":
                                self._show_result(f"深度分析失败: {t.get('error', '未知错误')}", is_error=True)
                                return
                        await asyncio.sleep(0.5)

                    self._show_result("深度分析超时", is_error=True)
                    return
            else:
                self._show_result(f"深度分析请求失败: {resp_data.get('message', '未知错误')}", is_error=True)
                return

        except Exception as ex:
            _log.info(f"GUI deep analysis WS unavailable ({ex}), trying pipeline")

        # Fallback: blocking pipeline
        if self._pipeline is None:
            self._show_result(_("分析服务未初始化"), is_error=True)
            self._progress_ring.visible = False
            self._status_text.visible = False
            self._progress_ring.update()
            self._status_text.update()
            return

        try:
            import asyncio
            self._update_progress_agent("deep_analyze", "深度分析执行中...")
            results = await asyncio.to_thread(
                self._pipeline.run_deep_analyze, code
            )
            if results:
                self._format_deep_result(results)
            else:
                self._show_result(f"深度分析失败: {code}", is_error=True)
        except Exception as ex:
            self._show_result(f"深度分析失败: {str(ex)}", is_error=True)
        finally:
            self._progress_ring.visible = False
            self._status_text.visible = False
            self._progress_ring.update()
            self._status_text.update()

    def _update_progress_agent(self, agent: str, message: str):
        """Update progress with agent-specific status."""
        self._status_text.value = message
        self._status_text.update()

    def _format_deep_result(self, result: dict):
        """Display deep analysis result with specialist breakdowns."""
        self._streaming = False
        self._stream_buffer = ""
        self._progress_ring.visible = False
        self._status_text.visible = False
        self._stream_bar.visible = False
        self._progress_ring.update()
        self._status_text.update()
        self._stream_bar.update()

        score = result.get("composite_score", result.get("sentiment_score", 50))
        if score >= 70:
            verdict = result.get("final_verdict", _("看涨"))
            verdict_color = SUCCESS_COLOR
        elif score >= 40:
            verdict = result.get("final_verdict", _("中性"))
            verdict_color = WARNING_COLOR
        else:
            verdict = result.get("final_verdict", _("看跌"))
            verdict_color = ERROR_COLOR

        # Verdict badge
        self._verdict_badge.content = ft.Text(verdict, size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self._verdict_badge.bgcolor = verdict_color
        self._verdict_badge.update()

        # Sentiment bar
        bar_width = min(score, 100)
        bar_color = SUCCESS_COLOR if score >= 60 else WARNING_COLOR if score >= 40 else ERROR_COLOR
        self._sentiment_bar.content = ft.Row([
            ft.Container(width=max(bar_width, 1), bgcolor=bar_color),
            ft.Container(expand=True, bgcolor="#333333"),
        ])
        self._sentiment_container.visible = True
        self._sentiment_container.update()

        # Catalysts and risks
        catalysts = result.get("key_catalysts", [])
        risk_factors = result.get("risk_factors", [])

        self._catalysts_section.content = ft.Column([
            ft.Text(f"  {_('核心利好')}", size=14, weight=ft.FontWeight.BOLD, color=SUCCESS_COLOR),
            *[ft.Text(f"  {c}", size=12, color="#a0a0a0") for c in (catalysts or [_('暂无')])],
        ])
        self._catalysts_section.visible = True

        self._risks_section.content = ft.Column([
            ft.Text(f"  {_('风险因素')}", size=14, weight=ft.FontWeight.BOLD, color=ERROR_COLOR),
            *[ft.Text(f"  {r}", size=12, color="#a0a0a0") for r in (risk_factors or [_('暂无')])],
        ])
        self._risks_section.visible = True
        self._catalysts_section.update()
        self._risks_section.update()

        # Build result text with specialist scores
        tech = result.get("technical", {}) or {}
        fund = result.get("fundamental", {}) or {}
        news = result.get("news", {}) or {}

        lines = [
            f"{_('股票代码')}: {result.get('code', '---')}",
            f"{_('股票名称')}: {result.get('name', '---')}",
            f"",
            f"{'='*30}",
            f"  {_('深度分析综合评分')}: {score}/100",
            f"  {_('最终研判')}: {verdict}",
            f"  {_('趋势预测')}: {result.get('trend_prediction', '---')}",
            f"  {_('操作建议')}: {result.get('operation_advice', '---')}",
            f"",
            f"{'='*30}",
            f"  {_('技术面评分')}: {tech.get('score', 'N/A')}",
            f"  {_('基本面评分')}: {fund.get('score', 'N/A')}",
            f"  {_('消息面评分')}: {news.get('score', 'N/A')}",
        ]

        if tech.get("trend"):
            lines.append(f"  {_('技术趋势')}: {tech.get('trend')}")
        if tech.get("key_signals"):
            lines.append(f"  {_('技术信号')}: {', '.join(tech.get('key_signals', []))}")
        if fund.get("valuation"):
            lines.append(f"  {_('估值水平')}: {fund.get('valuation')}")
        if fund.get("key_metrics"):
            lines.append(f"  {_('核心指标')}: {', '.join(fund.get('key_metrics', []))}")
        if news.get("sentiment"):
            lines.append(f"  {_('舆情情绪')}: {news.get('sentiment')}")
        if news.get("key_drivers"):
            lines.append(f"  {_('主要驱动')}: {', '.join(news.get('key_drivers', []))}")
        if result.get("synthesis_text"):
            lines.append(f"")
            lines.append(f"{'='*30}")
            lines.append(f"  {_('综合研判')}: {result['synthesis_text'][:300]}")

        self._result_area.visible = True
        self._result_area.content = ft.Text("\n".join(lines), color="#e8e8e8", size=13)
        self._result_area.update()

    async def _run_deep_analysis_pipeline(self, code: str):
        """Run deep analysis through the pipeline (fallback for when WS is not available)."""
        import asyncio
        # Use the pipeline's run method, but wrap in deep_analyze mode
        from src.ws_client import WsClient
        ws = WsClient()
        try:
            await ws.connect()
            await ws._ws.send(json.dumps({"action": "deep_analyze", "code": code}))
            resp = await ws._ws.recv()
            resp_data = json.loads(resp)
            await ws.close()

            if resp_data.get("result"):
                self._format_deep_result(resp_data["result"])
            else:
                self._show_result(_("深度分析未能立即返回结果"), is_error=True)
        except Exception as e:
            self._show_result(f"深度分析失败: {str(e)}", is_error=True)
        finally:
            self._progress_ring.visible = False
            self._status_text.visible = False
            self._progress_ring.update()
            self._status_text.update()

    def _update_progress(self, stage: str, percent: int, message: str):
        """Update progress callback"""
        self._status_text.value = message
        self._status_text.update()

    async def _run_analysis_async(self, code: str):
        """Run analysis with streaming when WebSocket is available.

        P5-1: Tries streaming via WsClient -> DataService WebSocket first.
        Falls back to the blocking pipeline (stdio) if WebSocket is unavailable.
        """
        import logging
        _log = logging.getLogger(__name__)

        # === Primary path: WebSocket streaming (P5-1) ===
        try:
            from src.ws_client import WsClient
            ws = WsClient()
            await ws.connect()
            _log.info(f"GUI streaming analysis via WebSocket for {code}")

            self.start_stream()

            async for event in ws.analyze_stream(code):
                etype = event.get("type")
                if etype == "stream_chunk":
                    self.append_stream_chunk(event.get("chunk", ""))
                elif etype == "stream_done":
                    result_data = event.get("result", {})
                    from src.analyzer import AnalysisResult
                    result = AnalysisResult(**result_data) if result_data else None
                    if result:
                        self.finish_stream(result)
                    await ws.close()
                    return
                elif etype == "stream_error":
                    _log.warning(f"GUI stream error for {code}: {event.get('message')}")
                    break

            await ws.close()
        except Exception as e:
            _log.info(f"GUI WebSocket streaming unavailable ({e}), falling back to pipeline")

        # === Fallback: blocking pipeline via stdio ===
        if self._pipeline is None:
            self._show_result(_("分析服务未初始化"), is_error=True)
            self._progress_ring.visible = False
            self._status_text.visible = False
            self._progress_ring.update()
            self._status_text.update()
            return

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
        # Determine verdict based on sentiment_score
        # 看涨: >=70, 中性: 40-69, 看跌: <40
        score = result.sentiment_score or 50
        if score >= 70:
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

        # Also check dashboard for catalysts/risks
        if result.dashboard:
            if not catalysts:
                catalysts = result.dashboard.get("intelligence", {}).get("positive_catalysts", [])
            if not risks:
                risks = result.dashboard.get("intelligence", {}).get("risk_alerts", [])

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
        self._streaming = False
        self._stream_buffer = ""
        self._stream_bar.visible = False
        self._stream_bar.update()

        # Show plain text for errors
        self._result_area.visible = True
        color = ERROR_COLOR if is_error else SUCCESS_COLOR
        self._result_area.content = ft.Text(message, color=color)
        self._result_area.update()
