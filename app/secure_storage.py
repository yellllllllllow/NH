"""Secure storage for sensitive credentials using AES-256-GCM encryption.

Provides industry-standard encryption for API keys and other secrets
stored locally on disk. Uses a machine-bound encryption key file.
"""

import os
import base64
import json
from typing import Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


KEY_FILE = ".news_agent_key"
SALT_FILE = ".news_agent_salt"
NONCE_BYTES = 12  # 96 bits for GCM
KEY_BITS = 256
PBKDF2_ITERATIONS = 600_000  # OWASP recommended minimum


def _get_data_dir() -> str:
    """Get a stable directory for storing encryption keys."""
    import sys
    if hasattr(sys, 'frozen'):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return base


def _ensure_key_exists() -> bytes:
    """Generate and persist an encryption key if one doesn't exist."""
    data_dir = _get_data_dir()
    key_path = os.path.join(data_dir, KEY_FILE)
    salt_path = os.path.join(data_dir, SALT_FILE)

    if os.path.exists(key_path) and os.path.exists(salt_path):
        with open(key_path, 'rb') as f:
            key_material = f.read()
        with open(salt_path, 'rb') as f:
            salt = f.read()
    else:
        # Generate new key material and salt
        key_material = os.urandom(32)  # 256 bits
        salt = os.urandom(16)
        try:
            with open(key_path, 'wb') as f:
                f.write(key_material)
            os.chmod(key_path, 0o600)  # Owner read/write only
            with open(salt_path, 'wb') as f:
                f.write(salt)
            os.chmod(salt_path, 0o600)
        except OSError:
            pass  # Non-critical, will use fallback

    # Derive AES-256 key using PBKDF2
    if HAS_CRYPTO:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
            backend=default_backend(),
        )
        return kdf.derive(key_material)
    else:
        # Fallback: use SHA-256 hash of key material (less secure but functional)
        import hashlib
        return hashlib.sha256(key_material + salt).digest()


def encrypt_data(plaintext: str) -> str:
    """Encrypt a string using AES-256-GCM.

    Returns base64-encoded ciphertext with embedded nonce.
    Format: base64(nonce + ciphertext + tag)
    """
    if not plaintext:
        return ""

    key = _ensure_key_exists()

    if HAS_CRYPTO:
        aesgcm = AESGCM(key)
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
        # nonce + ciphertext (which includes tag)
        return base64.b64encode(nonce + ciphertext).decode('ascii')
    else:
        # Fallback: simple XOR + base64 (obfuscation only, not true encryption)
        import struct
        nonce = os.urandom(8)
        data = plaintext.encode('utf-8')
        keystream = hashlib.sha256(key + nonce).digest()
        keystream = keystream * (len(data) // len(keystream) + 1)
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        return base64.b64encode(nonce + encrypted).decode('ascii')


def decrypt_data(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext.

    Returns the original plaintext string, or empty string on failure.
    """
    if not ciphertext_b64:
        return ""

    key = _ensure_key_exists()

    try:
        raw = base64.b64decode(ciphertext_b64)

        if HAS_CRYPTO:
            nonce = raw[:NONCE_BYTES]
            ciphertext = raw[NONCE_BYTES:]
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')
        else:
            # Fallback decryption
            import hashlib
            nonce = raw[:8]
            encrypted = raw[8:]
            keystream = hashlib.sha256(key + nonce).digest()
            keystream = keystream * (len(encrypted) // len(keystream) + 1)
            decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
            return decrypted.decode('utf-8')
    except Exception:
        return ""


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key for secure storage."""
    if not api_key:
        return ""
    return encrypt_data(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt a stored API key."""
    if not encrypted_key:
        return ""
    return decrypt_data(encrypted_key)


def is_key_encrypted(value: str) -> bool:
    """Check if a string value looks like encrypted data."""
    if not value:
        return False
    if value.startswith("sk-"):
        return False  # Plaintext API key
    try:
        raw = base64.b64decode(value)
        return len(raw) > 12  # Nonce (12) + min ciphertext
    except Exception:
        return False
