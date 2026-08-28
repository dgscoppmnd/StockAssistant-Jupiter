.PHONY: help build up down generate load api

help:
	@echo "Comandos disponibles:"
	@echo "  build    - Construir contenedores Docker"
	@echo "  up       - Levantar servicios"
	@echo "  down     - Detener servicios"
	@echo "  generate - Generar datos sintéticos"
	@echo "  load     - Cargar datos en BD"
	@echo "  api      - Iniciar API FastAPI"
	@echo "  docker-up      - Levanta contenedor BD"
	@echo "  docker-down      - Tira contenedor de BD"
	@echo "  docker-logs      - Muestra logs del contenedor"
	@echo "  docker-ps      - Muestra estado de contenedores"
	@echo "  docker-restart      - Reinicia contenedores"
	@echo "  docker-rebuild     - Recontruye contenedores desde 0"

build:
	docker compose -f docker/docker-compose.yml build

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

generate:
	python scripts/run_generator.py

load:
	python scripts/load_data.py

api:
	python scripts/run_api.py

docker-up:
	cd docker && docker-compose up -d

docker-down:
	cd docker && docker-compose down

docker-logs:
	cd docker && docker-compose logs -f

docker-ps:
	cd docker && docker-compose ps

docker-restart:
	cd docker && docker-compose restart

# Comando para reconstruir desde cero
docker-rebuild:
	cd docker && docker-compose down -v
	cd docker && docker-compose up -d
