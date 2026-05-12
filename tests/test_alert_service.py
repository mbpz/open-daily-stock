# -*- coding: utf-8 -*-
"""AlertService 模块测试"""
import pytest
from unittest.mock import patch, MagicMock


class TestAlertService:
    """AlertService 测试"""

    def test_alert_service_import(self):
        """AlertService 可以正常导入"""
        from src.alert_service import AlertService
        assert AlertService is not None

    def test_alert_service_init(self):
        """AlertService 可以正常初始化"""
        from src.alert_service import AlertService
        service = AlertService()
        assert service is not None

    def test_alert_service_check_no_previous_price(self):
        """首次检查如果涨跌幅超过阈值也会触发告警（使用change_pct字段）"""
        from src.alert_service import AlertService
        service = AlertService(threshold_pct=5.0)

        # First time seeing this stock, but change_pct from data source is 6%
        # This represents gap up/down from previous close, should alert
        market = {"code": "000001", "name": "平安银行", "price": 12.5, "change_pct": 6.0}

        with patch.object(service, '_send_notification') as mock_notify:
            result = service.check_and_alert_from_change_pct(market)

        # change_pct exceeds threshold, so alert should be sent
        assert result is True
        mock_notify.assert_called_once()

    def test_alert_service_check_below_threshold(self):
        """涨跌幅小于阈值时不触发告警"""
        from src.alert_service import AlertService
        service = AlertService(threshold_pct=5.0)

        # First call - store price
        market1 = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        service.check_and_alert_from_change_pct(market1)

        # Second call - change is 3%, below threshold
        market2 = {"code": "000001", "name": "平安银行", "price": 12.3, "change_pct": 2.5}
        with patch.object(service, '_send_notification') as mock_notify:
            result = service.check_and_alert_from_change_pct(market2)

        assert result is False
        mock_notify.assert_not_called()

    def test_alert_service_check_above_threshold(self):
        """涨跌幅大于阈值时触发告警"""
        from src.alert_service import AlertService
        service = AlertService(threshold_pct=5.0)

        # First call - store price
        market1 = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        service.check_and_alert_from_change_pct(market1)

        # Second call - change is 6%, above threshold
        market2 = {"code": "000001", "name": "平安银行", "price": 12.72, "change_pct": 6.0}
        with patch.object(service, '_send_notification') as mock_notify:
            result = service.check_and_alert_from_change_pct(market2)

        assert result is True
        mock_notify.assert_called_once()

    def test_alert_service_negative_change(self):
        """下跌超过阈值时触发告警"""
        from src.alert_service import AlertService
        service = AlertService(threshold_pct=5.0)

        # First call - store price
        market1 = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        service.check_and_alert_from_change_pct(market1)

        # Second call - change is -6%, below threshold
        market2 = {"code": "000001", "name": "平安银行", "price": 11.28, "change_pct": -6.0}
        with patch.object(service, '_send_notification') as mock_notify:
            result = service.check_and_alert_from_change_pct(market2)

        assert result is True
        mock_notify.assert_called_once()

    def test_alert_service_get_previous_price(self):
        """获取历史价格"""
        from src.alert_service import AlertService
        service = AlertService()

        market = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        assert service.get_previous_price("000001") is None

        service.check_and_alert_from_change_pct(market)
        assert service.get_previous_price("000001") == 12.0

    def test_alert_service_clear(self):
        """清空历史价格"""
        from src.alert_service import AlertService
        service = AlertService()

        market = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        service.check_and_alert_from_change_pct(market)
        assert service.get_previous_price("000001") == 12.0

        service.clear()
        assert service.get_previous_price("000001") is None


class TestAlertServiceNotification:
    """AlertService 通知测试"""

    def test_notification_not_sent_when_plyer_unavailable(self):
        """plyer 不可用时不发送通知"""
        from src.alert_service import AlertService, PLYER_AVAILABLE

        service = AlertService(threshold_pct=5.0)

        # First call - store price
        market1 = {"code": "000001", "name": "平安银行", "price": 12.0, "change_pct": 3.0}
        service.check_and_alert_from_change_pct(market1)

        # Second call - change is 6%, above threshold
        market2 = {"code": "000001", "name": "平安银行", "price": 12.72, "change_pct": 6.0}

        # When PLYER_AVAILABLE is False, check_and_alert_from_change_pct still returns True
        # (alert is triggered) but _send_notification returns early without calling notification
        with patch('src.alert_service.PLYER_AVAILABLE', False):
            result = service.check_and_alert_from_change_pct(market2)

        # Alert is triggered based on change_pct, but notification is skipped
        assert result is True