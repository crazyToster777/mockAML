.PHONY: up down restart logs ps build migrate test test-all allure

# --- Docker Compose ---

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

ps:
	docker compose ps

build:
	docker compose build --no-cache

migrate:
	docker compose run --rm migrate

# --- Tests (run locally, requires .venv) ---

test:
	pytest -m "unit or api" --alluredir=allure-results -q

test-all:
	pytest --alluredir=allure-results -q

allure:
	allure generate allure-results -o allure-report --clean
	allure open allure-report
