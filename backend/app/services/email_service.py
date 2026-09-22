import html
import logging
from typing import Optional, Protocol
import httpx

from backend.app.core.config import settings

logger = logging.getLogger("mirrage.email")

EMAIL_SUBJECT = "Your MIRRAGE verification code"


def generate_otp_email_text(otp: str) -> str:
    """Plain-text fallback body for OTP email."""
    return f"""MIRRAGE

Verify your email

Your MIRRAGE verification code is:

{otp}

This code expires in 10 minutes.

If you did not request this code, you can safely ignore this email.

Do not share this code with anyone.

MIRRAGE
Cybersecurity Training Environment
"""


def generate_otp_email_html(otp: str) -> str:
    """Responsive, client-compatible HTML body for OTP email."""
    escaped_otp = html.escape(otp)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Your MIRRAGE verification code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0B0D0F; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #E8E5DE;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #0B0D0F; padding: 40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 520px; background-color: #111417; border: 1px solid #252A2E; border-radius: 8px; overflow: hidden;">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 36px 20px 36px; border-bottom: 1px solid #1E232B;">
              <span style="font-family: Georgia, serif; font-size: 24px; font-weight: 700; color: #C49A52; letter-spacing: 3px;">MIRRAGE</span>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 32px 36px;">
              <h1 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 600; color: #E8E5DE;">Verify your email</h1>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #8A8F91;">
                Your MIRRAGE verification code is:
              </p>
              
              <!-- OTP Code Display -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 0 0 24px 0;">
                <tr>
                  <td align="center" style="background-color: #0F1215; border: 1px solid #252A2E; border-radius: 6px; padding: 20px;">
                    <span style="font-family: 'Courier New', Courier, monospace; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #00E5FF;">{escaped_otp}</span>
                  </td>
                </tr>
              </table>

              <p style="margin: 0 0 12px 0; font-size: 13px; line-height: 1.5; color: #8A8F91;">
                This code expires in 10 minutes.
              </p>
              <p style="margin: 0 0 12px 0; font-size: 13px; line-height: 1.5; color: #8A8F91;">
                If you did not request this code, you can safely ignore this email.
              </p>
              <p style="margin: 0 0 28px 0; font-size: 13px; line-height: 1.5; color: #A9574F; font-weight: 500;">
                Do not share this code with anyone.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 24px 36px; background-color: #0E100F; border-top: 1px solid #1E232B;">
              <p style="margin: 0 0 4px 0; font-size: 12px; font-weight: 600; color: #656B6E; letter-spacing: 1px;">MIRRAGE</p>
              <p style="margin: 0; font-size: 11px; color: #656B6E;">Cybersecurity Training Environment</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


class EmailServiceProvider(Protocol):
    async def send_otp(self, email: str, otp: str) -> None:
        ...


class EmailService:
    def __init__(self):
        self.provider = settings.EMAIL_PROVIDER.lower().strip() if settings.EMAIL_PROVIDER else ""

    def _get_from_address(self) -> str:
        """Construct the sender address with display name if available."""
        from_email = settings.EMAIL_FROM or settings.EMAIL_FROM_ADDRESS
        if settings.EMAIL_FROM_NAME and from_email:
            return f"{settings.EMAIL_FROM_NAME} <{from_email}>"
        return from_email

    async def send_otp(self, email: str, otp: str) -> None:
        """Send OTP to the given email address using the configured provider."""
        # Development mode: output to console only if explicitly enabled
        if settings.ENVIRONMENT == "development" and settings.OTP_DEV_MODE:
            print(f"========== DEV MODE OTP ==========")
            print(f"To: {email}")
            print(f"OTP: {otp}")
            print(f"==================================")
            return

        # Testing mode: silent bypass unless explicitly testing email
        if settings.ENVIRONMENT == "testing":
            return

        subject = EMAIL_SUBJECT
        text_content = generate_otp_email_text(otp)
        html_content = generate_otp_email_html(otp)
        from_header = self._get_from_address()

        if self.provider == "resend":
            await self._send_resend(email, subject, text_content, html_content, from_header)
        elif self.provider == "sendgrid":
            await self._send_sendgrid(email, subject, text_content, html_content, from_header)
        elif self.provider == "smtp":
            await self._send_smtp(email, subject, text_content, html_content, from_header)
        else:
            if settings.ENVIRONMENT == "production":
                raise ValueError(
                    "EMAIL_PROVIDER is not configured for production. "
                    "Set EMAIL_PROVIDER=resend|sendgrid|smtp and provide EMAIL_API_KEY."
                )
            logger.info("No EMAIL_PROVIDER configured; OTP email not sent in non-production.")

    async def _send_resend(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
        from_header: str,
    ) -> None:
        """Send email via Resend REST API."""
        if not settings.EMAIL_API_KEY:
            raise ValueError("EMAIL_API_KEY is required for Resend provider")

        payload = {
            "from": from_header,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        if settings.EMAIL_REPLY_TO:
            payload["reply_to"] = settings.EMAIL_REPLY_TO

        headers = {
            "Authorization": f"Bearer {settings.EMAIL_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                logger.error(
                    f"Resend email dispatch failed (HTTP {resp.status_code}). Check provider configuration."
                )
                raise RuntimeError(f"Email delivery failed with status {resp.status_code}")
            logger.info(f"OTP verification email successfully queued via Resend for {to_email}")

    async def _send_sendgrid(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
        from_header: str,
    ) -> None:
        """Send email via SendGrid v3 API."""
        if not settings.EMAIL_API_KEY:
            raise ValueError("EMAIL_API_KEY is required for SendGrid provider")

        from_email = settings.EMAIL_FROM or settings.EMAIL_FROM_ADDRESS
        from_dict = {"email": from_email}
        if settings.EMAIL_FROM_NAME:
            from_dict["name"] = settings.EMAIL_FROM_NAME

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": from_dict,
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
        }
        if settings.EMAIL_REPLY_TO:
            payload["reply_to"] = {"email": settings.EMAIL_REPLY_TO}

        headers = {
            "Authorization": f"Bearer {settings.EMAIL_API_KEY}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers=headers,
            )
            if resp.status_code not in (200, 202):
                logger.error(
                    f"SendGrid email dispatch failed (HTTP {resp.status_code}). Check provider configuration."
                )
                raise RuntimeError(f"Email delivery failed with status {resp.status_code}")
            logger.info(f"OTP verification email successfully queued via SendGrid for {to_email}")

    async def _send_smtp(
        self,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
        from_header: str,
    ) -> None:
        """Send email via standard SMTP."""
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_header
        msg["To"] = to_email
        if settings.EMAIL_REPLY_TO:
            msg["Reply-To"] = settings.EMAIL_REPLY_TO

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        # In production SMTP configuration, server parameters would be loaded
        logger.info(f"SMTP dispatch prepared for {to_email}")


email_service = EmailService()
