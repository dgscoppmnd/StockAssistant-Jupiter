"""Apply only the bundled init.sql, with transactional validation and real progress."""
import logging
import os
import time
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

from database_schema import SCHEMA_PATH
from schema_update_core import LOCK_KEY, load_update as load_schema_update, validate_schema
from DataBaseManagement.dbConectionPostgres import (
    _database_name, _get_env, _get_postgres_connection_server, db_context,
)

LOGGER = logging.getLogger('api.schema_update')


def schema_admin_ids():
    # Reserved for future role-based authorization. Setup endpoints temporarily
    # ignore this allowlist; its configuration and parsing remain available.
    default = '' if os.getenv('AWS_LAMBDA_FUNCTION_NAME') else '1'
    return {int(value.strip()) for value in os.getenv('SCHEMA_ADMIN_USER_IDS', default).split(',')
            if value.strip().isdigit()}


def load_update():
    return load_schema_update(SCHEMA_PATH)


def last_update(connection):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT to_regclass('public.app_schema_updates') AS relation")
        if cursor.fetchone()['relation'] is None:
            return None
        cursor.execute('SELECT checksum,run_id,applied_at,statement_count,validated_constraints FROM public.app_schema_updates WHERE id=1')
        row = cursor.fetchone()
        return dict(row) if row else None


def applied_update(connection, checksum):
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute("SELECT to_regclass('public.app_schema_update_history') AS relation")
        if cursor.fetchone()['relation'] is not None:
            cursor.execute('SELECT checksum,run_id,applied_at,statement_count,validated_constraints FROM public.app_schema_update_history WHERE checksum=%s', (checksum,))
            row = cursor.fetchone()
            if row:
                return dict(row)
    previous = last_update(connection)
    return previous if previous and previous['checksum'] == checksum else None


def update_status():
    checksum, statements = load_update()
    with db_context() as connection:
        previous = last_update(connection)
        applied = applied_update(connection, checksum)
    return {'checksum': checksum, 'statement_count': len(statements), 'last_update': previous,
            'pending': applied is None, 'applied_update': applied}


def migration_connection():
    dsn = os.getenv('JUPITER_MIGRATION_DSN', '').strip()
    is_lambda = bool(os.getenv('AWS_LAMBDA_FUNCTION_NAME'))
    if is_lambda and not dsn:
        import boto3
        parameter = os.getenv('SCHEMA_MIGRATION_DSN_PARAMETER', '/stockassistant/prod/db/migration_dsn')
        dsn = boto3.client('ssm').get_parameter(Name=parameter, WithDecryption=True)['Parameter']['Value']
    if not dsn:
        return _get_postgres_connection_server()
    parameters = psycopg2.extensions.parse_dsn(dsn)
    expected_host = _get_env('POSTGRES_HOST', 'DB_HOST', default='postgres')
    expected_port = _get_env('POSTGRES_PORT', 'DB_PORT', default='5432')
    if (parameters.get('dbname') != _database_name()
            or parameters.get('host', '').lower() != expected_host.lower()
            or int(parameters.get('port', '5432')) != int(expected_port)):
        raise ValueError('La conexión de migración no corresponde a la base de datos de la aplicación.')
    options = {'connect_timeout': 15, 'application_name': 'jupiter-schema-update'}
    if is_lambda:
        options.update(sslmode='verify-full', sslrootcert=os.getenv('PGSSLROOTCERT', '/opt/rds-global-bundle.pem'))
    return psycopg2.connect(dsn, **options)


def apply_update(user_id, checksum, statements, *, connect=migration_connection, validate=validate_schema):
    connection = None
    committed = False
    commit_attempted = False
    run_id = str(uuid4())
    processed = 0
    started = time.monotonic()
    yield {'stage': 'connecting', 'percent': 2, 'message': 'Conectando con la base de datos.', 'run_id': run_id}
    try:
        connection = connect()
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('statement_timeout', '60000', true)")
            cursor.execute("SELECT set_config('lock_timeout', '15000', true)")
            cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', (LOCK_KEY,))
            if not cursor.fetchone()[0]:
                raise RuntimeError('Otra actualización está en curso. Espera a que termine.')
            # Check inside the same database lock: retries, new Lambda instances
            # and concurrent requests cannot reapply a successfully committed file.
            previous = applied_update(connection, checksum)
            if previous:
                connection.rollback()
                yield {'stage': 'complete', 'percent': 100,
                       'message': 'Esta versión de init.sql ya se aplicó. No se ejecutaron cambios.',
                       'run_id': previous['run_id'], 'result': {
                           'checksum': checksum, 'run_id': previous['run_id'],
                           'statement_count': previous['statement_count'], 'already_applied': True}}
                return
            timezone = os.getenv('DB_LEGACY_TIMEZONE')
            if timezone:
                cursor.execute("SELECT set_config('TimeZone', %s, true)", (timezone,))
            yield {'stage': 'applying', 'percent': 5, 'processed': 0, 'total': len(statements),
                   'message': 'Aplicando cambios dentro de una transacción.', 'run_id': run_id}
            for index, statement in enumerate(statements, 1):
                if time.monotonic() - started > 240:
                    raise RuntimeError('La actualización superó el tiempo permitido.')
                cursor.execute(statement)
                processed = index
                yield {'stage': 'applying', 'percent': 5 + int(80 * index / len(statements)),
                       'processed': index, 'total': len(statements), 'run_id': run_id,
                       'message': f'Instrucción {index} de {len(statements)} aplicada provisionalmente.'}
            yield {'stage': 'validating', 'percent': 90, 'message': 'Validando tablas, columnas y restricciones.', 'run_id': run_id}
            validated = validate(connection)
            cursor.execute("""INSERT INTO public.app_schema_updates
                              (id,checksum,run_id,actor_id,statement_count,validated_constraints)
                              VALUES (1,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET
                              checksum=EXCLUDED.checksum,run_id=EXCLUDED.run_id,actor_id=EXCLUDED.actor_id,
                              applied_at=CURRENT_TIMESTAMP,statement_count=EXCLUDED.statement_count,
                              validated_constraints=EXCLUDED.validated_constraints""",
                           (checksum, run_id, user_id, len(statements), validated))
            cursor.execute("""INSERT INTO public.app_schema_update_history
                              (checksum,run_id,applied_at,statement_count,validated_constraints)
                              SELECT checksum,run_id,applied_at,statement_count,validated_constraints
                              FROM public.app_schema_updates WHERE id=1""")
            yield {'stage': 'committing', 'percent': 98, 'message': 'Validación correcta. Confirmando cambios.', 'run_id': run_id}
        commit_attempted = True
        connection.commit()
        committed = True
        LOGGER.info('event=schema_update_committed actor_id=%s run_id=%s checksum=%s', user_id, run_id, checksum)
        yield {'stage': 'complete', 'percent': 100, 'message': 'Base de datos actualizada y validada correctamente.',
               'run_id': run_id, 'result': {'checksum': checksum, 'run_id': run_id,
               'statement_count': len(statements), 'validated_constraints': validated}}
    except Exception as error:
        rolled_back = False
        if connection is not None:
            try:
                connection.rollback()
                rolled_back = not commit_attempted
            except Exception:
                pass
        code = getattr(error, 'pgcode', None)
        LOGGER.error('event=schema_update_failed actor_id=%s run_id=%s statement=%s type=%s code=%s',
                     user_id, run_id, processed + 1, type(error).__name__, code)
        message = ('La conexión no tiene permisos para modificar el esquema. Configura la conexión de migración.'
                   if code == '42501' else 'La actualización o su validación ha fallado.')
        if isinstance(error, RuntimeError) and not commit_attempted:
            message = str(error)
        if commit_attempted:
            message = 'No se pudo confirmar el resultado. Consulta el estado antes de volver a ejecutar.'
        elif rolled_back:
            message += ' Los cambios de esta ejecución se han descartado.'
        elif connection is None:
            message = 'No se pudo abrir la conexión de migración. No se aplicaron cambios.'
        yield {'stage': 'error', 'message': message, 'detail': message, 'rolled_back': rolled_back,
               'outcome_unknown': commit_attempted, 'run_id': run_id, 'code': code}
    finally:
        if connection is not None:
            if not committed:
                try:
                    connection.rollback()
                except Exception:
                    pass
            connection.close()
