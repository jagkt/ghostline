ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: up down logs psql

up:
	docker compose up -d
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose ps postgres | grep -q healthy; do sleep 1; done
	@echo "Postgres is up."

down:
	docker compose down

logs:
	docker compose logs -f


psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-ghostline} -d $${POSTGRES_DB:-ghostline}
