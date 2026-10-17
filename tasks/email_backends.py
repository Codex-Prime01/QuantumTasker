"""
Email backend that sends through Brevo's HTTPS API (port 443).

Render's free plan blocks outbound SMTP ports, so plain SMTP hangs and the
request gets killed by gunicorn. HTTPS is never blocked.
"""
import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_SEND_URL = 'https://api.brevo.com/v3/smtp/email'


def _contact(address):
    name, email = parseaddr(address)
    contact = {'email': email}
    if name:
        contact['name'] = name
    return contact


class BrevoAPIBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            payload = {
                'sender': _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
                'to': [_contact(addr) for addr in message.to],
                'subject': message.subject,
                'textContent': message.body,
            }
            for content, mimetype in getattr(message, 'alternatives', []):
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
            if message.cc:
                payload['cc'] = [_contact(a) for a in message.cc]
            if message.bcc:
                payload['bcc'] = [_contact(a) for a in message.bcc]
            if message.reply_to:
                payload['replyTo'] = _contact(message.reply_to[0])

            try:
                response = requests.post(
                    BREVO_SEND_URL,
                    json=payload,
                    headers={
                        'api-key': settings.BREVO_API_KEY,
                        'accept': 'application/json',
                    },
                    timeout=settings.EMAIL_SEND_TIMEOUT,
                )
                response.raise_for_status()
                sent += 1
            except requests.RequestException as exc:
                body = getattr(getattr(exc, 'response', None), 'text', '')
                logger.error('Brevo send failed: %s %s', exc, body[:300])
                if not self.fail_silently:
                    raise
        return sent
