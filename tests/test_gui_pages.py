# -*- coding: utf-8 -*-
"""GUI pages tests for MarketsPage, TasksPage, AnalyzePage, ConfigPage, LogsPage"""
import pytest
from unittest.mock import MagicMock, AsyncMock

# Check if flet is available - if not, skip all tests
flet_available = False
try:
    import flet as ft
    flet_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not flet_available, reason="flet not installed")

from tui.data.task_store import TaskStore
from tui.data.wrapper import DataProviderWrapper, MarketData


class TestMarketsPage:
    """Tests for MarketsPage widget"""

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock DataProviderWrapper with no data"""
        dp = MagicMock(spec=DataProviderWrapper)
        dp.get_data.return_value = {}
        dp.fetch_all = AsyncMock()
        dp.get_last_update.return_value = None
        return dp

    @pytest.fixture
    def mock_data_provider_with_data(self):
        """Create mock DataProviderWrapper with sample data"""
        dp = MagicMock(spec=DataProviderWrapper)
        dp.get_data.return_value = {
            "000001": MarketData("000001", "平安银行", 12.50, 0.85, "15.2万"),
            "600519": MarketData("600519", "贵州茅台", 1680.00, -1.25, "3.2万"),
        }
        dp.fetch_all = AsyncMock()
        dp.get_last_update.return_value = "10:30:00"
        return dp

    @pytest.fixture
    def mock_app(self):
        """Create mock app with page.run_task"""
        app = MagicMock()
        app.page = MagicMock()
        app.page.run_task = MagicMock()
        app.update_status = MagicMock()
        return app

    def test_markets_page_empty_initialization(self, mock_app, mock_data_provider):
        """test_markets_page_empty_initialization - MarketsPage with no data initializes correctly"""
        from gui.pages.markets import MarketsPage
        page = MarketsPage(mock_app, mock_data_provider)
        # Build should not raise
        control = page.build()
        assert control is not None
        # Table should exist with columns but no rows
        assert page.table is not None
        assert len(page.table.rows) == 0

    def test_markets_page_with_data(self, mock_app, mock_data_provider_with_data):
        """test_markets_page_with_data - MarketsPage displays data"""
        from gui.pages.markets import MarketsPage
        page = MarketsPage(mock_app, mock_data_provider_with_data)
        page.build()
        # Manually load data to test _load_data
        page._load_data()
        # Should have rows
        assert len(page.table.rows) == 2


class TestTasksPage:
    """Tests for TasksPage widget"""

    @pytest.fixture
    def task_store(self):
        """Create TaskStore with sample tasks"""
        store = TaskStore()
        store.add_task("600519")
        store.add_task("000001")
        return store

    @pytest.fixture
    def mock_app(self):
        """Create mock app"""
        app = MagicMock()
        app.page = MagicMock()
        app.page.run_task = MagicMock()
        app.update_status = MagicMock()
        return app

    def test_tasks_page_empty_initialization(self, mock_app):
        """test_tasks_page_empty_initialization - TasksPage with no task store"""
        from gui.pages.tasks import TasksPage
        page = TasksPage(mock_app, None)
        control = page.build()
        assert control is not None

    def test_tasks_page_with_tasks(self, mock_app, task_store):
        """test_tasks_page_with_tasks - TasksPage displays tasks"""
        from gui.pages.tasks import TasksPage
        page = TasksPage(mock_app, task_store)
        page.build()
        # Should have controls in task_list
        assert len(page.task_list.controls) == 2


class TestLogsPage:
    """Tests for LogsPage widget"""

    @pytest.fixture
    def mock_app(self):
        """Create mock app"""
        app = MagicMock()
        app.page = MagicMock()
        app.page.run_task = MagicMock()
        app.update_status = MagicMock()
        return app

    def test_logs_page_initialization(self, mock_app):
        """test_logs_page_initialization - LogsPage initializes correctly"""
        from gui.pages.logs import LogsPage
        page = LogsPage(mock_app)
        control = page.build()
        assert control is not None
        assert page._log_content is not None


class TestAnalyzePage:
    """Tests for AnalyzePage widget"""

    @pytest.fixture
    def mock_pipeline(self):
        """Create mock pipeline"""
        pipeline = MagicMock()
        pipeline.analyze = AsyncMock(return_value="Analysis complete")
        return pipeline

    @pytest.fixture
    def mock_app(self):
        """Create mock app"""
        app = MagicMock()
        app.page = MagicMock()
        app.page.run_task = MagicMock()
        app.update_status = MagicMock()
        return app

    def test_analyze_page_initialization(self, mock_app, mock_pipeline):
        """test_analyze_page_initialization - AnalyzePage initializes correctly"""
        from gui.pages.analyze import AnalyzePage
        page = AnalyzePage(mock_app, mock_pipeline)
        control = page.build()
        assert control is not None


class TestConfigPage:
    """Tests for ConfigPage widget"""

    @pytest.fixture
    def mock_app(self):
        """Create mock app"""
        app = MagicMock()
        app.page = MagicMock()
        app.page.run_task = MagicMock()
        app.update_status = MagicMock()
        return app

    def test_config_page_initialization(self, mock_app):
        """test_config_page_initialization - ConfigPage initializes correctly"""
        from gui.pages.config import ConfigPage
        page = ConfigPage(mock_app)
        control = page.build()
        assert control is not None
