"""Outgoing mail (e.g. signup verification) via SMTP.

Configuration lives in ``backend.config.Config``:

* ``SMTP_HOST`` / ``SMTP_PORT`` / ``SMTP_USER`` / ``SMTP_PASSWORD``
* ``MAIL_FROM`` — envelope and visible sender address
  (default ``kontakt@lehrjahre.ch``)
* ``MAIL_DEV_OUTBOX`` — in development (without ``SMTP_HOST``) outgoing
  mail is appended to this file instead of being sent.

Transport encryption is mandatory outside development: implicit TLS for
port 465, otherwise STARTTLS. A mail session without TLS is refused
rather than sending credentials or content in the clear.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from flask import current_app


class MailDeliveryError(RuntimeError):
    """Raised when a message could not be sent (transport/config problem)."""


def _write_dev_outbox(message: EmailMessage) -> None:
    """Append a rendered message to the development outbox file."""
    path = current_app.config["MAIL_DEV_OUTBOX"]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, mode=0o750, exist_ok=True)
    with open(path, "ab") as outbox:
        outbox.write(b"===== MAIL =====\n")
        outbox.write(message.as_bytes())
        outbox.write(b"\n")
    current_app.logger.info(
        "Mail development outbox: %s -> %s", message.get("To"), path
    )


def _send_smtp(message: EmailMessage, host: str, port: int) -> None:
    timeout = current_app.config.get("SMTP_TIMEOUT") or 20
    try:
        if port == 465:
            with smtplib.SMTP_SSL(
                host, port, timeout=timeout,
                context=ssl.create_default_context(),
            ) as smtp:
                smtp.ehlo()
                _login_and_send(smtp, message)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                _login_and_send(smtp, message)
    except smtplib.SMTPAuthenticationError as exc:
        current_app.logger.error("Mail authentication failed")
        raise MailDeliveryError("SMTP-Authentifizierung fehlgeschlagen.") from exc
    except (smtplib.SMTPNotSupportedError, ssl.SSLError) as exc:
        # A session without TLS would transmit credentials in the clear.
        raise MailDeliveryError("SMTP-Verbindung erfordert TLS.") from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise MailDeliveryError("Mail konnte nicht gesendet werden.") from exc


def _login_and_send(smtp: smtplib.SMTP, message: EmailMessage) -> None:
    user = current_app.config.get("SMTP_USER")
    password = current_app.config.get("SMTP_PASSWORD")
    if user and password:
        smtp.login(user, password)
    smtp.send_message(message)


def send_mail(to: str, subject: str, body: str) -> None:
    """Send a plain-text mail; raises MailDeliveryError on failure."""
    recipient = (to or "").strip()
    if not recipient or "@" not in recipient or any(c.isspace() for c in recipient):
        raise ValueError("Ungültige Empfangsadresse.")
    if not body:
        raise ValueError("Leere Nachricht.")

    config = current_app.config
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(
        (config.get("MAIL_FROM_NAME") or "", config.get("MAIL_FROM") or "")
    )
    message["To"] = recipient
    message["Message-ID"] = make_msgid(domain="lehrjahre.ch")
    message.set_content(body)

    host = config.get("SMTP_HOST") or ""
    if not host:
        if config.get("IS_DEV"):
            _write_dev_outbox(message)
            return
        raise MailDeliveryError("SMTP_HOST ist nicht konfiguriert.")

    _send_smtp(message, host, int(config.get("SMTP_PORT") or 587))


def send_user_invite(
    to: str, full_name: str, company_name: str, verify_url: str
) -> None:
    """Compose and send the first-login invitation for a newly created user."""
    subject = f"lehrjahre.ch: Einladung für {company_name}"
    body = (
        f"Guten Tag {full_name}\n\n"
        f"Sie wurden für «{company_name}» auf lehrjahre.ch, der digitalen "
        "Lerndokumentation für MEM-Berufslehren, eingeladen.\n\n"
        "Legen Sie Ihr persönliches Passwort mit diesem Link fest "
        "(gültig für 7 Tage):\n\n"
        f"{verify_url}\n\n"
        "Danach können Sie sich mit Ihrer Firmen-E-Mail-Adresse anmelden.\n\n"
        "Falls Sie diese Einladung nicht erwartet haben, ignorieren Sie "
        "diese E-Mail.\n\n"
        "Freundliche Grüsse\n"
        "das lehrjahre.ch Team\n"
        "(kontakt@lehrjahre.ch)\n"
    )
    send_mail(to, subject, body)


def send_registration_verification(to: str, full_name: str, verify_url: str) -> None:
    """Compose and send the signup verification mail."""
    subject = "lehrjahre.ch: Ihre Registrierung bestätigen"
    body = (
        f"Guten Tag {full_name}\n\n"
        "Vielen Dank für Ihre Registrierung auf lehrjahre.ch, der digitalen "
        "Lerndokumentation für MEM-Berufslehren.\n\n"
        "Bestätigen Sie Ihre E-Mail-Adresse mit diesem Link "
        "(gültig für 24 Stunden):\n\n"
        f"{verify_url}\n\n"
        "Nach der Bestätigung wird Ihre Firma angelegt und Ihr Konto "
        "aktiviert (Rolle: Administrator).\n\n"
        "Falls Sie diese Registrierung nicht ausgelöst haben, ignorieren "
        "Sie diese E-Mail — es wird dann nichts angelegt.\n\n"
        "Freundliche Grüsse\n"
        "das lehrjahre.ch Team\n"
        "(kontakt@lehrjahre.ch)\n"
    )
    send_mail(to, subject, body)
