"""Email service - sends transactional emails.

In production, replace the stub with real SMTP or API (e.g. SendGrid, AWS SES).
For development, logs emails to console.
"""
from typing import Optional

from loguru import logger

from app.config import settings


class EmailService:
    """Simple email service with dev-mode console logging."""

    def __init__(self):
        self.smtp_host = getattr(settings, "smtp_host", None)
        self.smtp_port = getattr(settings, "smtp_port", 587)
        self.smtp_user = getattr(settings, "smtp_user", None)
        self.smtp_password = getattr(settings, "smtp_password", None)
        self.from_email = getattr(settings, "from_email", "2606536766@qq.com")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> bool:
        """Send an email. Returns True if successful."""
        if self.smtp_host and self.smtp_user:
            return await self._send_smtp(to_email, subject, html_body)

        # Dev mode: log to console
        logger.info(
            f"[EMAIL] To: {to_email}\n"
            f"  Subject: {subject}\n"
            f"  Body: {html_body[:200]}..."
        )
        return True

    async def _send_smtp(self, to_email: str, subject: str, html_body: str) -> bool:
        """Send via SMTP."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_email, msg.as_string())

            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    async def send_password_reset(self, to_email: str, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"http://localhost:3000/auth/reset-password?token={reset_token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>密码重置 - 合同哨兵</h2>
            <p>您好，我们收到了您的密码重置请求。</p>
            <p>请点击下方链接重置密码（30分钟内有效）：</p>
            <p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:white;text-decoration:none;border-radius:8px;">重置密码</a></p>
            <p style="color:#666;font-size:12px;">如果您没有请求重置密码，请忽略此邮件。</p>
        </div>
        """
        return await self.send_email(to_email, "密码重置 - 合同哨兵", html)

    async def send_verification_email(self, to_email: str, verify_token: str) -> bool:
        """Send email verification."""
        verify_url = f"http://localhost:3000/auth/verify-email?token={verify_token}"
        html = f"""
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>验证邮箱 - 合同哨兵</h2>
            <p>感谢注册合同哨兵！请点击下方链接验证您的邮箱：</p>
            <p><a href="{verify_url}" style="display:inline-block;padding:12px 24px;background:#2563eb;color:white;text-decoration:none;border-radius:8px;">验证邮箱</a></p>
            <p style="color:#666;font-size:12px;">链接24小时内有效。</p>
        </div>
        """
        return await self.send_email(to_email, "验证您的邮箱 - 合同哨兵", html)
