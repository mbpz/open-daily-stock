"""PushPlus 推送通知渠道（国内推送服务，支持微信公众号）"""
import logging
from datetime import datetime

import requests

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# PushPlus API 端点
_API_URL = "http://www.pushplus.plus/send"


class PushPlusChannel(BaseChannel):
    """PushPlus 推送（国内服务，支持微信公众号）。

    迁自 src/notification.py:send_to_pushplus。

    特点：
    - 国内推送，免费额度充足
    - 支持 markdown / html / txt / json 多种 template
    - 默认使用 markdown template
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.token = config.get("pushplus_token")

    def is_configured(self) -> bool:
        return bool(self.token)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.MEDIUM

    def send(self, content: str, **kwargs) -> ChannelResult:
        """发送 PushPlus 消息。

        kwargs:
            title: 自定义标题，默认 "📈 股票分析报告 - YYYY-MM-DD"
            template: 消息模板（markdown / html / txt / json），默认 "markdown"
        """
        if not self.is_configured():
            return ChannelResult(
                success=False, channel=self.name, error="PushPlus Token 未配置"
            )

        title = kwargs.get("title")
        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 股票分析报告 - {date_str}"

        template = kwargs.get("template", "markdown")

        try:
            payload = {
                "token": self.token,
                "title": title,
                "content": content,
                "template": template,
            }
            response = requests.post(_API_URL, json=payload, timeout=10)

            if response.status_code != 200:
                err = f"HTTP {response.status_code}"
                logger.error(f"PushPlus 请求失败: {err}")
                return ChannelResult(success=False, channel=self.name, error=err)

            result = response.json()
            if result.get("code") == 200:
                return ChannelResult(success=True, channel=self.name, message="PushPlus 已发送")

            err_msg = result.get("msg", "未知错误")
            logger.error(f"PushPlus 返回错误: {err_msg}")
            return ChannelResult(success=False, channel=self.name, error=err_msg)

        except requests.exceptions.Timeout:
            logger.error("PushPlus 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"PushPlus 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
