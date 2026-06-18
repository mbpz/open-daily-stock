"""通知分块工具 — channel 共享的字节级 utility。

抽自 src/notification.py:_truncate_to_bytes 等纯函数；wechat / feishu 等需要按
字节限制分批发送的 channel 共用这些 helper。

不放置 channel 特化的智能分块逻辑（如 wechat 的 4 级 separator fallback、feishu 的
表格转换）— 那些保留在各 channel 文件里，因为其语义因平台而异。
"""
from __future__ import annotations


def get_bytes(s: str) -> int:
    """返回字符串的 UTF-8 字节数。"""
    return len(s.encode("utf-8"))


def truncate_to_bytes(text: str, max_bytes: int) -> str:
    """按字节数截断字符串，确保不会在多字节字符中间截断。

    迁自 src/notification.py:_truncate_to_bytes。

    Args:
        text: 要截断的字符串
        max_bytes: 最大字节数

    Returns:
        截断后的字符串。原长度 ≤ max_bytes 时原样返回；否则向前查找有效解码边界。
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""
