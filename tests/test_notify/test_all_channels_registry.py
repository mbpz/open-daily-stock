"""ALL_CHANNELS 注册表 + plugin_manager 集成测试。"""
import pytest

from src.notify.channels import ALL_CHANNELS
from src.notify.base import BaseChannel


class TestAllChannelsRegistry:
    def test_all_nine_channels_present(self):
        expected = {
            "wechat",
            "feishu",
            "telegram",
            "email",
            "discord",
            "custom",
            "pushover",
            "pushplus",
            "windows",
        }
        assert set(ALL_CHANNELS.keys()) == expected

    def test_all_classes_inherit_base_channel(self):
        for name, cls in ALL_CHANNELS.items():
            assert issubclass(cls, BaseChannel), f"{name} ({cls}) 不是 BaseChannel 子类"

    def test_all_constructible_with_empty_config(self):
        # plugin_manager 用 `cls({})` 实例化以便枚举类型。
        # 任何 channel 在空 config 下都不应抛异常。
        for name, cls in ALL_CHANNELS.items():
            try:
                instance = cls({})
            except Exception as e:
                pytest.fail(f"{name} ({cls.__name__}) 用空 config 实例化失败: {e}")
            assert isinstance(instance, BaseChannel)

    def test_all_unconfigured_with_empty_config(self):
        # 空 config → 所有 channel 都应 is_configured()=False（不会误以为已配置）
        for name, cls in ALL_CHANNELS.items():
            instance = cls({})
            assert instance.is_configured() is False, f"{name} 空配置不该报已配置"


class TestPluginManagerIntegration:
    def test_plugin_manager_registers_notifiers_without_error(self):
        """关键的 plugin_manager.py:238 集成验证。

        历史问题：plugin_manager 调 `cls()` 不传 config 导致所有 channel 实例化失败、
        被 try/except 吞掉。修复后：传空 config，调用应静默成功并注册全部 9 个 channel。
        """
        from src.plugin_manager import PluginManager

        pm = PluginManager()
        # 内部已调用 _discover_notifiers
        notify_plugins = pm.list_plugins(domain="notify")
        # 应至少能注册 9 个渠道（全部空 config 可构造）
        assert len(notify_plugins) >= 9
        # 名字应覆盖 ALL_CHANNELS 全部 key
        plugin_names = {p.name for p in notify_plugins}
        for name in ALL_CHANNELS.keys():
            assert name in plugin_names, f"{name} 未注册"
