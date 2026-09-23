.PHONY: check backend-check frontend-check test lint typecheck build docker-check

check: backend-check frontend-check docker-check

backend-check:
	cd backend && ruff check .
	cd backend && mypy app
	cd backend && pytest -q

frontend-check:
	cd frontend && npm run lint
	cd frontend && npm run test -- --run
	cd frontend && npm run build

docker-check:
	docker compose config --quiet

test:
	cd backend && pytest

lint:
	cd backend && ruff check .

typecheck:
	cd backend && mypy app

build:
	cd frontend && npm run build