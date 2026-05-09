"""邮件通知渠道"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ..base import BaseChannel, ChannelResult, ChannelPriority

logger = logging.getLogger(__name__)


class EmailChannel(BaseChannel):
    """邮件 SMTP 通知"""

    # SMTP 配置
    SMTP_CONFIGS = {
        "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
        "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
        "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
        "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    }

    def __init__(self, config: dict):
        super().__init__(config)
        self.sender = config.get("email_sender", "")
        self.password = config.get("email_password", "")
        self.receivers = config.get("email_receivers", [])

    def is_configured(self) -> bool:
        return bool(self.sender and self.password)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.MEDIUM

    def send(self, content: str, **kwargs) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="邮件未配置")

        try:
            # 获取邮件域
            domain = self.sender.split("@")[-1] if "@" in self.sender else ""
            smtp_config = self.SMTP_CONFIGS.get(domain, {"server": "smtp.gmail.com", "port": 587, "ssl": False})

            # 构建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = kwargs.get("subject", "股票分析通知")
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.receivers) if self.receivers else self.sender

            # 添加 HTML 内容
            html_part = MIMEText(content, "html", "utf-8")
            msg.attach(html_part)

            # 发送邮件
            timeout = 30  # 30 second timeout
            if smtp_config["ssl"]:
                # Port 465: SSL
                with smtplib.SMTP_SSL(smtp_config["server"], smtp_config["port"], timeout=timeout) as server:
                    server.login(self.sender, self.password)
                    server.sendmail(self.sender, self.receivers or [self.sender], msg.as_string())
            else:
                # Port 587: TLS
                with smtplib.SMTP(smtp_config["server"], smtp_config["port"], timeout=timeout) as server:
                    server.starttls()
                    server.login(self.sender, self.password)
                    server.sendmail(self.sender, self.receivers or [self.sender], msg.as_string())

            return ChannelResult(success=True, channel=self.name, message="邮件已发送")

        except smtplib.SMTPAuthError:
            logger.error("邮件认证失败")
            return ChannelResult(success=False, channel=self.name, error="邮件认证失败")
        except smtplib.SMTPConnectError:
            logger.error("邮件连接失败")
            return ChannelResult(success=False, channel=self.name, error="邮件连接失败")
        except Exception as e:
            logger.error(f"邮件发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))