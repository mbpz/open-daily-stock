"""screen handlers — 股票筛选器 (按市值/PE/行业/涨跌幅)。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def screen_stocks(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """股票筛选器 - 根据条件筛选股票"""
    try:
        import akshare as ak
        from data_provider.realtime_types import safe_float

        # 获取筛选条件
        market_cap_min = req.get("market_cap_min")  # 最小市值（亿元）
        market_cap_max = req.get("market_cap_max")  # 最大市值（亿元）
        pe_min = req.get("pe_min")  # 最小市盈率
        pe_max = req.get("pe_max")  # 最大市盈率
        industry = req.get("industry")  # 行业筛选
        change_pct_min = req.get("change_pct_min")  # 最小涨跌幅%
        change_pct_max = req.get("change_pct_max")  # 最大涨跌幅%

        logger.info(f"[筛选器] 开始筛选: 市值={market_cap_min}-{market_cap_max}, "
                    f"PE={pe_min}-{pe_max}, 行业={industry}, 涨跌幅={change_pct_min}-{change_pct_max}")

        # 获取全市场实时行情（东方财富数据源）
        df = ak.stock_zh_a_spot_em()

        if df is None or df.empty:
            logger.warning("[筛选器] 未获取到行情数据")
            return {"status": "ok", "data": [], "message": "无行情数据"}

        # 重命名列以便后续处理
        column_mapping = {
            '代码': 'code',
            '名称': 'name',
            '最新价': 'price',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change_amount',
            '成交量': 'volume',
            '成交额': 'amount',
            '市盈率-动态': 'pe',
            '市净率': 'pb',
            '总市值': 'total_mv',
            '流通市值': 'circ_mv',
        }
        df = df.rename(columns=column_mapping)

        # 转换数值类型
        for col in ['price', 'change_pct', 'change_amount', 'volume', 'amount', 'pe', 'pb', 'total_mv', 'circ_mv']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: safe_float(x) if not isinstance(x, (int, float)) else x)

        # 应用筛选条件
        filtered = df.copy()

        # 市值筛选（总市值单位是元，转换为亿元）
        if market_cap_min is not None:
            filtered = filtered[filtered['total_mv'].apply(
                lambda x: x is not None and x > 0 and x / 1e8 >= market_cap_min)]
        if market_cap_max is not None:
            filtered = filtered[filtered['total_mv'].apply(
                lambda x: x is not None and x > 0 and x / 1e8 <= market_cap_max)]

        # 市盈率筛选
        if pe_min is not None:
            filtered = filtered[filtered['pe'].apply(lambda x: x is not None and x >= pe_min)]
        if pe_max is not None:
            filtered = filtered[filtered['pe'].apply(lambda x: x is not None and x <= pe_max)]

        # 涨跌幅筛选
        if change_pct_min is not None:
            filtered = filtered[filtered['change_pct'].apply(lambda x: x is not None and x >= change_pct_min)]
        if change_pct_max is not None:
            filtered = filtered[filtered['change_pct'].apply(lambda x: x is not None and x <= change_pct_max)]

        # 行业筛选（需要获取行业数据）
        if industry:
            try:
                industry_df = ak.stock_board_industry_cons_em(symbol=industry)
                if industry_df is not None and not industry_df.empty:
                    industry_codes = set(industry_df['代码'].astype(str).tolist())
                    filtered = filtered[filtered['code'].astype(str).isin(industry_codes)]
            except Exception as e:
                logger.warning(f"[筛选器] 行业筛选失败: {e}")

        # 转换为结果列表
        results = []
        for _, row in filtered.iterrows():
            results.append({
                'code': str(row.get('code', '')),
                'name': str(row.get('name', '')),
                'price': row.get('price'),
                'change_pct': row.get('change_pct'),
                'volume': row.get('volume'),
                'pe': row.get('pe'),
                'pb': row.get('pb'),
                'total_mv': row.get('total_mv'),
                'circ_mv': row.get('circ_mv'),
            })

        logger.info(f"[筛选器] 筛选完成: 符合条件的股票 {len(results)} 只")
        return {"status": "ok", "data": results, "count": len(results)}

    except Exception as e:
        logger.error(f"[筛选器] 筛选失败: {e}")
        return {"status": "error", "message": f"筛选失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_screen_stocks = partial(screen_stocks, service)
    service._actions["screen_stocks"] = "_handle_screen_stocks"
