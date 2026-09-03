import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from DataBaseManagement.dbConectionPostgres import get_db_users
from DataBaseManagement.dbManagementUsers import get_user_by_email, get_user_by_id, update_user
from DataBaseManagement.schemasUsers import AuthSessionResponse, GoogleLoginRequest, PasswordLoginRequest, UserPublicResponse
from auth_service import build_session_payload, sync_google_user, verify_google_credential
from passwords import hash_password, verify_password
from security import create_session_token, extract_bearer_token, get_session_ttl_seconds, revoke_session_token, verify_session_token

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("api.endpointsAuth")


def _to_public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in UserPublicResponse.model_fields.keys()}


def _get_session_claims(authorization: str | None) -> dict[str, Any]:
    token = (authorization or "").strip()
    if token.startswith("Bearer "):
        token = token[len("Bearer "):].strip()

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token")

    claims = verify_session_token(token)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    return claims


@router.post("/google", response_model=AuthSessionResponse)
def login_with_google(payload: GoogleLoginRequest, db=Depends(get_db_users)):
    logger.info("event=google_login_start")
    google_profile = verify_google_credential(payload.credential)
    user = sync_google_user(google_profile, connection=db)
    session_token = create_session_token(build_session_payload(user))

    response = AuthSessionResponse(
        access_token=session_token,
        expires_in=get_session_ttl_seconds(),
        user=_to_public_user(user),
    )
    logger.info("event=google_login_success user_id=%s email=%s", user.get("id"), user.get("email"))
    return response


@router.post("/password", response_model=AuthSessionResponse)
def login_with_password(payload: PasswordLoginRequest, db=Depends(get_db_users)):
    email = payload.email.strip().lower()
    if not email or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email and password are required")

    user = get_user_by_email(email, connection=db)
    stored_password = str(user.get("password") or "") if user else ""
    if not user or not verify_password(payload.password, stored_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    now = datetime.now(timezone.utc)
    updates: dict[str, Any] = {
        "last_login_at": now,
        "updated_at": now,
    }

    if not stored_password.startswith("pbkdf2_sha256$"):
        updates["password"] = hash_password(payload.password)

    updated_user = update_user(user["id"], updates, connection=db)
    session_user = updated_user or {**user, **updates}

    session_token = create_session_token(build_session_payload(session_user))
    response = AuthSessionResponse(
        access_token=session_token,
        expires_in=get_session_ttl_seconds(),
        user=_to_public_user(session_user),
    )
    logger.info("event=password_login_success user_id=%s email=%s", session_user.get("id"), session_user.get("email"))
    return response


@router.get("/me", response_model=UserPublicResponse)
def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    _api_key: str | None = Header(default=None, alias="X-API-Key"),
    db=Depends(get_db_users),
):
    claims = _get_session_claims(authorization)
    user_id = claims.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    user = get_user_by_id(user_id, connection=db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user not found")

    return _to_public_user(user)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None, alias="Authorization")):
    token = extract_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token")

    claims = revoke_session_token(token)
    if claims is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

    return {"status": "ok", "logged_out": True}