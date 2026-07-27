.PHONY: up down seed demo sim rush test test-fe lint storybook load

up: ## bring the stack up; every container healthy in <90s
	@test -f config.yaml || cp config.example.yaml config.yaml
	docker compose up -d --build --wait --wait-timeout 90
	docker compose ps
	docker compose exec gateway python manage.py migrate
	docker compose exec kitchen alembic upgrade head

down:
	docker compose down -v

seed: ## menu, customers, staff, ovens and stations from config.yaml
	docker compose exec gateway python manage.py seed
	docker compose exec kitchen python -m kitchen.cli seed

demo: up seed ## up + seed + open the board — the one-command entry point
	@echo "make demo: board UI lands in Phase 8 — see PHASES.md"

sim: ## start the simulator at baseline rate — lands in Phase 6
	@echo "make sim: not implemented yet — see PHASES.md Phase 6"
	@exit 1

rush: ## trigger the friday_rush scenario — lands in Phase 6
	@echo "make rush: not implemented yet — see PHASES.md Phase 6"
	@exit 1

test: ## all Python tests, against real Postgres + Redis
	docker compose up -d --wait --wait-timeout 90 gateway-db kitchen-db redis
	POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0 \
		KITCHEN_POSTGRES_HOST=localhost KITCHEN_POSTGRES_PORT=5433 \
		uv run pytest

test-fe: ## vitest + Playwright visual regression
	cd apps/web && pnpm run test:unit
	cd apps/web && pnpm run test:storybook
	cd apps/web && pnpm exec playwright install --with-deps chromium
	cd apps/web && pnpm run test:visual

lint: ## ruff, mypy, stylelint, eslint, token + generated-client drift check
	uv run ruff check .
	uv run mypy
	cd services/gateway && uv run python manage.py spectacular --format openapi-json --file openapi.json --fail-on-warn
	git diff --exit-code -- services/gateway/openapi.json
	cd apps/web && pnpm run tokens:check
	cd apps/web && pnpm run api:check
	cd apps/web && pnpm run lint

storybook: ## design system — tokens, primitives, DINNER RUSH wordmark
	cd apps/web && pnpm run storybook

load: ## k6 run; writes docs/load/latest.json — lands in Phase 9
	@echo "make load: not implemented yet — see PHASES.md Phase 9"
	@exit 1
