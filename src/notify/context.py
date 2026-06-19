"""反向回复 context 提取 — DincTalk/飞书 Stream 模式将结果送回触发会话。

迁自 src/notification.py:
- _extract_dingtalk_session_webhook (L360)
- _extract_feishu_reply_info (L377)
- send_to_context / _send_via_source_context (L339/L2651)
- _send_feishu_stream_reply (L2685)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .types import BotMessage

logger = logging.getLogger(__name__)


def extract_dingtalk_session_webhook(source: Optional[BotMessage]) -> Optional[str]:
    """从 BotMessage 提取钉钉 Stream 模式会话 Webhook URL。"""
    if not isinstance(source, BotMessage):
        return None
    raw_data = getattr(source, "raw_data", {}) or {}
    if not isinstance(raw_data, dict):
        return None
    webhook = (
        raw_data.get("_session_webhook")
        or raw_data.get("sessionWebhook")
        or raw_data.get("session_webhook_url")
    )
    if not webhook and isinstance(raw_data.get("headers"), dict):
        webhook = raw_data["headers"].get("sessionWebhook")
    return webhook or None


def extract_feishu_reply_info(source: Optional[BotMessage]) -> Optional[Dict[str, str]]:
    """从 BotMessage 提取飞书回复信息（chat_id）。"""
    if not isinstance(source, BotMessage):
        return None
    if getattr(source, "platform", "") != "feishu":
        return None
    chat_id = getattr(source, "chat_id", "")
    if not chat_id:
        return None
    return {"chat_id": chat_id}


def has_context_channel(source: Optional[BotMessage]) -> bool:
    """是否存在基于消息上下文的临时渠道。"""
    return (
        extract_dingtalk_session_webhook(source) is not None
        or extract_feishu_reply_info(source) is not None
    )


def send_dingtalk_to_session(webhook_url: str, content: str) -> bool:
    """向钉钉会话 Webhook 发送内容（复用 CustomChannel DingTalk payload）。

    简化版：直接 POST markdown 消息；不走分块（context 回复预期较短）。
    """
    try:
        payload: Dict[str, Any] = {
            "msgtype": "markdown",
            "markdown": {"title": "股票分析报告", "text": content},
        }
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"钉钉会话推送异常: {e}")
        return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
    reraise=True,
)
def _post_feishu_with_retry(feishu_url: str, payload: Dict[str, Any]) -> None:
    response = requests.post(feishu_url, json=payload, timeout=30)
    if response.status_code != 200:
        raise requests.RequestException(f"HTTP {response.status_code}")
    result = response.json()
    code = result.get("code") if "code" in result else result.get("StatusCode")
    if code != 0:
        err_msg = result.get("msg") or result.get("StatusMessage", "未知错误")
        raise requests.RequestException(f"飞书回复错误: {err_msg}")


def send_feishu_reply(feishu_webhook_url: str, chat_id: str, content: str) -> bool:
    """向飞书会话回复内容（先卡片，失败回退 text）。"""
    try:
        # 优先 interactive 卡片
        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": "A股智能分析报告"}},
                "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}],
            },
        }
        try:
            _post_feishu_with_retry(feishu_webhook_url, card_payload)
            return True
        except requests.RequestException:
            logger.debug("飞书卡片回复失败，回退 text")

        text_payload = {
            "msg_type": "text",
            "content": {"text": content},
        }
        _post_feishu_with_retry(feishu_webhook_url, text_payload)
        return True

    except requests.RequestException as e:
        logger.error(f"飞书回复失败（已重试）: {e}")
        return False
    except Exception as e:
        logger.error(f"飞书回复异常: {e}")
        return False


def send_via_source_context(source: Optional[BotMessage], content: str, feishu_webhook_url: Optional[str] = None) -> bool:
    """根据 BotMessage 上下文自动选择渠道回复（钉钉/飞书 Stream 模式）。"""
    success = False

    # 钉钉
    dingtalk_hook = extract_dingtalk_session_webhook(source)
    if dingtalk_hook:
        if send_dingtalk_to_session(dingtalk_hook, content):
            logger.info("已通过钉钉会话（Stream）推送报告")
            success = True
        else:
            logger.error("钉钉会话（Stream）推送失败")

    # 飞书
    feishu_info = extract_feishu_reply_info(source)
    if feishu_info and feishu_webhook_url:
        chat_id = feishu_info["chat_id"]
        if send_feishu_reply(feishu_webhook_url, chat_id, content):
            logger.info("已通过飞书会话（Stream）推送报告")
            success = True
        else:
            logger.error("飞书会话（Stream）推送失败")

    return success
