"""K线历史回放页面

使用 DataService 获取K线数据并展示图表。
支持 MA5/MA10/MA20 均线指标叠加显示。
"""
import flet as ft
from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, ACCENT_COLOR

from src.charts import create_kline_chart


class KLinePage(ft.Container):
    """K线历史回放展示页面"""

    def __init__(self, app, data_provider=None):
        super().__init__()
        self.app = app
        self._dp = data_provider

        # 图表图像
        self._chart_image = ft.Image(
            src="",
            width=700,
            height=450,
            fit=ft.ImageFit.CONTAIN,
        )

        # 股票代码输入
        self._code_input = ft.TextField(
            hint_text="股票代码，如: 600519",
            width=200,
        )

        # 天数输入
        self._days_input = ft.TextField(
            hint_text="天数",
            value="60",
            width=80,
        )

        # 显示按钮
        self._btn = ft.Button(
            "显示K线",
            icon=ft.Icons.SHOW_CHART,
            on_click=self._show_chart,
            bgcolor=ACCENT_COLOR,
            color=ft.Colors.WHITE,
        )

        # 加载指示器
        self._progress_ring = ft.ProgressRing(width=20, height=20, visible=False)

        # 状态文本
        self._status_text = ft.Text("", color=TEXT_SECONDARY, size=12)

        # 表头
        header = ft.Text("K线历史回放", size=24, weight=ft.FontWeight.BOLD)

        # 输入行
        input_row = ft.Row([
            ft.Text("股票代码:", width=80),
            self._code_input,
            ft.Container(width=10),
            ft.Text("天数:", width=40),
            self._days_input,
            ft.Container(width=10),
            self._btn,
            self._progress_ring,
            self._status_text,
        ])

        # 图表容器
        self._chart_container = ft.Container(
            content=ft.Column([
                ft.Text("输入股票代码，点击显示K线", color=TEXT_SECONDARY),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
            bgcolor=CARD_BG,
            border_radius=10,
            width=750,
            height=500,
        )

        self.content = ft.Container(
            content=ft.Column([
                header,
                ft.Divider(height=2, color=CARD_BORDER),
                input_row,
                ft.Container(height=20),
                ft.Row([
                    self._chart_container,
                ], scroll=ft.ScrollMode.AUTO),
            ]),
            padding=10,
        )

    async def _show_chart(self, e):
        """显示K线图表"""
        code = self._code_input.value.strip()
        if not code:
            self._status_text.value = "请输入股票代码"
            self._status_text.update()
            return

        try:
            days = int(self._days_input.value.strip()) if self._days_input.value.strip() else 60
        except ValueError:
            days = 60

        # 显示加载状态
        self._progress_ring.visible = True
        self._status_text.value = f"正在获取 {code} 数据..."
        self._chart_container.content = ft.Column([
            ft.ProgressRing(width=40, height=40),
            ft.Text(f"正在获取 {code} 数据...", color=TEXT_SECONDARY),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self._chart_container.update()
        self._status_text.update()

        try:
            # 通过 DataService 获取 K线数据
            import asyncio
            result = await asyncio.to_thread(
                self._get_kline_data_sync, code, days
            )

            if result.get("status") != "ok":
                self._status_text.value = result.get("message", "获取数据失败")
                self._progress_ring.visible = False
                self._chart_container.content = ft.Column([
                    ft.Text(f"加载失败: {result.get('message', '未知错误')}", color=ft.colors.RED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                self._chart_container.update()
                self._status_text.update()
                return

            image_path = result.get("image_path", "")
            history_data = result.get("data", [])

            if not image_path and not history_data:
                self._status_text.value = f"无法获取 {code} 的数据"
                self._progress_ring.visible = False
                self._chart_container.content = ft.Column([
                    ft.Text(f"无法获取 {code} 的数据", color=ft.colors.RED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                self._chart_container.update()
                self._status_text.update()
                return

            # 如果已有 image_path，直接使用
            if image_path:
                self._chart_image.src = image_path
                self._chart_container.content = self._chart_image
            else:
                # 否则生成图表
                chart_path = await asyncio.to_thread(
                    create_kline_chart, history_data, code, days
                )
                self._chart_image.src = chart_path
                self._chart_container.content = self._chart_image

            self._status_text.value = f"{code} - {len(history_data)} 条数据"

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self._status_text.value = f"错误: {str(ex)}"
            self._chart_container.content = ft.Column([
                ft.Text(f"加载失败: {str(ex)}", color=ft.colors.RED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        finally:
            self._progress_ring.visible = False
            self._chart_container.update()
            self._status_text.update()

    def _get_kline_data_sync(self, code: str, days: int):
        """同步获取K线数据（在线程中运行）"""
        from src.data_service import DataService
        service = DataService()
        return service._handle_request({
            "action": "get_kline_data",
            "code": code,
            "days": days,
        })