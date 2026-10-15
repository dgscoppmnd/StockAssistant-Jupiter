"""Carga secretos desde SSM Parameter Store al entorno del proceso (solo en Lambda).

Los secretos no se guardan en las variables de la función: se leen al arrancar,
una vez por instancia, y no se sobrescriben si ya existen en el entorno.
"""

import os

SSM_PREFIX = "/stockassistant/prod"

# variable de entorno -> parámetro SSM (SecureString)
SECRET_PARAMETERS = {
    "OPENAI_API_KEY": "openai_api_key",
    "GOOGLE_CLIENT_ID": "google_client_id",
    "STOCKASSISTANT_API_KEYS": "api_keys",
    "STOCKASSISTANT_SESSION_SECRET": "session_secret",
    "SECRET_KEY": "session_secret",
    "DB_PASSWORD": "db/app_password",
    "POSTGRES_PASSWORD": "db/app_password",
}


def load_secrets_from_ssm() -> None:
    if not os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("SECRETS_FROM_SSM", "").lower() != "true":
        return
    pending = {name: param for name, param in SECRET_PARAMETERS.items() if not os.getenv(name)}
    if not pending:
        return

    import boto3
    from botocore.config import Config

    client = boto3.client(
        "ssm",
        region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        config=Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 3}),
    )
    parameters = sorted({f"{SSM_PREFIX}/{param}" for param in pending.values()})
    values: dict[str, str] = {}
    for start in range(0, len(parameters), 10):
        response = client.get_parameters(Names=parameters[start:start + 10], WithDecryption=True)
        if response.get("InvalidParameters"):
            raise RuntimeError(f"Parámetros SSM inexistentes: {response['InvalidParameters']}")
        values.update({item["Name"]: item["Value"] for item in response["Parameters"]})

    for name, param in pending.items():
        os.environ[name] = values[f"{SSM_PREFIX}/{param}"]
