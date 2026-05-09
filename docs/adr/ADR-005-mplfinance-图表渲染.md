# ADR-005: mplfinance 图表渲染

**Date:** 2026-05-10
**Status:** Accepted

---

## Context

open-daily-stock 需要生成 K 线图表（蜡烛图）用于：

1. **K 线历史回放** — 查看个股日线走势，叠加移动均线 (MA5/MA10/MA20)
2. **技术指标叠加** — RSI、MACD、Bollinger Bands、KDJ、WR、OBV 等
3. **GUI 内嵌展示** — Flet 图形界面中显示图表

图表不需要交互式缩放/拖拽，只需静态渲染后嵌入 GUI 页面。

可选方案：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **mplfinance** | 专为金融 K 线设计，开箱即用 | 静态 PNG 输出，无交互 |
| Plotly | 交互式缩放/悬停提示 | 依赖重，JSON 序列化，需 WebView |
| lightweight-charts | 专业金融图表，高性能 | JavaScript 库，需 WebView 桥接 |
| 自定义 matplotlib | 完全控制样式 | 重复造轮子，K 线实现复杂 |

## Decision

使用 **mplfinance** 生成 K 线图表，输出 PNG 静态图片。

### 选择理由

1. **金融专用** — mplfinance 专为蜡烛图设计，内置成交量面板、均线叠加、颜色主题
2. **依赖最小** — 基于 matplotlib，无 Web/JS 依赖，PyInstaller 打包友好
3. **开箱即用** — 一行 `mpf.plot(df, type='candle')` 生成完整 K 线图
4. **指标扩展** — `mpf.make_addplot()` 支持添加额外面板（RSI/MACD/KDJ 等）
5. **静态输出匹配需求** — GUI 不需要交互式图表，PNG 直接嵌入 Flet 页面即可

### 实施

```python
# src/charts.py
import mplfinance as mpf
import pandas as pd

def generate_kline_chart(
    df: pd.DataFrame,
    code: str,
    indicators: list[str] | None = None,
    mas: list[int] | None = None,
) -> str:
    """生成 K 线图表，返回 PNG 文件路径"""
    # 市场颜色：中国习惯红跌绿涨
    market_colors = mpf.make_marketcolors(up="green", down="red", ...)
    style = mpf.make_mpf_style(marketcolors=market_colors, ...)

    # 构建附加面板（技术指标）
    addplots = _build_indicators(df, indicators or [], code)

    fig, axes = mpf.plot(
        df,
        type="candle",
        style=style,
        volume=True,
        mav=mas or [5, 10, 20],  # 移动均线
        addplot=addplots,
        savefig=output_path,
        returnfig=True,
    )
    plt.close(fig)
    return output_path
```

### 支持的指标

| 指标 | mplfinance 支持方式 | 实现 |
|------|---------------------|------|
| MA5/MA10/MA20 | 内置 `mav` 参数 | 直接参数 |
| 成交量 | 内置 `volume=True` | 直接参数 |
| RSI (相对强弱) | `make_addplot()` | 自定义计算 + addplot |
| MACD | `make_addplot()` | 自定义计算 + addplot |
| Bollinger Bands | `make_addplot()` | 自定义计算 + addplot |
| KDJ | `make_addplot()` | 自定义计算 + addplot |
| WR (威廉指标) | `make_addplot()` | 自定义计算 + addplot |
| OBV (能量潮) | `make_addplot()` | 自定义计算 + addplot |

### 输出缓存

图表 PNG 保存在项目根目录的 `charts_cache/` 目录，按股票代码和参数命名：
```
charts_cache/600519_d60_ma5-10-20_rsi_macd.png
```

---

## Consequences

**正面：**
- 金融图表专用库，生成效果专业
- 依赖轻量，打包体积小
- 与 matplotlib 生态无缝集成
- A 股红跌绿涨颜色习惯直接支持

**负面：**
- 静态 PNG 无缩放/拖拽交互（对 K 线回放场景足够，但无法点击查看详情）
- 无头环境下中文/字体渲染可能异常（CI/CD 和某些 Linux 桌面）
- 高频更新（如每秒刷新）时 PNG 写入性能不如 Canvas 方案

**替代方案考虑：**
- Plotly：交互性强但依赖重（500MB+），不适合 PyInstaller 打包
- lightweight-charts：效果最佳但需要 JS/WebView，增加架构复杂度
- 自定义 matplotlib：可完全控制但需要从头实现 K 线/均线/指标逻辑，工作量大

**未来迁移路径：**
如果未来需要交互式图表（P4-1 画线工具等），可保留 mplfinance 用于静态导出，新增 WebView 方案用于交互式展示，两者并存。
