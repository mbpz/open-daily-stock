# -*- coding: utf-8 -*-
"""WizardView TUI 组件测试

P5-4: Updated to handle new welcome screen (step -1) before 3-step wizard.
"""
import pytest
from unittest.mock import MagicMock

from textual.app import App
from textual.widgets import Static, Input
from textual.events import Key
from tui.widgets.wizard import WizardView


class WizardTestApp(App):
    """用于测试 WizardView 的测试应用"""

    def __init__(self, on_complete_callback=None, on_skip_callback=None):
        super().__init__()
        self._on_complete = on_complete_callback
        self._on_skip = on_skip_callback

    def compose(self):
        yield WizardView(
            on_complete_callback=self._on_complete,
            on_skip_callback=self._on_skip
        )


@pytest.fixture
def wizard_app():
    """创建 WizardView 测试应用"""
    return WizardTestApp()


@pytest.fixture
def wizard_app_with_callbacks():
    """创建带回调的 WizardView 测试应用"""
    on_complete = MagicMock()
    on_skip = MagicMock()
    app = WizardTestApp(on_complete_callback=on_complete, on_skip_callback=on_skip)
    app._on_complete = on_complete
    app._on_skip = on_skip
    return app


class TestWelcomeScreen:
    """P5-4: 欢迎页显示两个选项"""

    async def test_welcome_shows_two_options(self, wizard_app):
        """Welcome screen displays two options: 快速体验 and 开始配置."""
        async with wizard_app.run_test() as pilot:
            step_title = wizard_app.query_one("#welcome-step-title", Static)
            text = step_title.content
            assert "请选择" in text, f"期望 '请选择启动方式', 实际: {text}"

            field0 = wizard_app.query_one("#welcome-field-0", Static)
            field1 = wizard_app.query_one("#welcome-field-1", Static)
            assert "►" in field0.content, "第一个选项应该有选中标记"
            assert "快速体验" in field0.content
            assert "开始配置" in field1.content

    async def test_welcome_navigate_down(self, wizard_app):
        """按 ↓ 在欢迎页导航."""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")

            wizard.on_key(Key(key="down", character=""))
            await pilot.pause()

            field0 = wizard_app.query_one("#welcome-field-0", Static)
            field1 = wizard_app.query_one("#welcome-field-1", Static)
            assert " " in field0.content, "第一个选项不应再有选中标记"
            assert "►" in field1.content, "第二个选项应该有选中标记"

    async def test_welcome_select_demo_calls_complete(self, wizard_app_with_callbacks):
        """Selecting 快速体验 triggers on_complete callback (demo mode)."""
        app = wizard_app_with_callbacks

        async with app.run_test() as pilot:
            wizard = app.query_one("WizardView")

            # Select the first option (demo) by pressing enter
            wizard._selected_field_idx = 0  # "快速体验"
            wizard._select_welcome_option()
            await pilot.pause()

            assert app._on_complete.called, "选择演示模式应触发回调"

    async def test_welcome_select_config_advances_to_step1(self, wizard_app):
        """Selecting 开始配置 advances to step 1."""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")

            # Select the second option (config)
            wizard._selected_field_idx = 1  # "开始配置"
            wizard._select_welcome_option()
            await pilot.pause()

            # Should now show step 1
            step_title = wizard_app.query_one("#step-title", Static)
            text = step_title.content
            assert "步骤 1/3" in text, f"应进入步骤 1, 实际: {text}"


class TestWizardStep1Display:
    """步骤1显示正确（需先跳过欢迎页）"""

    async def test_wizard_step1_display(self, wizard_app):
        """验证步骤 1/3 显示正确的标题"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")
            # Advance past welcome screen to step 1
            wizard._current_step = 0
            wizard._selected_field_idx = 0
            wizard._clear_and_recompose()
            await pilot.pause()

            step_title = wizard_app.query_one("#step-title", Static)
            text = step_title.content

            assert "步骤 1/3" in text, f"期望 '步骤 1/3'，实际: {text}"
            assert "配置 API Key" in text, f"期望 '配置 API Key'，实际: {text}"

            field0 = wizard_app.query_one("#wizard-field-0", Static)
            field0_text = field0.content
            assert "OpenAI/MiniMax API Key" in field0_text
            assert "►" in field0_text, "第一个字段应该有选中标记 ►"


class TestWizardNavigateFields:
    """↑↓ 导航字段（需先跳过欢迎页）"""

    async def test_wizard_navigate_fields(self, wizard_app):
        """按 ↓ 键导航，验证选中字段变化"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")
            # Advance to step 1
            wizard._current_step = 0
            wizard._selected_field_idx = 0
            wizard._clear_and_recompose()
            await pilot.pause()

            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "►" in field0.content

            wizard.on_key(Key(key="down", character=""))
            await pilot.pause()

            field0_after = wizard_app.query_one("#wizard-field-0", Static)
            field1_after = wizard_app.query_one("#wizard-field-1", Static)

            assert " " in field0_after.content, "第一个字段不应再有选中标记"
            assert "►" in field1_after.content, "第二个字段应该有选中标记 ►"

    async def test_wizard_navigate_up(self, wizard_app):
        """按 ↑ 键向上导航"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")
            # Advance to step 1
            wizard._current_step = 0
            wizard._selected_field_idx = 0
            wizard._clear_and_recompose()
            await pilot.pause()

            wizard.on_key(Key(key="down", character=""))
            await pilot.pause()

            field1 = wizard_app.query_one("#wizard-field-1", Static)
            assert "►" in field1.content

            wizard.on_key(Key(key="up", character=""))
            await pilot.pause()

            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "►" in field0.content


class TestWizardEditField:
    """Enter 编辑字段（需先跳过欢迎页）"""

    async def test_wizard_edit_field(self, wizard_app):
        """按 Enter 编辑字段，输入值并提交"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")
            # Advance to step 1
            wizard._current_step = 0
            wizard._selected_field_idx = 0
            wizard._clear_and_recompose()
            await pilot.pause()

            wizard.on_key(Key(key="enter", character=""))
            await pilot.pause()

            input_widget = wizard_app.query_one("#wizard-input", Input)
            assert input_widget is not None

            input_widget.focus()
            await pilot.press("t")
            await pilot.press("e")
            await pilot.press("s")
            await pilot.press("t")
            await pilot.pause()

            assert input_widget.value == "test"

            field_key = wizard.WIZARD_STEPS[0]["fields"][0]["key"]
            wizard._field_values[field_key] = input_widget.value
            input_widget.remove()
            wizard._refresh_display()
            await pilot.pause()

            inputs = wizard_app.query("#wizard-input")
            assert len(inputs) == 0, "编辑完成后 Input 应该消失"

            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "test" in field0.content


class TestWizardSkip:
    """跳过引导（需先跳过欢迎页）"""

    async def test_wizard_skip(self, wizard_app_with_callbacks):
        """验证步骤 3 按 Esc 跳过引导"""
        app = wizard_app_with_callbacks

        async with app.run_test() as pilot:
            wizard = app.query_one("WizardView")

            # Advance to step 1 and verify Esc doesn't skip
            wizard._current_step = 0
            wizard._selected_field_idx = 0
            wizard._clear_and_recompose()
            await pilot.pause()

            wizard.on_key(Key(key="escape", character=""))
            await pilot.pause()
            assert not app._on_skip.called, "步骤 1 按 Esc 不应触发跳过"

            # 直接设置步骤为 3（skippable）
            wizard._current_step = 2  # 0-indexed, so step 3 is index 2
            wizard._selected_field_idx = 0

            step = wizard.WIZARD_STEPS[2]
            assert step.get("skippable") is True, "步骤 3 应该是可跳过的"

            app._on_skip.reset_mock()
            wizard.on_key(Key(key="escape", character=""))
            await pilot.pause()
            assert app._on_skip.called, "步骤 3 按 Esc 应该触发跳过"
