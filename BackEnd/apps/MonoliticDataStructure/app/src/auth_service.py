import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import HTTPException, status

from DataBaseManagement.dbManagementUsers import (
    get_user_by_email,
    get_user_by_google_sub,
    insert_user,
    update_user,
)

LOGGER = logging.getLogger("api.auth")
GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo?id_token={credential}"


def _get_google_client_id() -> str:
    client_id = os.getenv(GOOGLE_CLIENT_ID_ENV, "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google client id not configured",
        )
    return client_id


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _is_authorized_google_identity(email: str, hosted_domain: str | None) -> bool:
    if hosted_domain:
        return True
    return "@" in _normalize_email(email)


def verify_google_credential(credential: str) -> dict[str, Any]:
    client_id = _get_google_client_id()
    response = requests.get(GOOGLE_TOKENINFO_URL.format(credential=credential.strip()), timeout=10)
    if response.status_code != 200:
        LOGGER.warning("event=google_token_invalid status=%s", response.status_code)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    payload = response.json()
    audience = payload.get("aud")
    if audience != client_id:
        LOGGER.warning("event=google_token_audience_mismatch aud=%s", audience)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

    if str(payload.get("email_verified", "")).lower() not in {"true", "1"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Google email is not verified")

    email = str(payload.get("email", "")).strip()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google credential missing email")

    return payload


def _build_description(email: str, profile: dict[str, Any]) -> str:
    full_name = str(profile.get("name") or "").strip()
    if full_name:
        return f"Google user {full_name} ({email})"
    return f"Google user {email}"


def _default_name(email: str, profile: dict[str, Any]) -> str:
    for key in ("given_name", "name"):
        value = str(profile.get(key) or "").strip()
        if value:
            return value[:100]

    local_part = email.split("@", 1)[0].strip() or "Usuario"
    return local_part[:100]


def _default_last_name(profile: dict[str, Any]) -> str:
    value = str(profile.get("family_name") or "").strip()
    if value:
        return value[:100]
    return "Google"


def sync_google_user(profile: dict[str, Any], connection: Any = None) -> dict[str, Any]:
    email = _normalize_email(str(profile.get("email", "")))
    google_sub = str(profile.get("sub", "")).strip()
    hosted_domain = profile.get("hd") if isinstance(profile.get("hd"), str) else None

    existing = get_user_by_google_sub(google_sub, connection=connection) if google_sub else None
    if existing is None:
        existing = get_user_by_email(email, connection=connection)

    if existing is None and not _is_authorized_google_identity(email, hosted_domain):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo se permiten cuentas verificadas por Google o usuarios ya registrados",
        )

    now = datetime.now(timezone.utc)
    avatar_url = str(profile.get("picture") or "").strip() or None
    given_name = str(profile.get("given_name") or "").strip() or None
    family_name = str(profile.get("family_name") or "").strip() or None
    email_verified = str(profile.get("email_verified", "")).lower() in {"true", "1"}
    full_name = str(profile.get("name") or "").strip() or None

    if existing is None:
        payload = {
            "nombre": (given_name or _default_name(email, profile))[:100],
            "apellido": (family_name or _default_last_name(profile))[:100],
            "email": email,
            "descripcion": _build_description(email, profile)[:200],
            "password": secrets.token_urlsafe(32),
            "status": 1,
            "startline": None,
            "deadline": None,
            "auth_provider": "google",
            "google_sub": google_sub or None,
            "avatar_url": avatar_url,
            "given_name": given_name,
            "family_name": family_name,
            "email_verified": email_verified,
            "last_login_at": now,
            "updated_at": now,
        }
        return insert_user(payload, connection=connection)

    updates: dict[str, Any] = {
        "auth_provider": "google",
        "updated_at": now,
        "last_login_at": now,
        "email_verified": email_verified,
    }

    if google_sub and existing.get("google_sub") != google_sub:
        updates["google_sub"] = google_sub

    if avatar_url:
        updates["avatar_url"] = avatar_url

    if given_name and not str(existing.get("nombre") or "").strip():
        updates["nombre"] = given_name[:100]

    if family_name and not str(existing.get("apellido") or "").strip():
        updates["apellido"] = family_name[:100]

    if full_name and not str(existing.get("descripcion") or "").strip():
        updates["descripcion"] = _build_description(email, profile)[:200]

    if email and _normalize_email(str(existing.get("email", ""))) != email:
        updates["email"] = email

    updated = update_user(existing["id"], updates, connection=connection)
    return updated or existing


def build_session_payload(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "sub": str(user.get("id")),
        "user_id": user.get("id"),
        "email": user.get("email"),
        "name": f"{user.get('nombre', '')} {user.get('apellido', '')}".strip(),
        "auth_provider": user.get("auth_provider", "google"),
        "avatar_url": user.get("avatar_url"),
    }
