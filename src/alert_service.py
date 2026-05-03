# -*- coding: utf-8 -*-
"""Alert service for price change notifications"""
from typing import Dict, Optional
from dataclasses import dataclass

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

import logging

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Price data with timestamp"""
    code: str
    name: str
    price: float
    change_pct: float


class AlertService:
    """
    Alert service that monitors price changes and sends desktop notifications.

    Stores previous prices in memory and triggers notification when change > threshold%.
    """

    def __init__(self, threshold_pct: float = 5.0):
        """
        Initialize AlertService.

        Args:
            threshold_pct: Percentage threshold for alerts (default: 5.0)
        """
        self._threshold_pct = threshold_pct
        self._previous_prices: Dict[str, PriceData] = {}

    def check_and_alert(self, market: Dict) -> bool:
        """
        Check if price change exceeds threshold and send alert if needed.

        Args:
            market: Market data dict with 'code', 'name', 'price', 'change_pct'

        Returns:
            True if alert was sent, False otherwise
        """
        code = market.get("code")
        name = market.get("name", "")
        price = market.get("price", 0)
        change_pct = market.get("change_pct", 0)

        if not code or price <= 0:
            return False

        previous = self._previous_prices.get(code)
        alert_triggered = False

        if previous is not None and previous.price > 0:
            # Calculate price change percentage from previous price
            price_change_pct = ((price - previous.price) / previous.price) * 100

            if abs(price_change_pct) > self._threshold_pct:
                self._send_notification(code, name, price_change_pct)
                alert_triggered = True
        else:
            # First time seeing this stock, just store the price
            pass

        # Update stored price
        self._previous_prices[code] = PriceData(
            code=code,
            name=name,
            price=price,
            change_pct=change_pct
        )

        return alert_triggered

    def check_and_alert_from_change_pct(self, market: Dict) -> bool:
        """
        Check if change_pct exceeds threshold and send alert if needed.

        This method uses the change_pct directly from the data source
        (percent change from previous close).

        Args:
            market: Market data dict with 'code', 'name', 'price', 'change_pct'

        Returns:
            True if alert was sent, False otherwise
        """
        code = market.get("code")
        name = market.get("name", "")
        change_pct = market.get("change_pct", 0)

        if not code:
            return False

        if abs(change_pct) > self._threshold_pct:
            self._send_notification(code, name, change_pct)

            # Update stored price
            price = market.get("price", 0)
            self._previous_prices[code] = PriceData(
                code=code,
                name=name,
                price=price,
                change_pct=change_pct
            )
            return True

        # Update stored price even if no alert
        price = market.get("price", 0)
        self._previous_prices[code] = PriceData(
            code=code,
            name=name,
            price=price,
            change_pct=change_pct
        )
        return False

    def _send_notification(self, code: str, name: str, change_pct: float):
        """Send desktop notification using plyer"""
        if not PLYER_AVAILABLE:
            logger.warning("plyer not installed, skipping desktop notification")
            return

        message = f"股票 {code} 涨跌超过 {self._threshold_pct}%，当前涨幅 {change_pct:+.2f}%"

        try:
            notification.notify(
                title=f"行情异动提醒: {code}",
                message=message,
                app_name="Open Daily Stock",
                timeout=10
            )
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def get_previous_price(self, code: str) -> Optional[float]:
        """Get the previous price for a stock code"""
        previous = self._previous_prices.get(code)
        return previous.price if previous else None

    def clear(self):
        """Clear all stored prices"""
        self._previous_prices.clear()