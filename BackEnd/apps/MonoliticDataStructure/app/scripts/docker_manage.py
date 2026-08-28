#!/usr/bin/env python
"""Script para gestionar Docker containers"""

import shutil
import subprocess
import sys
from pathlib import Path

DOCKER_DIR = Path(__file__).resolve().parent.parent / "docker"


def _docker_command() -> str:
    """Devuelve el comando de Docker compatible con el entorno."""
    if shutil.which("docker") is None:
        return ""
    return "docker compose" if _docker_compose_available() else "docker-compose"


def _docker_compose_available() -> bool:
    """Comprueba si la forma moderna `docker compose` está disponible."""
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
        cwd=DOCKER_DIR,
    )
    return result.returncode == 0


def run_command(command: str):
    """Ejecuta un comando en la terminal y gestiona errores claros."""
    print(f"▶️  Ejecutando: {command}")

    if not shutil.which("docker"):
        print("❌ Docker no está instalado o no está disponible en el PATH.")
        sys.exit(1)

    result = subprocess.run(command, shell=True, cwd=DOCKER_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        if "Cannot connect to the Docker daemon" in stderr or "failed to connect to the docker API" in stderr:
            print("❌ No se pudo conectar al daemon de Docker.")
            print("   Asegúrate de que Docker Desktop está arrancado y funcionando.")
        else:
            print("❌ Error al ejecutar el comando")
            if stderr:
                print(stderr)
        sys.exit(1)

    if result.stdout:
        print(result.stdout)

def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/docker_manage.py [up|down|restart|logs|ps]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    docker_cmd = _docker_command()
    if not docker_cmd:
        print("❌ Docker no está instalado o no está disponible en el PATH.")
        sys.exit(1)

    if action == "up":
        print("🐳 Levantando contenedores...")
        run_command(f"{docker_cmd} up -d")
        print("✅ Contenedores levantados")
        print("📊 pgAdmin disponible en: http://localhost:5050")
        print("   Email: admin@supplychain.com")
        print("   Password: admin123")
        print("🔗 PostgreSQL en: localhost:5432")
        print("   Database: supply_chain")
        print("   User: admin")
        print("   Password: admin123")
    
    elif action == "down":
        print("🛑 Deteniendo contenedores...")
        run_command(f"{docker_cmd} down")
        print("✅ Contenedores detenidos")
    
    elif action == "restart":
        print("🔄 Reiniciando contenedores...")
        run_command(f"{docker_cmd} restart")
        print("✅ Contenedores reiniciados")
    
    elif action == "logs":
        run_command(f"{docker_cmd} logs -f")
    
    elif action == "ps":
        run_command(f"{docker_cmd} ps")
    
    else:
        print(f"❌ Acción desconocida: {action}")

if __name__ == "__main__":
    main()