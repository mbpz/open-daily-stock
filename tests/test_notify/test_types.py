"""src/notify/types 单元测试。"""
import pytest

from src.notify.types import (
    BotMessage,
    ChannelDetector,
    NotificationChannel,
    channel_from_key,
    channel_to_key,
)


# ─── BotMessage ────────────────────────────────────────────────


class TestBotMessage:
    def test_default_construction(self):
        msg = BotMessage()
        assert msg.content == ""
        assert msg.html_content == ""
        assert msg.image_paths == []
        assert msg.mention_list == []

    def test_field_default_factory_avoids_shared_state(self):
        a = BotMessage()
        b = BotMessage()
        a.image_paths.append("x")
        # 不应共享同一 list 实例
        assert b.image_paths == []

    def test_with_values(self):
        msg = BotMessage(
            content="hi",
            html_content="<p>hi</p>",
            image_paths=["/a.png"],
            mention_list=["@u"],
        )
        assert msg.content == "hi"
        assert msg.html_content == "<p>hi</p>"
        assert msg.image_paths == ["/a.png"]
        assert msg.mention_list == ["@u"]


# ─── NotificationChannel Enum ─────────────────────────────────


class TestNotificationChannelEnum:
    def test_all_ten_members(self):
        # 数量与旧 src/notification.py 严格一致
        assert len(NotificationChannel) == 10

    def test_string_values(self):
        assert NotificationChannel.WECHAT.value == "wechat"
        assert NotificationChannel.FEISHU.value == "feishu"
        assert NotificationChannel.TELEGRAM.value == "telegram"
        assert NotificationChannel.EMAIL.value == "email"
        assert NotificationChannel.PUSHOVER.value == "pushover"
        assert NotificationChannel.PUSHPLUS.value == "pushplus"
        assert NotificationChannel.CUSTOM.value == "custom"
        assert NotificationChannel.DISCORD.value == "discord"
        assert NotificationChannel.WINDOWS.value == "windows"
        assert NotificationChannel.UNKNOWN.value == "unknown"

    def test_can_be_used_as_dict_key(self):
        # pipeline.py 行为：channels list 内做 in 比较
        channels = [NotificationChannel.WECHAT, NotificationChannel.FEISHU]
        assert NotificationChannel.WECHAT in channels
        assert NotificationChannel.PUSHOVER not in channels


# ─── ChannelDetector ──────────────────────────────────────────


class TestChannelDetector:
    def test_chinese_names_mapped(self):
        assert ChannelDetector.get_channel_name(NotificationChannel.WECHAT) == "企业微信"
        assert ChannelDetector.get_channel_name(NotificationChannel.FEISHU) == "飞书"
        assert ChannelDetector.get_channel_name(NotificationChannel.TELEGRAM) == "Telegram"
        assert ChannelDetector.get_channel_name(NotificationChannel.EMAIL) == "邮件"
        assert ChannelDetector.get_channel_name(NotificationChannel.PUSHOVER) == "Pushover"
        assert ChannelDetector.get_channel_name(NotificationChannel.PUSHPLUS) == "PushPlus"
        assert ChannelDetector.get_channel_name(NotificationChannel.CUSTOM) == "自定义Webhook"
        assert ChannelDetector.get_channel_name(NotificationChannel.DISCORD) == "Discord机器人"
        assert ChannelDetector.get_channel_name(NotificationChannel.WINDOWS) == "Windows通知"
        assert ChannelDetector.get_channel_name(NotificationChannel.UNKNOWN) == "未知渠道"


# ─── key ↔ Enum 转换 ──────────────────────────────────────────


class TestKeyEnumConversion:
    def test_channel_from_key_known(self):
        assert channel_from_key("wechat") == NotificationChannel.WECHAT
        assert channel_from_key("feishu") == NotificationChannel.FEISHU

    def test_channel_from_key_case_insensitive(self):
        assert channel_from_key("WECHAT") == NotificationChannel.WECHAT
        assert channel_from_key("Wechat") == NotificationChannel.WECHAT

    def test_channel_from_key_unknown(self):
        assert channel_from_key("nonexistent") is None
        assert channel_from_key("") is None
        assert channel_from_key(None) is None

    def test_channel_to_key(self):
        assert channel_to_key(NotificationChannel.WECHAT) == "wechat"
        assert channel_to_key(NotificationChannel.FEISHU) == "feishu"

    def test_round_trip_all_channels(self):
        # 每个 channel 都能 enum → key → enum 往返
        for ch in NotificationChannel:
            if ch == NotificationChannel.UNKNOWN:
                continue  # UNKNOWN 不在 _CHANNEL_KEY_TO_ENUM 里（合理）
            key = channel_to_key(ch)
            back = channel_from_key(key)
            assert back == ch


# ─── ALL_CHANNELS 与 Enum 对应 ────────────────────────────────


class TestAllChannelsAlignWithEnum:
    def test_each_all_channels_key_has_enum(self):
        from src.notify.channels import ALL_CHANNELS

        for key in ALL_CHANNELS.keys():
            assert channel_from_key(key) is not None, f"ALL_CHANNELS key '{key}' 在 Enum 中无对应"
