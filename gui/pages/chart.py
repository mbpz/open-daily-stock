"""K线图表页面"""
import flet as ft
import base64
from io import BytesIO
import pandas as pd
import mplfinance as mpf

from gui.theme import CARD_BG, CARD_BORDER, TEXT_SECONDARY, ACCENT_COLOR


class ChartPage(ft.Container):
    """K线图表展示页面"""

    def __init__(self, app, data_provider=None):
        super().__init__()
        self.app = app
        self._dp = data_provider

        # 图表图像
        self._chart_image = ft.Image(
            src_base64="",
            width=600,
            height=400,
            fit=ft.ImageFit.CONTAIN,
        )

        # 股票代码输入
        self._code_input = ft.TextField(
            hint_text="股票代码，如: 600519",
            width=200,
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
        header = ft.Text("K线图表", size=24, weight=ft.FontWeight.BOLD)

        # 输入行
        input_row = ft.Row([
            ft.Text("股票代码:", width=80),
            self._code_input,
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
            width=700,
            height=450,
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
            # 获取数据
            df = await get_daily_data_async(code, days=60)

            if df is None or df.empty:
                self._status_text.value = f"无法获取 {code} 的数据"
                self._progress_ring.visible = False
                self._chart_container.content = ft.Column([
                    ft.Text(f"无法获取 {code} 的数据", color=ft.colors.RED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
                self._chart_container.update()
                self._status_text.update()
                return

            # 生成K线图
            buf = await generate_candlestick_async(df, code)

            # 更新显示
            self._chart_image.src_base64 = buf
            self._chart_container.content = self._chart_image
            self._status_text.value = f"{code} - {len(df)} 条数据"

        except Exception as ex:
            self._status_text.value = f"错误: {str(ex)}"
            self._chart_container.content = ft.Column([
                ft.Text(f"加载失败: {str(ex)}", color=ft.colors.RED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        finally:
            self._progress_ring.visible = False
            self._chart_container.update()
            self._status_text.update()


# 对话框函数（在主线程运行避免线程安全问题）
def get_daily_data_sync(code: str, days: int = 60) -> pd.DataFrame:
    """同步获取日线数据"""
    from data_provider.base import DataFetcherManager
    try:
        manager = DataFetcherManager()
        df, _ = manager.get_daily_data(code, days=days)
        return df
    except Exception:
        return None


def generate_candlestick_sync(df: pd.DataFrame, code: str) -> str:
    """生成K线图并返回base64编码"""
    # 准备数据：确保列名为 mplfinance 需要的格式
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    # 设置日期为索引
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

    # 重命名列以匹配 mplfinance 要求
    df = df.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    })

    # 只保留需要的列
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

    # 设置样式
    mc = mpf.make_marketcolors(
        up='green', down='red',
        edge='inherit',
        wick='inherit',
        volume='in',
    )
    style = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle='-',
        gridcolor='#333333',
        facecolor='white',
        figcolor='white',
        y_on_right=True,
    )

    # 绘制图表
    fig, axes = mpf.plot(
        df,
        type='candle',
        style=style,
        title=f'{code} - K线',
        ylabel='价格',
        ylabel_lower='成交量',
        volume=True,
        figsize=(10, 6),
        returnfig=True,
        panel_ratios=(4, 2),
    )

    # 保存到字节流
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=80, facecolor='white')
    import matplotlib.pyplot as plt
    plt.close(fig)

    return base64.b64encode(buf.getvalue()).decode()


# 在 asyncio 事件循环中运行的异步函数
async def get_daily_data_async(code: str, days: int = 60) -> pd.DataFrame:
    """异步获取日线数据（在 thread pool 中运行）"""
    import asyncio
    return await asyncio.to_thread(get_daily_data_sync, code, days)


async def generate_candlestick_async(df: pd.DataFrame, code: str) -> str:
    """异步生成K线图（在 thread pool 中运行）"""
    import asyncio
    return await asyncio.to_thread(generate_candlestick_sync, df, code)