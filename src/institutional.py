# -*- coding: utf-8 -*-
"""
===================================
机构动向追踪模块 (Institutional Activity Tracking)
===================================

职责：
1. 大股东增减持信息（通过搜索获取）
2. 机构调研信息聚合（通过搜索获取）
3. 龙虎榜数据（优先akshare，其次搜索）

数据来源：
- akshare: 龙虎榜详情、机构调研统计
- 搜索服务: 大股东增减持、机构调研新闻
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_major_shareholder_changes(code: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    获取大股东增减持信息（通过搜索）

    Args:
        code: 股票代码
        days: 搜索最近天数（默认30天）

    Returns:
        大股东增减持信息列表
    """
    try:
        from src.search_service import SearchService
        from src.config import get_config

        config = get_config()
        search_service = SearchService(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            serpapi_keys=config.serpapi_keys
        )

        # 获取股票名称
        from src.analyzer import STOCK_NAME_MAP
        name = STOCK_NAME_MAP.get(code, code)

        # 构建搜索查询：大股东增减持
        queries = [
            f"{name} {code} 大股东 增持",
            f"{name} {code} 大股东 减持",
            f"{name} {code} 股东 增减持 公告",
        ]

        all_results = []
        seen_urls = set()

        for query in queries[:2]:  # 限制查询次数
            results = search_service.search_all(query, count=5)
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "type": "major_shareholder_change",
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet[:200] if r.snippet else "",
                        "source": r.source,
                        "published_date": r.published_date,
                    })

        logger.info(f"[机构追踪] 获取大股东增减持信息 {code}: {len(all_results)} 条")
        return all_results

    except Exception as e:
        logger.error(f"[机构追踪] 获取大股东增减持失败 [{code}]: {e}")
        return []


def get_institutional_surveys(code: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    获取机构调研信息（通过搜索）

    Args:
        code: 股票代码
        days: 搜索最近天数（默认30天）

    Returns:
        机构调研信息列表
    """
    try:
        from src.search_service import SearchService
        from src.config import get_config

        config = get_config()
        search_service = SearchService(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            serpapi_keys=config.serpapi_keys
        )

        # 获取股票名称
        from src.analyzer import STOCK_NAME_MAP
        name = STOCK_NAME_MAP.get(code, code)

        # 构建搜索查询：机构调研
        queries = [
            f"{name} {code} 机构调研",
            f"{name} {code} 机构 调研 活动",
            f"{name} {code} 机构投资者 调研",
        ]

        all_results = []
        seen_urls = set()

        for query in queries[:2]:  # 限制查询次数
            results = search_service.search_all(query, count=5)
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "type": "institutional_survey",
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet[:200] if r.snippet else "",
                        "source": r.source,
                        "published_date": r.published_date,
                    })

        logger.info(f"[机构追踪] 获取机构调研信息 {code}: {len(all_results)} 条")
        return all_results

    except Exception as e:
        logger.error(f"[机构追踪] 获取机构调研信息失败 [{code}]: {e}")
        return []


def get_dragon_board(date: str = None, days: int = 5) -> List[Dict[str, Any]]:
    """
    获取龙虎榜数据（优先akshare，其次搜索）

    Args:
        date: 指定日期，格式 "YYYY-MM-DD"，默认获取最近交易日
        days: 搜索最近天数（当akshare失败时）

    Returns:
        龙虎榜数据列表
    """
    import akshare as ak

    try:
        # 确定日期范围
        if date:
            start_date = date
            end_date = date
        else:
            # 获取最近 days 个交易日
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        logger.info(f"[龙虎榜] 获取数据: {start_date} ~ {end_date}")

        # 优先使用 akshare 获取龙虎榜详情
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)

        if df is None or df.empty:
            logger.warning(f"[龙虎榜] akshare 返回空数据，尝试搜索备选")
            return _get_dragon_board_fallback(days)

        # 转换为 dict 列表
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("date", "")),
                "code": str(row.get("code", "")),
                "name": str(row.get("name", "")),
                "reason": str(row.get("reason", "")),
                "buy_amount": float(row.get("buy_amount", 0)) if row.get("buy_amount") else 0,
                "sell_amount": float(row.get("sell_amount", 0)) if row.get("sell_amount") else 0,
                "net_amount": float(row.get("net_amount", 0)) if row.get("net_amount") else 0,
            })

        logger.info(f"[龙虎榜] 获取成功: {len(result)} 条")
        return result

    except Exception as e:
        logger.warning(f"[龙虎榜] akshare 获取失败: {e}，尝试搜索备选")
        return _get_dragon_board_fallback(days)


def _get_dragon_board_fallback(days: int = 5) -> List[Dict[str, Any]]:
    """
    通过搜索获取龙虎榜数据（akshare失败时的备选方案）

    Args:
        days: 搜索最近天数

    Returns:
        龙虎榜数据列表
    """
    try:
        from src.search_service import SearchService
        from src.config import get_config

        config = get_config()
        search_service = SearchService(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            serpapi_keys=config.serpapi_keys
        )

        # 搜索龙虎榜新闻
        queries = [
            "龙虎榜 今日 营业部 买卖",
            "龙虎榜数据 机构 席位",
            "龙虎榜 异动 股票",
        ]

        all_results = []
        seen_urls = set()

        for query in queries[:2]:
            results = search_service.search_all(query, count=8)
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append({
                        "type": "dragon_board_news",
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet[:200] if r.snippet else "",
                        "source": r.source,
                        "published_date": r.published_date,
                    })

        logger.info(f"[龙虎榜] 搜索备选获取: {len(all_results)} 条")
        return all_results

    except Exception as e:
        logger.error(f"[龙虎榜] 搜索备选失败: {e}")
        return []


def format_institutional_report(data: Dict[str, Any], code: str) -> str:
    """
    格式化机构动向报告

    Args:
        data: 包含 major_shareholders, institutional_surveys 的字典
        code: 股票代码

    Returns:
        格式化的报告文本
    """
    from src.analyzer import STOCK_NAME_MAP
    name = STOCK_NAME_MAP.get(code, code)

    lines = [
        f"【{name}({code}) 机构动向追踪】",
        ""
    ]

    # 大股东增减持
    major_shareholders = data.get("major_shareholders", [])
    if major_shareholders:
        lines.append("【大股东增减持】")
        for i, item in enumerate(major_shareholders[:5], 1):
            date_str = f" [{item.get('published_date', '')}]" if item.get('published_date') else ""
            lines.append(f"  {i}. {item.get('title', '')}{date_str}")
            snippet = item.get('snippet', '')
            if snippet:
                lines.append(f"     {snippet[:100]}...")
        lines.append("")
    else:
        lines.append("【大股东增减持】暂无数据")
        lines.append("")

    # 机构调研
    institutional_surveys = data.get("institutional_surveys", [])
    if institutional_surveys:
        lines.append("【机构调研】")
        for i, item in enumerate(institutional_surveys[:5], 1):
            date_str = f" [{item.get('published_date', '')}]" if item.get('published_date') else ""
            lines.append(f"  {i}. {item.get('title', '')}{date_str}")
            snippet = item.get('snippet', '')
            if snippet:
                lines.append(f"     {snippet[:100]}...")
        lines.append("")
    else:
        lines.append("【机构调研】暂无数据")
        lines.append("")

    return "\n".join(lines)


def get_institutional_summary(code: str) -> Dict[str, Any]:
    """
    获取机构动向汇总（大股东增减持 + 机构调研）

    Args:
        code: 股票代码

    Returns:
        包含两类数据的字典
    """
    major_shareholders = get_major_shareholder_changes(code)
    institutional_surveys = get_institutional_surveys(code)

    return {
        "code": code,
        "major_shareholders": major_shareholders,
        "institutional_surveys": institutional_surveys,
        "timestamp": datetime.now().isoformat(),
    }