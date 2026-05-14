import pytest
from unittest.mock import patch, Mock

def test_check_update_returns_latest_version():
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes and improvements"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker()
        latest = checker.check_latest_version()
        assert latest == "v0.5.0"

def test_check_update_detects_new_version():
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker(current_version="v0.4.0")
        assert checker.is_new_version_available() == True

def test_check_update_no_new_version():
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(json=lambda: {
            "tag_name": "v0.5.0",
            "body": "Bug fixes"
        })
        from src.update_checker import UpdateChecker
        checker = UpdateChecker(current_version="v0.5.0")
        assert checker.is_new_version_available() == False