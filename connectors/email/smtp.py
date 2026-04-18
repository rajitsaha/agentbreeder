"""SMTP Email Connector — sends email via SMTP using stdlib only.

Configuration (constructor args take priority, env vars used as fallback):
    SMTP_HOST: SMTP server hostname
    SMTP_PORT: SMTP server port (default: 587)
    SMTP_USER: SMTP authentication username
    SMTP_PASSWORD: SMTP authentication password
    SMTP_USE_TLS: Whether to use STARTTLS (default: true)
"""

from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class SMTPConnectorError(Exception):
    """Raised when an SMTP operation fails."""


class SMTPConnector(BaseConnector):
    """Sends email via SMTP and exposes connector metadata to the registry."""

    def __init__(
        self,
        host: str = "",
        port: int = 0,
        user: str = "",
        password: str = "",
        use_tls: bool | None = None,
    ) -> None:
        self._host = host or os.environ.get("SMTP_HOST", "")
        self._port = port or int(os.environ.get("SMTP_PORT", "587"))
        self._user = user or os.environ.get("SMTP_USER", "")
        self._password = password or os.environ.get("SMTP_PASSWORD", "")
        if use_tls is None:
            self._use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        else:
            self._use_tls = use_tls

    @property
    def name(self) -> str:
        return "smtp"

    async def is_available(self) -> bool:
        """Test reachability by opening and immediately closing an SMTP connection."""

        def _check() -> bool:
            try:
                with smtplib.SMTP(self._host, self._port, timeout=5) as conn:
                    conn.quit()
                return True
            except OSError:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    async def scan(self) -> list[dict]:
        """Return connector metadata describing this sender's capabilities."""
        return [
            {
                "name": "smtp-email-sender",
                "description": (
                    "Send plain-text and HTML email via SMTP. "
                    f"Configured for {self._host}:{self._port}."
                ),
                "source": self.name,
                "capabilities": ["send_email", "send_html_email"],
                "config": {
                    "host": self._host,
                    "port": self._port,
                    "use_tls": self._use_tls,
                    "authenticated": bool(self._user),
                },
            }
        ]

    def send(
        self,
        to: list[str],
        subject: str,
        body: str,
        html: str | None = None,
        from_addr: str | None = None,
    ) -> None:
        """Send an email synchronously.

        Builds a multipart/alternative message when html is supplied so that
        mail clients that cannot render HTML fall back to the plain-text body.
        """
        sender = from_addr or self._user
        if not sender:
            raise SMTPConnectorError("No sender address: supply from_addr or set SMTP_USER")
        if not self._host:
            raise SMTPConnectorError("No SMTP host configured")

        if html:
            msg: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
            assert isinstance(msg, MIMEMultipart)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(to)
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html, "html"))
        else:
            msg = MIMEText(body, "plain")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(to)

        try:
            with smtplib.SMTP(self._host, self._port) as conn:
                if self._use_tls:
                    conn.starttls()
                if self._user and self._password:
                    conn.login(self._user, self._password)
                conn.sendmail(sender, to, msg.as_string())
        except smtplib.SMTPException as exc:
            logger.error("SMTP send failed: %s", exc)
            raise SMTPConnectorError(str(exc)) from exc
        except OSError as exc:
            logger.error("SMTP connection error: %s", exc)
            raise SMTPConnectorError(str(exc)) from exc

    async def send_async(
        self,
        to: list[str],
        subject: str,
        body: str,
        html: str | None = None,
        from_addr: str | None = None,
    ) -> None:
        """Non-blocking wrapper around send() for use in async contexts."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: self.send(to, subject, body, html, from_addr),
        )
