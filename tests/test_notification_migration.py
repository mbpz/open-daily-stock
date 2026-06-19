"""P0-2 迁移完成验证 — src.notification.py 已删除。

验证：
  1. 所有类型/服务从 src.notify 可导入
  2. src.notify 不依赖已删除的 src.notification
  3. NotificationChannel / BotMessage 向后兼容旧契约
"""
import sys
import warnings

import pytest


def test_notification_service_from_notify():
    """NotificationService 现在从 src.notify 导入。"""
    from src.notify import NotificationService


def test_types_from_notify():
    """类型在 src.notify 下直接可用。"""
    from src.notify import NotificationChannel, BotMessage
    assert NotificationChannel.WECHAT.value == "wechat"
    msg = BotMessage(content="hello")
    assert msg.content == "hello"
    assert msg.image_paths == []


def test_src_notify_does_not_depend_on_legacy_module():
    """src.notify 不依赖已删除的 src.notification。"""
    assert "src.notification" not in sys.modules
    # 重新导入也应成功
    if "src.notify" in sys.modules:
        del sys.modules["src.notify"]
    from src.notify import (
        NotificationChannel, BotMessage, NotificationDispatcher,
        BaseChannel, ChannelResult, ChannelPriority,
        MarkdownFormatter, SimpleFormatter, DashboardFormatter,
        NotificationService,
    )


def test_bot_message_dataclass_compatible():
    """BotMessage 保持旧契约。"""
    from src.notify import BotMessage
    m = BotMessage("hello")
    assert m.content == "hello"
    m2 = BotMessage(content="c", html_content="<p>c</p>",
                    image_paths=["/a.png"], mention_list=["@user"])
    assert m2.image_paths == ["/a.png"]
    assert m2.mention_list == ["@user"]


def test_legacy_module_is_gone():
    """确认 src.notification 模块已不存在。"""
    # 清除可能来自同一进程缓存的残留
    sys.modules.pop("src.notification", None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ModuleNotFoundError):
            __import__("src.notification")
