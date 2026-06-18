"""WindowsToastChannel 单元测试。

注意：CI 跑在 macOS/Linux，平台门控会自动让 is_configured() 返回 False。
平台无关的测试（unconfigured 路径、构造）总是能跑；平台相关的测试用 monkeypatch
模拟 _win10toast_available + _ToastNotifier。
"""
from unittest.mock import MagicMock

import pytest

from src.notify.channels import windows as windows_mod
from src.notify.channels.windows import WindowsToastChannel


# ─── 平台无关 ──────────────────────────────────────────────────


class TestPlatformGated:
    def test_unconfigured_on_non_windows_returns_failure(self, monkeypatch):
        monkeypatch.setattr(windows_mod, "_win10toast_available", False)
        ch = WindowsToastChannel({})
        assert ch.is_configured() is False

        result = ch.send("hi")
        assert result.success is False
        assert "不可用" in result.error
        assert result.channel == "WindowsToastChannel"

    def test_send_does_not_raise_on_non_windows(self, monkeypatch):
        monkeypatch.setattr(windows_mod, "_win10toast_available", False)
        ch = WindowsToastChannel({})
        # 重要：即便平台不支持，也不应抛异常
        result = ch.send("any content")
        assert isinstance(result.success, bool)


# ─── 模拟 Windows ──────────────────────────────────────────────


@pytest.fixture
def mock_windows(monkeypatch):
    """模拟 Windows 平台 + win10toast 已安装。"""
    monkeypatch.setattr(windows_mod, "_win10toast_available", True)
    fake_toaster_class = MagicMock()
    fake_toaster_instance = MagicMock()
    fake_toaster_class.return_value = fake_toaster_instance
    monkeypatch.setattr(windows_mod, "_ToastNotifier", fake_toaster_class)
    return fake_toaster_class, fake_toaster_instance


class TestSendOnWindows:
    def test_short_content_passes_through(self, mock_windows):
        _, instance = mock_windows
        ch = WindowsToastChannel({})
        result = ch.send("简短消息")

        assert result.success is True
        assert result.channel == "WindowsToastChannel"
        instance.show_toast.assert_called_once()
        kwargs = instance.show_toast.call_args.kwargs
        assert kwargs["msg"] == "简短消息"
        assert "股票分析报告" in kwargs["title"]
        assert kwargs["duration"] == 5
        assert kwargs["threaded"] is False

    def test_long_content_is_truncated(self, mock_windows):
        _, instance = mock_windows
        ch = WindowsToastChannel({})
        long_content = "x" * 500
        result = ch.send(long_content)

        assert result.success is True
        msg = instance.show_toast.call_args.kwargs["msg"]
        assert msg.endswith("...")
        assert len(msg) == 200 + 3  # 200 字符 + "..."

    def test_custom_title_and_duration(self, mock_windows):
        _, instance = mock_windows
        ch = WindowsToastChannel({})
        ch.send("hi", title="紧急提醒", duration=10)

        kwargs = instance.show_toast.call_args.kwargs
        assert kwargs["title"] == "紧急提醒"
        assert kwargs["duration"] == 10

    def test_show_toast_exception_returns_failure(self, mock_windows):
        toaster_class, instance = mock_windows
        instance.show_toast.side_effect = RuntimeError("toast failed")
        ch = WindowsToastChannel({})
        result = ch.send("hi")

        assert result.success is False
        assert "toast failed" in result.error
