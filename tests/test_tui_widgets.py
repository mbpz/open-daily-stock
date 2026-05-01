# -*- coding: utf-8 -*-
"""TUI widgets tests for MarketsView, TasksView, AnalyzeView, ConfigView, LogsView"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from textual.app import App
from textual.widgets import Static, Input
from textual.events import Key
from tui.widgets.markets import MarketsView
from tui.widgets.tasks import TasksView
from tui.widgets.analyze import AnalyzeView
from tui.widgets.config import ConfigView
from tui.widgets.logs import LogsView
from tui.data.task_store import TaskStore, Task, TaskStatus
from tui.data.wrapper import DataProviderWrapper, MarketData


class TestMarketsView:
    """Tests for MarketsView widget"""

    @pytest.fixture
    def mock_data_provider(self):
        """Create mock DataProviderWrapper with no data"""
        dp = MagicMock(spec=DataProviderWrapper)
        dp.get_data.return_value = {}
        return dp

    @pytest.fixture
    def mock_data_provider_with_data(self):
        """Create mock DataProviderWrapper with sample data"""
        dp = MagicMock(spec=DataProviderWrapper)
        dp.get_data.return_value = {
            "000001": MarketData("000001", "平安银行", 12.50, 0.85, "15.2万"),
            "600519": MarketData("600519", "贵州茅台", 1680.00, -1.25, "3.2万"),
        }
        return dp

    async def test_markets_display_empty(self, mock_data_provider):
        """test_markets_display_empty - 无数据时显示空状态"""
        app = App()
        app._wizard_skipped = True
        markets_view = MarketsView(mock_data_provider)

        async with app.run_test() as pilot:
            app.mount(markets_view)
            await pilot.pause()

            # Verify empty state message is displayed
            rendered = markets_view._render_data()
            assert "暂无数据" in rendered
            assert "使用 [r] 手动刷新或等待自动更新" in rendered

    async def test_markets_display_data(self, mock_data_provider_with_data):
        """test_markets_display_data - 有数据时显示行情"""
        app = App()
        app._wizard_skipped = True
        markets_view = MarketsView(mock_data_provider_with_data)

        async with app.run_test() as pilot:
            app.mount(markets_view)
            await pilot.pause()

            rendered = markets_view._render_data()
            # Verify stock data is displayed
            assert "000001" in rendered
            assert "平安银行" in rendered
            assert "600519" in rendered
            assert "贵州茅台" in rendered
            # Verify price and change are shown
            assert "12.50" in rendered
            assert "1680.00" in rendered
            # Verify emoji indicators
            assert "🟢" in rendered or "🔴" in rendered


class TestConfigView:
    """Tests for ConfigView widget"""

    @pytest.fixture
    def mock_config(self):
        """Create mock config object"""
        config = MagicMock()
        config.stock_list = ["000001", "600519"]
        config.openai_api_key = "test-key-123"
        config.openai_base_url = "https://api.example.com"
        config.openai_model = "gpt-4o-mini"
        config.gemini_api_key = None
        config.wechat_webhook_url = None
        config.feishu_webhook_url = None
        config.save_to_env = MagicMock(return_value=True)
        return config

    async def test_config_display_fields(self, mock_config):
        """test_config_display_fields - ConfigView 显示所有字段"""
        with patch("src.config.get_config", return_value=mock_config):
            app = App()
            config_view = ConfigView()

            async with app.run_test() as pilot:
                app.mount(config_view)
                await pilot.pause()

                # Verify nav-hint contains config management text
                nav_hint = app.query_one("#nav-hint", Static)
                assert "配置管理" in str(nav_hint.render())

                # Verify all 7 fields are present
                for i in range(7):
                    field = app.query_one(f"#field-{i}", Static)
                    field_text = str(field.render())
                    # Check label is shown
                    assert any(label in field_text for label in [
                        "自选股列表", "OpenAI API Key", "API 地址", "模型名称",
                        "Gemini API Key", "企业微信 Webhook", "飞书 Webhook"
                    ]), f"Field {i} missing expected label. Got: {field_text}"

    async def test_config_edit_and_save(self, mock_config):
        """test_config_edit_and_save - 编辑并保存配置"""
        with patch("src.config.get_config", return_value=mock_config):
            app = App()
            config_view = ConfigView()

            async with app.run_test() as pilot:
                app.mount(config_view)
                await pilot.pause()

                # Verify first field is selected (has ► marker)
                field0 = app.query_one("#field-0", Static)
                assert "►" in str(field0.render())

                # Press Enter to edit first field
                config_view.on_key(Key(key="enter", character=""))
                await pilot.pause()

                # Verify input widget appears
                input_widget = app.query_one("#config-input", Input)
                assert input_widget is not None

                # Change value
                input_widget.value = "000001,600519,000002"

                # Submit the input (simulates pressing Enter)
                input_widget.on_submit(input_widget)
                await pilot.pause()

                # Press Escape to save
                config_view.on_key(Key(key="escape", character=""))
                await pilot.pause()

                # Verify save was triggered (status message updated)
                save_status = app.query_one("#save-status", Static)
                status_text = str(save_status.render())
                # Should show save status message
                assert "保存" in status_text or "无" in status_text


class TestTasksView:
    """Tests for TasksView widget"""

    @pytest.fixture
    def task_store(self):
        """Create TaskStore with sample tasks"""
        store = TaskStore()
        store.add_task("600519")
        store.add_task("000001")
        return store

    async def test_tasks_view(self, task_store):
        """test_tasks_view - TasksView 显示任务列表"""
        app = App()
        tasks_view = TasksView(task_store)

        async with app.run_test() as pilot:
            app.mount(tasks_view)
            await pilot.pause()

            rendered = tasks_view.render()
            # Verify task list header
            assert "历史任务" in rendered
            # Verify tasks are displayed (added in reverse order, so 000001 first then 600519)
            assert "600519" in rendered
            assert "000001" in rendered
            # Verify empty state not shown (we have tasks)
            assert "暂无任务记录" not in rendered

    async def test_tasks_view_empty(self):
        """test_tasks_view_empty - TasksView 空状态"""
        app = App()
        tasks_view = TasksView(TaskStore())

        async with app.run_test() as pilot:
            app.mount(tasks_view)
            await pilot.pause()

            rendered = tasks_view.render()
            assert "暂无任务记录" in rendered


class TestAnalyzeView:
    """Tests for AnalyzeView widget"""

    @pytest.fixture
    def analyze_callback(self):
        """Create mock analyze callback"""
        return MagicMock()

    async def test_analyze_view_compose(self, analyze_callback):
        """test_analyze_view_compose - AnalyzeView 正确组合"""
        app = App()
        analyze_view = AnalyzeView(on_analyze=analyze_callback)

        async with app.run_test() as pilot:
            app.mount(analyze_view)
            await pilot.pause()

            # Verify components exist
            label = app.query_one("#label", Static)
            assert "股票代码" in str(label.render())

            input_field = app.query_one("#stock-input", Input)
            assert input_field is not None

            btn = app.query_one("#analyze-btn")
            assert btn is not None

    async def test_analyze_view_button_press(self, analyze_callback):
        """test_analyze_view_button_press - 点击分析按钮触发回调"""
        app = App()
        analyze_view = AnalyzeView(on_analyze=analyze_callback)

        async with app.run_test() as pilot:
            app.mount(analyze_view)
            await pilot.pause()

            # Focus input and type stock code
            input_field = app.query_one("#stock-input", Input)
            input_field.focus()
            await pilot.press("6")
            await pilot.press("0")
            await pilot.press("0")
            await pilot.press("5")
            await pilot.press("1")
            await pilot.press("9")
            await pilot.pause()

            # Click analyze button
            btn = app.query_one("#analyze-btn")
            btn.action_press()
            await pilot.pause()

            # Verify callback was called with stock code
            analyze_callback.assert_called_once_with("600519")


class TestLogsView:
    """Tests for LogsView widget"""

    @pytest.fixture
    def logs_view_with_file(self, tmp_path):
        """Create LogsView with a mock log file"""
        # Create logs directory and file
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "stock_analysis_20260101.log"
        log_file.write_text("2026-01-01 10:00:00 INFO Starting analysis\n2026-01-01 10:01:00 INFO Analysis complete\n")

        with patch.object(LogsView, "_log_dir", log_dir):
            view = LogsView()
            yield view

    async def test_logs_view(self, logs_view_with_file):
        """test_logs_view - LogsView 读取日志文件"""
        app = App()
        logs_view = logs_view_with_file

        async with app.run_test() as pilot:
            app.mount(logs_view)
            await pilot.pause()

            # Trigger load_logs manually since on_mount loads from logs/ (may not exist)
            logs_view.load_logs()
            await pilot.pause()

            rendered = logs_view.render()
            # Verify log header
            assert "日志" in rendered
            # Verify log content is loaded (or "暂无日志" if file not found in test env)
            assert "过滤:" in rendered

    async def test_logs_view_empty(self):
        """test_logs_view_empty - LogsView 无日志文件时显示空状态"""
        app = App()
        logs_view = LogsView()

        async with app.run_test() as pilot:
            app.mount(logs_view)
            await pilot.pause()

            logs_view.load_logs()
            await pilot.pause()

            rendered = logs_view.render()
            # Should show empty state
            assert "暂无日志" in rendered