"""Límite de intentos de login persistido en PostgreSQL (las instancias Lambda no comparten memoria).

Se bloquean por separado el email (5 fallos) y la IP (20 fallos) durante LOCK_SECONDS,
contando fallos dentro de una ventana de WINDOW_SECONDS. Si la tabla no existe o la BD falla,
no se bloquea (fail-open) y se deja un aviso en el log.
"""

import logging
import os
from typing import Any

from fastapi import HTTPException, Request, status

LOGGER = logging.getLogger("api.loginThrottle")

EMAIL_LIMIT = int(os.getenv("LOGIN_EMAIL_LIMIT", "5"))
IP_LIMIT = int(os.getenv("LOGIN_IP_LIMIT", "20"))
WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "900"))
LOCK_SECONDS = int(os.getenv("LOGIN_LOCK_SECONDS", "900"))


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _keys(email: str, ip: str) -> list[tuple[str, int]]:
    return [(f"email:{email}", EMAIL_LIMIT), (f"ip:{ip}", IP_LIMIT)]


def ensure_not_locked(connection: Any, email: str, ip: str) -> None:
    names = [name for name, _ in _keys(email, ip)]
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXTRACT(EPOCH FROM max(locked_until) - now()) FROM public.login_attempts "
                "WHERE key = ANY(%s) AND locked_until > now()",
                (names,),
            )
            row = cursor.fetchone()
        connection.commit()
    except Exception as error:
        connection.rollback()
        LOGGER.warning("event=login_throttle_unavailable error=%s", type(error).__name__)
        return
    remaining = row[0] if row else None
    if remaining:
        LOGGER.warning("event=login_locked email=%s ip=%s", email, ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Inténtalo más tarde.",
            headers={"Retry-After": str(int(remaining) + 1)},
        )


def record_failure(connection: Any, email: str, ip: str) -> None:
    LOGGER.warning("event=login_failed email=%s ip=%s", email, ip)
    try:
        with connection.cursor() as cursor:
            for name, limit in _keys(email, ip):
                cursor.execute(
                    """
                    INSERT INTO public.login_attempts AS t (key, failures, window_start)
                    VALUES (%(key)s, 1, now())
                    ON CONFLICT (key) DO UPDATE SET
                        failures = CASE WHEN t.window_start < now() - make_interval(secs => %(window)s)
                                        THEN 1 ELSE t.failures + 1 END,
                        window_start = CASE WHEN t.window_start < now() - make_interval(secs => %(window)s)
                                            THEN now() ELSE t.window_start END
                    """,
                    {"key": name, "window": WINDOW_SECONDS},
                )
                cursor.execute(
                    "UPDATE public.login_attempts SET locked_until = now() + make_interval(secs => %s) "
                    "WHERE key = %s AND failures >= %s",
                    (LOCK_SECONDS, name, limit),
                )
        connection.commit()
    except Exception as error:
        connection.rollback()
        LOGGER.warning("event=login_throttle_unavailable error=%s", type(error).__name__)


def record_success(connection: Any, email: str) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM public.login_attempts WHERE key = %s", (f"email:{email}",))
        connection.commit()
    except Exception as error:
        connection.rollback()
        LOGGER.warning("event=login_throttle_unavailable error=%s", type(error).__name__)
