"""Field-level encryption service for Phase 6.

Uses AES-256-GCM via the ``cryptography`` library with PBKDF2 key derivation.
Also provides a SQLAlchemy ``TypeDecorator`` for transparent column encryption.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from sqlalchemy import String, TypeDecorator

from app.config import settings

# ---------------------------------------------------------------------------
# Key derivation
# ---------------------------------------------------------------------------
_SALT = b"sovereign-ai-hub-salt-v1"  # Static salt; rotate via key change
_KEY_CACHE: dict[str, bytes] = {}


def _derive_key(passphrase: str | None = None) -> bytes:
    """Derive a 256-bit AES key from the passphrase using PBKDF2."""
    passphrase = passphrase or settings.encryption_key or settings.gateway_secret_key
    if passphrase in _KEY_CACHE:
        return _KEY_CACHE[passphrase]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=600_000,
        backend=default_backend(),
    )
    key = kdf.derive(passphrase.encode("utf-8"))
    _KEY_CACHE[passphrase] = key
    return key


# ---------------------------------------------------------------------------
# Encrypt / decrypt helpers
# ---------------------------------------------------------------------------
def encrypt_field(plaintext: str, key: bytes | None = None) -> str:
    """Encrypt *plaintext* with AES-256-GCM. Returns base64 ``nonce:ciphertext``."""
    if not plaintext:
        return plaintext
    aes_key = key or _derive_key()
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # 96-bit nonce
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Encode nonce + ciphertext together
    combined = nonce + ct
    return base64.b64encode(combined).decode("ascii")


def decrypt_field(ciphertext: str, key: bytes | None = None) -> str:
    """Decrypt a value produced by ``encrypt_field``."""
    if not ciphertext:
        return ciphertext
    aes_key = key or _derive_key()
    combined = base64.b64decode(ciphertext)
    nonce = combined[:12]
    ct = combined[12:]
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ct, None)
    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# SQLAlchemy TypeDecorator for transparent column encryption
# ---------------------------------------------------------------------------
class EncryptedString(TypeDecorator):
    """A SQLAlchemy column type that transparently encrypts/decrypts values.

    Usage::

        class SecretModel(Base):
            __tablename__ = "secrets"
            id = mapped_column(Integer, primary_key=True)
            secret_value = mapped_column(EncryptedString(length=2048))
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 4096, **kwargs: Any) -> None:
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        return encrypt_field(value)

    def process_result_value(self, value: str | None, dialect: Any) -> str | None:
        if value is None:
            return None
        try:
            return decrypt_field(value)
        except Exception:
            # Return raw value if decryption fails (e.g. unencrypted legacy data)
            return value
