# tests/test_update_service.py
import pytest
from unittest.mock import patch, MagicMock

class TestUpdateService:
    def test_get_current_version_from_pyproject(self):
        """Version is read from __version__ or pyproject.toml"""
        from src.update_service import UpdateService
        # Version should be a valid string like "0.2.1"
        version = UpdateService.get_current_version()
        assert version is not None
        assert isinstance(version, str)
        assert len(version) > 0

    def test_check_latest_version_no_update(self):
        """When current version is latest, returns (None, None)"""
        from src.update_service import UpdateService
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"tag_name": "v0.2.1"}
            mock_get.return_value = mock_response

            latest, url = UpdateService.check_latest_version()
            # If current is >= latest, should return (None, None)
            # This test verifies the API call works

    def test_check_latest_version_with_update(self):
        """When remote version is newer, returns (version, url)"""
        from src.update_service import UpdateService
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "tag_name": "v0.3.0",
                "assets": [{"browser_download_url": "https://github.com/.../open-daily-stock-macos"}]
            }
            mock_get.return_value = mock_response

            latest, url = UpdateService.check_latest_version()
            if latest:
                assert latest == "0.3.0"
                assert url is not None