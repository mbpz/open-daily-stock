"""邮件 SMTP 通知渠道。

迁自 src/notification.py:send_to_email / _markdown_to_html / SMTP_CONFIGS。

核心特性：
- **完整 SMTP_CONFIGS**（11 个国内外域）：qq/foxmail/163/126/gmail/outlook/
  hotmail/live/sina/sohu/aliyun/139；未知域 fallback 到 smtp.<domain>:465 SSL
- **Markdown → HTML** 完整 4 个 extras：tables/fenced-code-blocks/
  break-on-newline/cuddled-lists；包装 GitHub 风 CSS 样式（h1/h2/h3、表格、引用、
  代码块、列表、hr）
- multipart/alternative 同时附 plain + html（plain 兼容性，html 渲染优先）
- SMTPAuthenticationError / SMTPConnectError 友好错误信息
- 默认主题 `📈 股票智能分析报告 - YYYY-MM-DD`
- timeout 30s
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

from ..base import BaseChannel, ChannelPriority, ChannelResult

try:
    import markdown2

    _MARKDOWN_AVAILABLE = True
except ImportError:
    _MARKDOWN_AVAILABLE = False

logger = logging.getLogger(__name__)


# 完整 SMTP 服务器配置（迁自旧 SMTP_CONFIGS，11 项）
SMTP_CONFIGS: Dict[str, Dict] = {
    # QQ
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    # 网易
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    # Gmail
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    # Outlook 系
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    # 新浪
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    # 搜狐
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    # 阿里云
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    # 139 邮箱
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}

_DEFAULT_TIMEOUT = 30

# 邮件 HTML 样式（GitHub 风格，迁自旧 _markdown_to_html）
_EMAIL_CSS = """
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                line-height: 1.5;
                color: #24292e;
                font-size: 14px;
                padding: 15px;
                max-width: 900px;
                margin: 0 auto;
            }
            h1 {
                font-size: 20px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.2em;
                margin-bottom: 0.8em;
                color: #0366d6;
            }
            h2 {
                font-size: 18px;
                border-bottom: 1px solid #eaecef;
                padding-bottom: 0.3em;
                margin-top: 1.0em;
                margin-bottom: 0.6em;
            }
            h3 {
                font-size: 16px;
                margin-top: 0.8em;
                margin-bottom: 0.4em;
            }
            p {
                margin-top: 0;
                margin-bottom: 8px;
            }
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 12px 0;
                display: block;
                overflow-x: auto;
                font-size: 13px;
            }
            th, td {
                border: 1px solid #dfe2e5;
                padding: 6px 10px;
                text-align: left;
            }
            th {
                background-color: #f6f8fa;
                font-weight: 600;
            }
            tr:nth-child(2n) {
                background-color: #f8f8f8;
            }
            tr:hover {
                background-color: #f1f8ff;
            }
            blockquote {
                color: #6a737d;
                border-left: 0.25em solid #dfe2e5;
                padding: 0 1em;
                margin: 0 0 10px 0;
            }
            code {
                padding: 0.2em 0.4em;
                margin: 0;
                font-size: 85%;
                background-color: rgba(27,31,35,0.05);
                border-radius: 3px;
                font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
            }
            pre {
                padding: 12px;
                overflow: auto;
                line-height: 1.45;
                background-color: #f6f8fa;
                border-radius: 3px;
                margin-bottom: 10px;
            }
            hr {
                height: 0.25em;
                padding: 0;
                margin: 16px 0;
                background-color: #e1e4e8;
                border: 0;
            }
            ul, ol {
                padding-left: 20px;
                margin-bottom: 10px;
            }
            li {
                margin: 2px 0;
            }
"""


def _markdown_to_html(markdown_text: str) -> str:
    """将 Markdown 转换为 GitHub 风 HTML 邮件正文。

    - markdown2 转换开启 4 个 extras：tables / fenced-code-blocks /
      break-on-newline / cuddled-lists
    - 包装完整 HTML 文档（含 CSS）
    - markdown2 不可用时降级：换行替换为 `<br>`
    """
    if _MARKDOWN_AVAILABLE:
        body = markdown2.markdown(
            markdown_text,
            extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
        )
    else:
        body = markdown_text.replace("\n", "<br>")

    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                {_EMAIL_CSS}
            </style>
        </head>
        <body>
            {body}
        </body>
        </html>
        """


def _resolve_smtp_config(sender: str) -> Dict:
    """根据发件邮箱域名解析 SMTP 配置；未知域 fallback 到 smtp.<domain>:465 SSL。"""
    domain = sender.split("@")[-1].lower() if "@" in sender else ""
    cfg = SMTP_CONFIGS.get(domain)
    if cfg:
        return {"server": cfg["server"], "port": cfg["port"], "ssl": cfg["ssl"], "domain": domain}
    return {
        "server": f"smtp.{domain}" if domain else "smtp.unknown",
        "port": 465,
        "ssl": True,
        "domain": domain,
        "fallback": True,
    }


class EmailChannel(BaseChannel):
    """邮件 SMTP 通知（自动识别 11 项国内外服务商）。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.sender = config.get("email_sender", "") or ""
        self.password = config.get("email_password", "") or ""
        receivers = config.get("email_receivers", [])
        # 兼容空列表 / None / 字符串
        if not receivers:
            self.receivers = [self.sender] if self.sender else []
        elif isinstance(receivers, str):
            self.receivers = [receivers]
        else:
            self.receivers = list(receivers)

    def is_configured(self) -> bool:
        return bool(self.sender and self.password)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.MEDIUM

    def send(self, content: str, **kwargs) -> ChannelResult:
        """通过 SMTP 发送 multipart/alternative 邮件。

        kwargs:
            subject: 自定义主题，默认 "📈 股票智能分析报告 - YYYY-MM-DD"
        """
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="邮件未配置")

        subject = kwargs.get("subject")
        if subject is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            subject = f"📈 股票智能分析报告 - {date_str}"

        try:
            html_content = _markdown_to_html(content)

            # 构建 multipart/alternative：plain 文本兼容 + HTML 渲染
            msg = MIMEMultipart("alternative")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.receivers)
            msg.attach(MIMEText(content, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            smtp_cfg = _resolve_smtp_config(self.sender)
            if smtp_cfg.get("fallback"):
                logger.warning(
                    f"未知邮箱类型 {smtp_cfg['domain']}，尝试通用配置 "
                    f"{smtp_cfg['server']}:{smtp_cfg['port']}"
                )
            else:
                logger.info(
                    f"自动识别邮箱: {smtp_cfg['domain']} → "
                    f"{smtp_cfg['server']}:{smtp_cfg['port']}"
                )

            if smtp_cfg["ssl"]:
                with smtplib.SMTP_SSL(
                    smtp_cfg["server"], smtp_cfg["port"], timeout=_DEFAULT_TIMEOUT
                ) as server:
                    server.login(self.sender, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(
                    smtp_cfg["server"], smtp_cfg["port"], timeout=_DEFAULT_TIMEOUT
                ) as server:
                    server.starttls()
                    server.login(self.sender, self.password)
                    server.send_message(msg)

            logger.info(f"邮件发送成功，收件人: {self.receivers}")
            return ChannelResult(success=True, channel=self.name, message="邮件已发送")

        except smtplib.SMTPAuthenticationError:
            logger.error("邮件认证错误，请检查邮箱和授权码")
            return ChannelResult(
                success=False, channel=self.name, error="邮件认证错误（检查邮箱与授权码）"
            )
        except smtplib.SMTPConnectError as e:
            logger.error(f"邮件连接失败: {e}")
            return ChannelResult(
                success=False, channel=self.name, error=f"无法连接 SMTP 服务器: {e}"
            )
        except Exception as e:
            logger.error(f"邮件发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
