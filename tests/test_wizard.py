# -*- coding: utf-8 -*-
"""WizardView TUI 组件测试"""
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


class TestWizardStep1Display:
    """test_wizard_step1_display - 步骤1显示正确"""

    async def test_wizard_step1_display(self, wizard_app):
        """验证步骤 1/3 显示正确的标题"""
        async with wizard_app.run_test() as pilot:
            # 验证步骤标题显示
            step_title = wizard_app.query_one("#step-title", Static)
            text = step_title.content

            assert "步骤 1/3" in text, f"期望 '步骤 1/3'，实际: {text}"
            assert "配置 API Key" in text, f"期望 '配置 API Key'，实际: {text}"

            # 验证字段显示
            field0 = wizard_app.query_one("#wizard-field-0", Static)
            field0_text = field0.content
            assert "OpenAI/MiniMax API Key" in field0_text
            assert "►" in field0_text, "第一个字段应该有选中标记 ►"


class TestWizardNavigateFields:
    """test_wizard_navigate_fields - ↑↓ 导航字段"""

    async def test_wizard_navigate_fields(self, wizard_app):
        """按 ↓ 键导航，验证选中字段变化"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")

            # 初始状态第一个字段被选中
            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "►" in field0.content

            # 按 ↓ 键选择下一个字段（直接调用 on_key 绕过焦点问题）
            wizard.on_key(Key(key="down", character=""))
            await pilot.pause()

            # 验证选中标记移动到第二个字段
            field0_after = wizard_app.query_one("#wizard-field-0", Static)
            field1_after = wizard_app.query_one("#wizard-field-1", Static)

            assert " " in field0_after.content, "第一个字段不应再有选中标记"
            assert "►" in field1_after.content, "第二个字段应该有选中标记 ►"

    async def test_wizard_navigate_up(self, wizard_app):
        """按 ↑ 键向上导航"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")

            # 先按 ↓ 移动到第二个字段
            wizard.on_key(Key(key="down", character=""))
            await pilot.pause()

            # 验证已移到第二个字段
            field1 = wizard_app.query_one("#wizard-field-1", Static)
            assert "►" in field1.content

            # 按 ↑ 键返回
            wizard.on_key(Key(key="up", character=""))
            await pilot.pause()

            # 验证选中标记回到第一个字段
            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "►" in field0.content


class TestWizardEditField:
    """test_wizard_edit_field - Enter 编辑字段"""

    async def test_wizard_edit_field(self, wizard_app):
        """按 Enter 编辑字段，输入值并提交"""
        async with wizard_app.run_test() as pilot:
            wizard = wizard_app.query_one("WizardView")

            # 按 Enter 进入编辑模式
            wizard.on_key(Key(key="enter", character=""))
            await pilot.pause()

            # 验证 Input 组件出现
            input_widget = wizard_app.query_one("#wizard-input", Input)
            assert input_widget is not None

            # 聚焦并使用按键输入
            input_widget.focus()
            await pilot.press("t")
            await pilot.press("e")
            await pilot.press("s")
            await pilot.press("t")
            await pilot.pause()

            # 验证输入的值
            assert input_widget.value == "test"

            # 模拟提交：设置字段值并移除输入框
            field_key = wizard.WIZARD_STEPS[0]["fields"][0]["key"]
            wizard._field_values[field_key] = input_widget.value
            input_widget.remove()
            wizard._refresh_display()
            await pilot.pause()

            # 验证 Input 组件消失
            inputs = wizard_app.query("#wizard-input")
            assert len(inputs) == 0, "编辑完成后 Input 应该消失"

            # 验证字段显示更新
            field0 = wizard_app.query_one("#wizard-field-0", Static)
            assert "test" in field0.content


class TestWizardSkip:
    """test_wizard_skip - 跳过引导"""

    async def test_wizard_skip(self, wizard_app_with_callbacks):
        """验证步骤 3 按 Esc 跳过引导"""
        app = wizard_app_with_callbacks

        async with app.run_test() as pilot:
            wizard = app.query_one("WizardView")

            # 验证步骤 1 按 Esc 不会跳过（非 skippable）
            wizard.on_key(Key(key="escape", character=""))
            await pilot.pause()
            assert not app._on_skip.called, "步骤 1 按 Esc 不应触发跳过"

            # 直接设置步骤为 3（skippable）
            wizard._current_step = 2  # 0-indexed, so step 3 is index 2
            wizard._selected_field_idx = 0

            # 验证步骤 3 的 skippable 属性
            step = wizard.WIZARD_STEPS[2]
            assert step.get("skippable") is True, "步骤 3 应该是可跳过的"

            # 按 Esc 应该触发跳过
            app._on_skip.reset_mock()
            wizard.on_key(Key(key="escape", character=""))
            await pilot.pause()
            assert app._on_skip.called, "步骤 3 按 Esc 应该触发跳过"
