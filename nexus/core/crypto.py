"""
Cryptographic Handshake and Transport Primitives
Handles public modulus reconstruction and PKCS1_v1_5 padding for platform authentication payloads.
"""

import base64
from typing import Tuple, Optional

try:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Cipher import PKCS1_v1_5
except ImportError:
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
    except ImportError:
        RSA = None
        PKCS1_v1_5 = None


def encrypt_password_payload(password: str, mod_hex: str, exp_hex: str) -> Optional[str]:
    """
    Encrypts target password using RSA public key (n, e) with PKCS#1 v1.5 padding.
    Returns base64-encoded encrypted string.
    """
    if not RSA or not PKCS1_v1_5:
        # Fallback implementation using cryptography library if available
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa, padding
            n = int(mod_hex, 16)
            e = int(exp_hex, 16)
            public_numbers = rsa.RSAPublicNumbers(e, n)
            public_key = public_numbers.public_key()
            encrypted = public_key.encrypt(
                password.encode("utf-8"),
                padding.PKCS1v15()
            )
            return base64.b64encode(encrypted).decode("ascii")
        except Exception:
            return None

    try:
        n = int(mod_hex, 16)
        e = int(exp_hex, 16)
        rsa_key = RSA.construct((n, e))
        cipher = PKCS1_v1_5.new(rsa_key)
        encrypted_bytes = cipher.encrypt(password.encode("utf-8"))
        return base64.b64encode(encrypted_bytes).decode("ascii")
    except Exception:
        return None
