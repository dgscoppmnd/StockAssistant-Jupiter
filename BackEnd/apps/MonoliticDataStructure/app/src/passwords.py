import base64
import binascii
import hashlib
import hmac
import secrets

PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 150000
PASSWORD_SALT_BYTES = 16


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_HASH_ITERATIONS}${_encode(salt)}${_encode(derived)}"


def is_hashed_password(value: str) -> bool:
    return value.startswith(f"{PASSWORD_HASH_PREFIX}$")


def verify_password(password: str, stored_password: str) -> bool:
    stored_value = (stored_password or "").strip()
    if not stored_value:
        return False

    if not is_hashed_password(stored_value):
        return hmac.compare_digest(stored_value, password)

    parts = stored_value.split("$", 3)
    if len(parts) != 4:
        return False

    _, iteration_text, salt_text, hash_text = parts
    try:
        iterations = int(iteration_text)
        salt = _decode(salt_text)
        expected = _decode(hash_text)
    except (TypeError, ValueError, binascii.Error):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(derived, expected)