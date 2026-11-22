import html
import asyncio
from dataclasses import dataclass
from email.utils import formataddr
from email_validator import validate_email
import logging
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

This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.

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
                This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.
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


@dataclass(frozen=True)
class EmailDispatchResult:
    outcome: str
    http_status: int | None = None


class EmailDeliveryError(Exception):
    """Only fixed codes; never include provider bodies, keys, recipients or OTPs."""
    def __init__(self, code, *, outcome="unknown", http_status=None):
        super().__init__(code)
        self.code = code
        self.outcome = outcome
        self.http_status = http_status


class EmailService:
    def __init__(self, transport=None):
        self.transport = transport  # Injectable HTTPX mock transport in provider tests.

    @property
    def provider(self):
        value = settings.EMAIL_PROVIDER.strip().lower()
        return value if value in {"resend", "sendgrid"} else "unconfigured" if not value else "unsupported"

    def _sender(self):
        return validate_email(settings.EMAIL_FROM, check_deliverability=False, allow_smtputf8=False).ascii_email

    async def send_otp(self, email: str, otp: str) -> EmailDispatchResult:
        if settings.ENVIRONMENT == "testing":
            return EmailDispatchResult("simulated")
        if settings.ENVIRONMENT == "development" and settings.OTP_DEV_MODE:
            print(f"DEV MODE OTP for {email}: {otp}")
            return EmailDispatchResult("simulated")
        return await self._send(email, EMAIL_SUBJECT, generate_otp_email_text(otp), generate_otp_email_html(otp))

    async def send_slot_ready(self, email: str, deadline) -> EmailDispatchResult:
        if settings.ENVIRONMENT == "testing" or (settings.ENVIRONMENT == "development" and settings.OTP_DEV_MODE):
            return EmailDispatchResult("simulated")
        url = "https://themirrage.me/sessions"
        expires = deadline.strftime("%d %b %Y at %H:%M UTC")
        message = f"Your MIRRAGE slot is reserved until {expires}. Sign in and start your environment before the reservation expires."
        return await self._send(email, "Your MIRRAGE slot is ready", f"{message}\n\n{url}",
                                f'<p>{message}</p><p><a href="{url}">Open MIRRAGE sessions</a></p>')

    async def _send(self, email: str, subject: str, text: str, html_body: str) -> EmailDispatchResult:
        if error := settings.email_configuration_error():
            raise EmailDeliveryError(error, outcome="failed")
        sender = self._sender()
        reply = (validate_email(settings.EMAIL_REPLY_TO, check_deliverability=False,
                                allow_smtputf8=False).ascii_email if settings.EMAIL_REPLY_TO else None)
        if self.provider == "resend":
            endpoint = "https://api.resend.com/emails"
            payload = {"from": formataddr((settings.EMAIL_FROM_NAME, sender)), "to": [email],
                       "subject": subject, "text": text, "html": html_body}
            if reply:
                payload["reply_to"] = reply
        else:
            endpoint = "https://api.sendgrid.com/v3/mail/send"
            payload = {"personalizations": [{"to": [{"email": email}]}],
                       "from": {"email": sender, "name": settings.EMAIL_FROM_NAME},
                       "subject": subject, "content": [{"type": "text/plain", "value": text},
                                                              {"type": "text/html", "value": html_body}]}
            if reply:
                payload["reply_to"] = {"email": reply}
        try:
            async with asyncio.timeout(settings.EMAIL_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(timeout=settings.EMAIL_TIMEOUT_SECONDS, transport=self.transport,
                                             follow_redirects=False, trust_env=False) as client:
                    response = await client.post(endpoint, json=payload, headers={
                        "Authorization": f"Bearer {settings.EMAIL_API_KEY}", "Content-Type": "application/json"})
            accepted = response.status_code == (200 if self.provider == "resend" else 202)
            if not accepted:
                # A server-side failure can have ambiguous side effects. Do not retry.
                raise EmailDeliveryError("PROVIDER_REJECTED", http_status=response.status_code,
                                         outcome="unknown" if response.status_code >= 500 else "failed")
            if self.provider == "resend":
                try:
                    receipt = response.json()
                    if not isinstance(receipt, dict) or not isinstance(receipt.get("id"), str) or not receipt["id"]:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise EmailDeliveryError("PROVIDER_RESPONSE_INVALID", http_status=response.status_code) from None
            logger.info("Email accepted by provider %s", self.provider)
            return EmailDispatchResult("accepted", response.status_code)
        except (TimeoutError, httpx.TimeoutException):
            raise EmailDeliveryError("PROVIDER_TIMEOUT") from None
        except httpx.RequestError:
            raise EmailDeliveryError("PROVIDER_NETWORK_ERROR") from None


email_service = EmailService()
