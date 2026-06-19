"""EmailChannel 单元测试（增强后）。"""
from unittest.mock import MagicMock, patch

import pytest

from src.notify.channels.email import (
    EmailChannel,
    SMTP_CONFIGS,
    _markdown_to_html,
    _resolve_smtp_config,
)


# ─── SMTP_CONFIGS 完整性 ────────────────────────────────────────


class TestSmtpConfigs:
    def test_chinese_domains_present(self):
        for d in ["qq.com", "163.com", "126.com", "sina.com", "sohu.com", "139.com", "aliyun.com", "foxmail.com"]:
            assert d in SMTP_CONFIGS

    def test_international_domains_present(self):
        for d in ["gmail.com", "outlook.com", "hotmail.com", "live.com"]:
            assert d in SMTP_CONFIGS

    def test_qq_uses_465_ssl(self):
        cfg = SMTP_CONFIGS["qq.com"]
        assert cfg["server"] == "smtp.qq.com"
        assert cfg["port"] == 465
        assert cfg["ssl"] is True

    def test_gmail_uses_587_tls(self):
        cfg = SMTP_CONFIGS["gmail.com"]
        assert cfg["port"] == 587
        assert cfg["ssl"] is False

    def test_count_at_least_eleven(self):
        # 旧实现是 11 项，避免回退
        assert len(SMTP_CONFIGS) >= 11


# ─── _resolve_smtp_config ──────────────────────────────────────


class TestResolveSmtpConfig:
    def test_known_domain(self):
        cfg = _resolve_smtp_config("user@163.com")
        assert cfg["server"] == "smtp.163.com"
        assert cfg["domain"] == "163.com"
        assert "fallback" not in cfg

    def test_unknown_domain_fallback(self):
        cfg = _resolve_smtp_config("user@example.org")
        assert cfg["server"] == "smtp.example.org"
        assert cfg["port"] == 465
        assert cfg["ssl"] is True
        assert cfg.get("fallback") is True

    def test_no_at_sign(self):
        cfg = _resolve_smtp_config("not-an-email")
        # 边界：domain 解析失败也不抛异常
        assert "server" in cfg

    def test_case_insensitive(self):
        cfg = _resolve_smtp_config("user@GMAIL.COM")
        # 旧实现 .lower() — 域名应被识别
        assert cfg["server"] == "smtp.gmail.com"


# ─── _markdown_to_html ─────────────────────────────────────────


class TestMarkdownToHtml:
    def test_extras_enabled(self):
        # 表格 / 代码块 / break-on-newline / cuddled-lists 4 个 extras
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        html = _markdown_to_html(md)
        assert "<table>" in html
        assert "<th>a</th>" in html or "<th>a</th>" in html.lower()

    def test_includes_doctype_and_style(self):
        html = _markdown_to_html("hello")
        assert "<!DOCTYPE html>" in html
        assert "<style>" in html
        # 关键 CSS 选择器
        assert "h1 {" in html
        assert "table {" in html
        assert "blockquote {" in html

    def test_break_on_newline(self):
        # break-on-newline extras 让单换行也变 <br>
        html = _markdown_to_html("行A\n行B")
        assert "<br" in html or "<br/>" in html or "<br />" in html


# ─── 构造 / is_configured ──────────────────────────────────────


class TestConstruction:
    def test_empty_receivers_falls_back_to_sender(self):
        ch = EmailChannel({"email_sender": "u@qq.com", "email_password": "p"})
        assert ch.receivers == ["u@qq.com"]

    def test_string_receiver_wrapped_to_list(self):
        ch = EmailChannel({"email_sender": "s@qq.com", "email_password": "p", "email_receivers": "r@qq.com"})
        assert ch.receivers == ["r@qq.com"]

    def test_list_receivers_kept(self):
        ch = EmailChannel(
            {"email_sender": "s@qq.com", "email_password": "p", "email_receivers": ["a@x.com", "b@x.com"]}
        )
        assert ch.receivers == ["a@x.com", "b@x.com"]

    def test_is_configured(self):
        assert EmailChannel({}).is_configured() is False
        assert EmailChannel({"email_sender": "s@qq.com"}).is_configured() is False
        assert EmailChannel({"email_password": "p"}).is_configured() is False
        assert EmailChannel({"email_sender": "s@qq.com", "email_password": "p"}).is_configured() is True


# ─── send 行为 ──────────────────────────────────────────────────


@pytest.fixture
def configured_qq():
    return EmailChannel(
        {"email_sender": "user@qq.com", "email_password": "pwd", "email_receivers": ["a@x.com"]}
    )


@pytest.fixture
def configured_gmail():
    return EmailChannel(
        {"email_sender": "user@gmail.com", "email_password": "pwd", "email_receivers": ["a@x.com"]}
    )


class TestSendSsl:
    def test_qq_uses_smtp_ssl(self, configured_qq):
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl, patch(
            "src.notify.channels.email.smtplib.SMTP"
        ) as mock_plain:
            r = configured_qq.send("正文")
        assert r.success is True
        mock_ssl.assert_called_once()
        mock_plain.assert_not_called()
        # 服务器/端口
        args = mock_ssl.call_args.args
        assert args[0] == "smtp.qq.com"
        assert args[1] == 465

    def test_gmail_uses_smtp_with_starttls(self, configured_gmail):
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl, patch(
            "src.notify.channels.email.smtplib.SMTP"
        ) as mock_plain:
            mock_server = mock_plain.return_value.__enter__.return_value
            r = configured_gmail.send("hi")
        assert r.success is True
        mock_plain.assert_called_once()
        mock_ssl.assert_not_called()
        args = mock_plain.call_args.args
        assert args[0] == "smtp.gmail.com"
        assert args[1] == 587
        mock_server.starttls.assert_called_once()


class TestSendPayload:
    def test_subject_default_includes_date(self, configured_qq):
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = mock_ssl.return_value.__enter__.return_value
            configured_qq.send("hi")
        msg = mock_server.send_message.call_args.args[0]
        assert "股票智能分析报告" in str(msg["Subject"])

    def test_custom_subject_via_kwargs(self, configured_qq):
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = mock_ssl.return_value.__enter__.return_value
            configured_qq.send("hi", subject="紧急通知")
        msg = mock_server.send_message.call_args.args[0]
        assert "紧急通知" in str(msg["Subject"])

    def test_multipart_alternative_with_plain_and_html(self, configured_qq):
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = mock_ssl.return_value.__enter__.return_value
            configured_qq.send("# 标题\n正文")
        msg = mock_server.send_message.call_args.args[0]
        # multipart/alternative 含两个 part：plain + html
        parts = msg.get_payload()
        assert len(parts) == 2
        types = sorted(p.get_content_type() for p in parts)
        assert types == ["text/html", "text/plain"]


class TestErrorPaths:
    def test_unconfigured(self):
        ch = EmailChannel({})
        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl, patch(
            "src.notify.channels.email.smtplib.SMTP"
        ) as mock_plain:
            r = ch.send("x")
        assert r.success is False
        assert "未配置" in r.error
        mock_ssl.assert_not_called()
        mock_plain.assert_not_called()

    def test_auth_error_returns_friendly_message(self, configured_qq):
        import smtplib

        with patch("src.notify.channels.email.smtplib.SMTP_SSL") as mock_ssl:
            mock_server = mock_ssl.return_value.__enter__.return_value
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
            r = configured_qq.send("x")
        assert r.success is False
        assert "认证错误" in r.error or "授权码" in r.error

    def test_connect_error_returns_friendly_message(self, configured_qq):
        import smtplib

        with patch(
            "src.notify.channels.email.smtplib.SMTP_SSL",
            side_effect=smtplib.SMTPConnectError(421, "boom"),
        ):
            r = configured_qq.send("x")
        assert r.success is False
        assert "无法连接" in r.error or "SMTP" in r.error

    def test_unexpected_exception_caught(self, configured_qq):
        with patch(
            "src.notify.channels.email.smtplib.SMTP_SSL", side_effect=RuntimeError("kaboom")
        ):
            r = configured_qq.send("x")
        assert r.success is False
        assert "kaboom" in r.error
