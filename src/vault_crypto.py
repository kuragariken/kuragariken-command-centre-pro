"""
vault_crypto.py — Proper encryption for the Vault.

Security model (matches KeePass/Bitwarden local vault approach):
  - PBKDF2-HMAC-SHA256, 390,000 iterations, 16-byte random salt
    derives a 32-byte key from the master password.
  - Fernet (AES-128-CBC + HMAC-SHA256) encrypts each secret individually.
  - The salt is stored in JSON alongside the ciphertext.
  - The master password itself is NEVER stored — not even its hash.
  - Wrong password → Fernet raises InvalidToken (tamper-proof).
  - Auto-lock after configurable idle timeout.

No 'no password' mode. A master password is REQUIRED to use the vault.
"""
import os
import base64
import secrets
import string
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


PBKDF2_ITERATIONS = 390_000   # OWASP 2023 recommendation for PBKDF2-SHA256
SALT_BYTES        = 16
KEY_LEN           = 32        # 256-bit


# ── Key derivation ────────────────────────────────────────────────

def derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit Fernet-compatible key from password + salt."""
    kdf = PBKDF2HMAC(
        algorithm  = hashes.SHA256(),
        length     = KEY_LEN,
        salt       = salt,
        iterations = PBKDF2_ITERATIONS,
    )
    raw_key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)   # Fernet needs urlsafe-b64


def new_salt() -> bytes:
    """Generate a cryptographically random salt."""
    return os.urandom(SALT_BYTES)


# ── Encrypt / decrypt ─────────────────────────────────────────────

def encrypt(plaintext: str, password: str, salt: bytes) -> str:
    """
    Encrypt plaintext with the given password + salt.
    Returns a single base64 string: no extra metadata needed.
    """
    key   = derive_key(password, salt)
    f     = Fernet(key)
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt(token: str, password: str, salt: bytes) -> Optional[str]:
    """
    Decrypt token with the given password + salt.
    Returns None if password is wrong or data is tampered.
    """
    try:
        key = derive_key(password, salt)
        f   = Fernet(key)
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        return None


def verify_password(password: str, salt_hex: str, test_token: str) -> bool:
    """
    Verify a master password by attempting to decrypt the canary token.
    The canary is a known plaintext encrypted when password was first set.
    """
    try:
        salt   = bytes.fromhex(salt_hex)
        result = decrypt(test_token, password, salt)
        return result == "CCP_VAULT_OK"
    except Exception:
        return False


def make_canary(password: str, salt: bytes) -> str:
    """Create a canary token to verify future password attempts."""
    return encrypt("CCP_VAULT_OK", password, salt)


# ── Password strength ─────────────────────────────────────────────

def password_strength(pw: str) -> tuple[int, str, str]:
    """
    Returns (score 0-4, label, colour).
    score 0 = very weak, 4 = strong.
    """
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 12: score += 1
    if any(c.isupper() for c in pw) and any(c.islower() for c in pw): score += 1
    if any(c.isdigit() for c in pw): score += 0.5
    if any(c in string.punctuation for c in pw): score += 0.5
    score = min(4, int(score))

    labels = ["Very Weak", "Weak", "Fair", "Strong", "Very Strong"]
    colors = ["#ef4444",   "#f97316","#fbbf24","#4ade80","#00e87a"]
    return score, labels[score], colors[score]


# ── Password generator ────────────────────────────────────────────

def generate_password(length: int = 16,
                      upper: bool = True,
                      digits: bool = True,
                      symbols: bool = True) -> str:
    """Generate a cryptographically secure random password."""
    pool = string.ascii_lowercase
    must = []
    if upper:
        pool += string.ascii_uppercase
        must.append(secrets.choice(string.ascii_uppercase))
    if digits:
        pool += string.digits
        must.append(secrets.choice(string.digits))
    if symbols:
        sym = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        pool += sym
        must.append(secrets.choice(sym))

    remaining = length - len(must)
    pw = must + [secrets.choice(pool) for _ in range(remaining)]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)
