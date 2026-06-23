# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 大盘复盘模块
===================================

职责：
1. 执行大盘复盘分析
2. 生成复盘报告
3. 保存和发送复盘报告
"""

import logging
from datetime import datetime
from typing import Optional

from src.notify import NotificationService
from src.market_analyzer import MarketAnalyzer
from src.search_pkg import SearchManager as SearchService
from src.analyzer import GeminiAnalyzer


logger = logging.getLogger(__name__)


def run_market_review(
    notifier: NotificationService, 
    analyzer: Optional[GeminiAnalyzer] = None, 
    search_service: Optional[SearchService] = None
) -> Optional[str]:
    """
    执行大盘复盘分析
    
    Args:
        notifier: 通知服务
        analyzer: AI分析器（可选）
        search_service: 搜索服务（可选）
    
    Returns:
        复盘报告文本
    """
    logger.info("开始执行大盘复盘分析...")
    
    try:
        market_analyzer = MarketAnalyzer(
            search_service=search_service,
            analyzer=analyzer
        )
        
        # 执行复盘
        review_report = market_analyzer.run_daily_review()
        
        if review_report:
            # 保存报告到文件
            date_str = datetime.now().strftime('%Y%m%d')
            report_filename = f"market_review_{date_str}.md"
            filepath = notifier.save_report_to_file(
                f"# 🎯 大盘复盘\n\n{review_report}", 
                report_filename
            )
            logger.info(f"大盘复盘报告已保存: {filepath}")
            
            # 推送通知
            if notifier.is_available():
                # 添加标题
                report_content = f"🎯 大盘复盘\n\n{review_report}"
                
                results = notifier.send(report_content)
                if any(r.success for r in results):
                    logger.info("大盘复盘推送成功")
                else:
                    logger.warning("大盘复盘推送失败")
            
            return review_report
        
    except Exception as e:
        logger.error(f"大盘复盘分析失败: {e}")
    
    return None
