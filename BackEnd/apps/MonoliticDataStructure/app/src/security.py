import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Any, Final

from fastapi import Header, HTTPException, status

LOGGER = logging.getLogger("api.security")
API_KEYS_ENV: Final[str] = "STOCKASSISTANT_API_KEYS"
SESSION_SECRET_ENV: Final[str] = "STOCKASSISTANT_SESSION_SECRET"
SESSION_TTL_ENV: Final[str] = "STOCKASSISTANT_SESSION_TTL_MINUTES"
_REVOKED_SESSION_JTI: dict[str, int] = {}


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("event=invalid_env_int env=%s value=%s default=%s", name, raw, default)
        return default


def _parse_api_keys() -> set[str]:
    raw = os.getenv(API_KEYS_ENV, "")
    return {item.strip() for item in raw.split(",") if item and item.strip()}


def _mask_secret(secret: str) -> str:
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}***{secret[-2:]}"


def _session_secret() -> str:
    secret = os.getenv(SESSION_SECRET_ENV, "").strip()
    if secret:
        return secret

    api_keys = sorted(_parse_api_keys())
    if api_keys:
        LOGGER.warning("event=session_secret_fallback source=api_keys")
        return api_keys[0]

    LOGGER.warning("event=session_secret_fallback source=dev-default")
    return "stockassistant-dev-session-secret"


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _base64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def get_session_ttl_seconds() -> int:
    ttl_minutes = _get_env_int(SESSION_TTL_ENV, 12 * 60)
    return max(ttl_minutes, 1) * 60


def _cleanup_revoked_sessions(now_ts: int | None = None) -> None:
    now = now_ts or int(time.time())
    expired_jti = [jti for jti, expires_at in _REVOKED_SESSION_JTI.items() if expires_at <= now]
    for jti in expired_jti:
        _REVOKED_SESSION_JTI.pop(jti, None)


def _is_revoked_session_jti(jti: str | None, now_ts: int | None = None) -> bool:
    if not jti:
        return False
    _cleanup_revoked_sessions(now_ts=now_ts)
    return jti in _REVOKED_SESSION_JTI


def create_session_token(claims: dict[str, Any]) -> str:
    issued_at = int(time.time())
    ttl_seconds = get_session_ttl_seconds()
    payload = {
        **claims,
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
        "iss": "stockassistant-api",
        "jti": claims.get("jti") or secrets.token_urlsafe(12),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        (
            _base64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
            _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        )
    )
    signature = hmac.new(
        _session_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def verify_session_token(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None

    header_raw, payload_raw, signature_raw = parts
    signing_input = f"{header_raw}.{payload_raw}"
    expected_signature = hmac.new(
        _session_secret().encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    try:
        provided_signature = _base64url_decode(signature_raw)
        payload = json.loads(_base64url_decode(payload_raw).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None

    if not hmac.compare_digest(expected_signature, provided_signature):
        return None

    now_ts = int(time.time())
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < now_ts:
        return None

    if payload.get("iss") != "stockassistant-api":
        return None

    if _is_revoked_session_jti(payload.get("jti"), now_ts=now_ts):
        return None

    return payload


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""

    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix):].strip()

    return authorization.strip()


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    expected_keys = _parse_api_keys()
    if not expected_keys:
        LOGGER.error("event=api_key_not_configured env=%s", API_KEYS_ENV)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key not configured on server",
        )

    bearer_token = extract_bearer_token(authorization)
    candidate = (x_api_key or bearer_token or "").strip()
    if not candidate:
        LOGGER.warning("event=api_key_missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if candidate not in expected_keys:
        session_claims = verify_session_token(candidate)
        if session_claims is None:
            LOGGER.warning("event=api_or_session_invalid key=%s", _mask_secret(candidate))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

    return candidate


def revoke_session_token(token: str) -> dict[str, Any] | None:
    claims = verify_session_token(token)
    if claims is None:
        return None

    jti = claims.get("jti")
    expires_at = claims.get("exp")
    if isinstance(jti, str) and isinstance(expires_at, int):
        _cleanup_revoked_sessions()
        _REVOKED_SESSION_JTI[jti] = expires_at
        LOGGER.info("event=session_revoked jti=%s exp=%s", jti, expires_at)

    return claims
