# tests/test_refresh_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

class TestRefreshService:
    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.stock_list = ["600519", "000001"]
        config.schedule_refresh_time = "18:00"
        return config

    def test_refresh_service_initialization(self, mock_config):
        """RefreshService initializes with config"""
        from src.refresh_service import RefreshService
        service = RefreshService(mock_config)
        assert service._config == mock_config
        assert service._dp is not None
        assert service._pipeline is not None

    @pytest.mark.asyncio
    async def test_refresh_all_returns_results(self, mock_config):
        """refresh_all returns list of analysis results"""
        from src.refresh_service import RefreshService

        with patch.object(RefreshService, '__init__', lambda self, config: None):
            service = RefreshService(mock_config)
            service._config = mock_config
            service._dp = MagicMock()
            service._dp.fetch_all = AsyncMock()
            service._dp.get_data.return_value = {}
            service._pipeline = MagicMock()
            service._pipeline.run = MagicMock(return_value=[])

            results = await service.refresh_all()
            assert isinstance(results, list)