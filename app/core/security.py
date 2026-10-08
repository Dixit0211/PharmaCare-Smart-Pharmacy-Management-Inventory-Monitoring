"""Security helpers: password hashing, verification, and role utilities."""

import secrets
import bcrypt


def hash_password(password: str) -> str:
    """Generate a bcrypt hash of the provided plain password string."""
    if not password:
        raise ValueError("Password cannot be empty")
    # Truncate to 72 bytes if needed (bcrypt standard limitation)
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random hexadecimal token."""
    return secrets.token_hex(nbytes)
