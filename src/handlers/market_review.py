"""market_review handlers — 大盘概览 + 复盘报告 (P6-2)。"""
from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.storage import MarketReview, get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_market_overview(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get current market overview (indices, sectors, breadth)."""
    try:
        from src.market_analyzer import MarketAnalyzer
        analyzer = MarketAnalyzer(search_service=None, analyzer=None)
        overview = analyzer.get_market_overview()
        return {
            "status": "ok",
            "data": {
                "date": overview.date,
                "indices": [
                    {"name": i.name, "change": i.change, "pct_chg": i.pct_chg}
                    for i in overview.indices
                ] if overview.indices else [],
                "total_stocks": overview.total_stocks,
                "up_count": overview.up_count,
                "down_count": overview.down_count,
                "hot_sectors": [
                    {"name": s.name, "pct_chg": s.pct_chg}
                    for s in (overview.hot_sectors or [])
                ],
                "cold_sectors": [
                    {"name": s.name, "pct_chg": s.pct_chg}
                    for s in (overview.cold_sectors or [])
                ],
            }
        }
    except Exception as e:
        logger.error(f"获取市场概览失败: {e}")
        return {"status": "error", "message": str(e)}


def get_market_review(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Generate end-of-day market review report and save to DB (P6-2).

    Supports optional `force` param to regenerate even if today's report exists.
    """
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        force = req.get("force", False)

        # Check if today's report already exists (cache)
        if not force:
            try:
                db = get_db()
                with db.get_session() as session:
                    existing = session.query(MarketReview).filter(
                        MarketReview.review_date == today
                    ).first()
                    if existing:
                        return {
                            "status": "ok",
                            "report": existing.report_md,
                            "review_date": today,
                            "cached": True,
                        }
            except Exception:
                pass

        # Build MarketAnalyzer with configured AI provider
        from src.analyzer import GeminiAnalyzer
        from src.market_analyzer import MarketAnalyzer

        ai_analyzer = GeminiAnalyzer()
        if not ai_analyzer.is_available():
            ai_analyzer = None

        market_analyzer = MarketAnalyzer(
            search_service=None,
            analyzer=ai_analyzer,
        )
        report = market_analyzer.run_market_review()

        if not report:
            return {"status": "error", "message": "生成复盘报告失败（数据获取异常）"}

        # Extract short summary
        summary = report[:200].replace("#", "").replace("*", "").strip()

        # Save to DB
        try:
            db = get_db()
            with db.get_session() as session:
                review = MarketReview(
                    review_date=today,
                    report_md=report,
                    market_summary=summary,
                )
                session.add(review)
                session.commit()
            logger.info(f"Market review saved to DB for {today}")
        except Exception as e:
            logger.warning(f"Failed to save market review to DB: {e}")

        # Send notification
        try:
            from src.notify import NotificationService
            ns = NotificationService()
            ns.send(f"🎯 大盘复盘 {today}\n\n{summary}...")
        except Exception:
            pass

        return {
            "status": "ok",
            "report": report,
            "review_date": today,
            "cached": False,
        }
    except Exception as e:
        logger.error(f"生成市场复盘报告失败: {e}")
        return {"status": "error", "message": str(e)}


def get_market_reviews_history(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve historical market review reports (P6-2)."""
    try:
        limit = req.get("limit", 10)
        db = get_db()
        with db.get_session() as session:
            reviews = session.query(MarketReview).order_by(
                MarketReview.review_date.desc()
            ).limit(limit).all()
            return {
                "status": "ok",
                "data": [
                    {"review_date": r.review_date, "summary": r.market_summary, "report": r.report_md}
                    for r in reviews
                ],
            }
    except Exception as e:
        logger.error(f"查询历史复盘失败: {e}")
        return {"status": "error", "message": str(e)}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_market_overview = partial(get_market_overview, service)
    service._actions["get_market_overview"] = "_handle_get_market_overview"

    service._handle_get_market_review = partial(get_market_review, service)
    service._actions["get_market_review"] = "_handle_get_market_review"

    service._handle_get_market_reviews_history = partial(get_market_reviews_history, service)
    service._actions["get_market_reviews_history"] = "_handle_get_market_reviews_history"
