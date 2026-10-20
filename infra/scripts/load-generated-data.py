"""Carga los CSV de data/generated en RDS con COPY (rápido y transaccional por tabla).

Uso (con el SG de RDS abierto a tu IP):
    python infra/scripts/load-generated-data.py [--only products,suppliers] [--dir RUTA]

Credenciales: usuario `app`, contraseña desde SSM, host desde RDS y base de datos desde la Lambda.
No imprime secretos. Omite las tablas que ya tienen filas (el rol `app` no puede hacer TRUNCATE).
"""

import argparse
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import psycopg2

AWS = shutil.which("aws") or "aws"
CA_URL = "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
DEFAULT_DIR = (
    Path(__file__).resolve().parents[2]
    / "BackEnd" / "apps" / "MonoliticDataStructure" / "app" / "data" / "generated"
)
# Orden que respeta las claves foráneas
ORDER = [
    ("products", "products.csv"),
    ("suppliers", "suppliers.csv"),
    ("warehouses", "warehouses.csv"),
    ("inventory", "inventory.csv"),
    ("logistics", "logistics.csv"),
    ("sales", "sales.csv"),
    ("supply_chain_metrics", "supply_chain_metrics.csv"),
]


def aws(*args: str) -> str:
    result = subprocess.run([AWS, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"aws {args[0]} {args[1]} falló: {result.stderr.strip()}")
    return result.stdout.strip()


def connect(region: str, instance: str, function: str):
    host = aws(
        "rds", "describe-db-instances", "--db-instance-identifier", instance,
        "--region", region, "--query", "DBInstances[0].Endpoint.Address", "--output", "text",
    )
    dbname = aws(
        "lambda", "get-function-configuration", "--function-name", function,
        "--region", region, "--query", "Environment.Variables.DB_NAME", "--output", "text",
    )
    password = aws(
        "ssm", "get-parameter", "--name", "/stockassistant/prod/db/app_password",
        "--with-decryption", "--region", region, "--query", "Parameter.Value", "--output", "text",
    )
    cert = Path(tempfile.gettempdir()) / "rds-global-bundle.pem"
    if not cert.exists():
        urllib.request.urlretrieve(CA_URL, cert)
    return psycopg2.connect(
        host=host, port=5432, dbname=dbname, user="app", password=password,
        sslmode="verify-full", sslrootcert=str(cert), connect_timeout=15,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--only", default="", help="tablas separadas por comas")
    parser.add_argument("--region", default="eu-west-1")
    parser.add_argument("--instance", default="stockassistant-prod")
    parser.add_argument("--function", default="stockassistant-api")
    args = parser.parse_args()
    only = {name.strip() for name in args.only.split(",") if name.strip()}

    connection = connect(args.region, args.instance, args.function)
    try:
        for table, filename in ORDER:
            if only and table not in only:
                continue
            path = args.dir / filename
            if not path.is_file():
                print(f"{table}: falta {path}, se omite")
                continue
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT EXISTS (SELECT 1 FROM public.{table})")
                if cursor.fetchone()[0]:
                    print(f"{table}: ya tiene datos, se omite")
                    continue
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                columns = source.readline().strip().split(",")
                source.seek(0)
                started = time.time()
                try:
                    with connection.cursor() as cursor:
                        cursor.copy_expert(
                            f"COPY public.{table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv, HEADER true)",
                            source,
                            1024 * 1024,
                        )
                        loaded = cursor.rowcount
                        if table == "products":
                            # This loader only COPYs into an empty table. Match
                            # the former AWS catalog view for these new rows.
                            cursor.execute("""UPDATE public.products
                                              SET price=selling_price_usd,
                                                  final_price=selling_price_usd,
                                                  currency='USD'""")
                    connection.commit()
                except Exception as error:
                    connection.rollback()
                    raise SystemExit(f"{table}: error, transacción revertida: {str(error).strip()[:600]}")
            print(f"{table}: {loaded} filas en {time.time() - started:.0f} s")
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE")
        print("ANALYZE hecho")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
