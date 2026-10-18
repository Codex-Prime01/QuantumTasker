import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


class Command(BaseCommand):
    help = 'Create the two keys push alarms need. Run once, then copy them into Render.'

    def handle(self, *args, **options):
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_value = private_key.private_numbers().private_value.to_bytes(32, 'big')
        public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.stdout.write('Add these two environment variables (Render > Environment):\n')
        self.stdout.write(f'VAPID_PUBLIC_KEY={_b64url(public_bytes)}')
        self.stdout.write(f'VAPID_PRIVATE_KEY={_b64url(private_value)}')
        self.stdout.write('\nKeep the private key secret. If you change the keys, every device has to turn alarms on again.')
