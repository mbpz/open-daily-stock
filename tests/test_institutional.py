# -*- coding: utf-8 -*-
"""Tests for institutional activity tracking module"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestDataServiceInstitutionalActions:
    """Test DataService institutional actions"""

    def test_get_institutional_action_exists(self):
        """DataService should have get_institutional action"""
        from src.data_service import DataService
        service = DataService()
        assert "get_institutional" in service._actions
        assert hasattr(service, "_handle_get_institutional")

    def test_get_dragon_board_action_exists(self):
        """DataService should have get_dragon_board action"""
        from src.data_service import DataService
        service = DataService()
        assert "get_dragon_board" in service._actions
        assert hasattr(service, "_handle_get_dragon_board")

    def test_get_institutional_returns_data(self):
        """get_institutional should return data"""
        from src.data_service import DataService
        service = DataService()

        # Mock the institutional module functions
        with patch('src.institutional.get_institutional_summary') as mock_summary:
            mock_summary.return_value = {
                "code": "600519",
                "major_shareholders": [],
                "institutional_surveys": [],
                "timestamp": "2024-01-01T00:00:00"
            }
            result = service._handle_request({"action": "get_institutional", "code": "600519"})
            assert result.get("status") == "ok"
            assert "data" in result

    def test_get_institutional_missing_code(self):
        """get_institutional without code should return error"""
        from src.data_service import DataService
        service = DataService()

        result = service._handle_request({"action": "get_institutional"})
        assert result.get("status") == "error"
        assert "code" in result.get("message", "").lower()

    def test_get_dragon_board_returns_data(self):
        """get_dragon_board should return data"""
        from src.data_service import DataService
        service = DataService()

        # Mock the dragon board function
        with patch('src.institutional.get_dragon_board') as mock_board:
            mock_board.return_value = []
            result = service._handle_request({"action": "get_dragon_board"})
            assert result.get("status") == "ok"
            assert "data" in result

    def test_get_dragon_board_with_date(self):
        """get_dragon_board with date should return data"""
        from src.data_service import DataService
        service = DataService()

        with patch('src.institutional.get_dragon_board') as mock_board:
            mock_board.return_value = []
            result = service._handle_request({"action": "get_dragon_board", "date": "2024-01-15"})
            assert result.get("status") == "ok"
            assert "data" in result


class TestInstitutionalModule:
    """Test institutional.py module functions"""

    def test_format_institutional_report(self):
        """format_institutional_report should return a string"""
        from src.institutional import format_institutional_report

        data = {
            "major_shareholders": [],
            "institutional_surveys": []
        }
        result = format_institutional_report(data, "600519")
        assert isinstance(result, str)

    def test_format_institutional_report_with_data(self):
        """format_institutional_report with data should format correctly"""
        from src.institutional import format_institutional_report

        data = {
            "major_shareholders": [
                {"title": "大股东增持公告", "snippet": "某大股东宣布增持", "published_date": "2024-01-01"}
            ],
            "institutional_surveys": [
                {"title": "机构调研公告", "snippet": "某机构进行调研", "published_date": "2024-01-02"}
            ]
        }
        result = format_institutional_report(data, "600519")
        assert isinstance(result, str)
        assert "大股东增减持" in result
        assert "机构调研" in result

    def test_get_institutional_summary_returns_dict(self):
        """get_institutional_summary should return a dict"""
        from src.institutional import get_institutional_summary

        with patch('src.institutional.get_major_shareholder_changes') as mock_major:
            with patch('src.institutional.get_institutional_surveys') as mock_surveys:
                mock_major.return_value = []
                mock_surveys.return_value = []
                result = get_institutional_summary("600519")
                assert isinstance(result, dict)
                assert "code" in result
                assert "major_shareholders" in result
                assert "institutional_surveys" in result