"""Session-only, server-authorized execution of the bundled schema file."""
import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from psycopg2.extras import RealDictCursor

from DataBaseManagement.dbConectionPostgres import db_context
from security import extract_bearer_token, verify_session_token
from schema_update_service import apply_update, load_update, update_status

router = APIRouter(prefix='/setup/database', tags=['Setup'])


def setup_user(authorization: str | None = Header(default=None)):
    claims = verify_session_token(extract_bearer_token(authorization))
    if not claims or not isinstance(claims.get('user_id'), int):
        raise HTTPException(401, 'Inicia sesión para consultar la configuración de la base de datos.')
    # Close this connection before streaming: holding a users read lock would
    # otherwise block ALTER TABLE users in the migration itself.
    with db_context() as connection, connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("""SELECT id FROM public.users WHERE id=%s AND status=1
                          AND (startline IS NULL OR startline<=CURRENT_TIMESTAMP)
                          AND (deadline IS NULL OR deadline>CURRENT_TIMESTAMP)""", (claims['user_id'],))
        user = cursor.fetchone()
    if not user:
        raise HTTPException(401, 'La cuenta no está activa o ha caducado.')
    return int(user['id'])


class SchemaUpdateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_checksum: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.get('/status')
def database_status(user_id: int = Depends(setup_user)):
    # SCHEMA_ADMIN_USER_IDS is intentionally ignored until user roles are added.
    # setup_user still requires a valid session and an active, unexpired account.
    try:
        return {'can_update': True, **update_status()}
    except Exception:
        raise HTTPException(503, 'No se pudo consultar el estado del esquema.') from None


@router.post('/update')
def update_database(payload: SchemaUpdateRequest, user_id: int = Depends(setup_user)):
    # Same temporary authorization policy as /status; keep session validation.
    try:
        checksum, statements = load_update()
    except Exception:
        raise HTTPException(503, 'No se pudo preparar el init.sql del servidor. No se aplicaron cambios.') from None
    if checksum != payload.expected_checksum:
        raise HTTPException(409, 'init.sql cambió desde la última consulta. Actualiza el estado y vuelve a intentarlo.')

    def events():
        for event in apply_update(user_id, checksum, statements):
            yield json.dumps(event, ensure_ascii=False) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson', headers={
        'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no',
    })
