.PHONY: up down ui seed reset demo sim rush test test-fe lint storybook load

up: ## bring the stack up; every container healthy in <90s
	@test -f config.yaml || cp config.example.yaml config.yaml
	docker compose up -d --build --wait --wait-timeout 90
	docker compose ps
	docker compose exec gateway python manage.py migrate
	docker compose exec kitchen alembic upgrade head
	docker compose exec dispatch alembic upgrade head

down:
	docker compose down -v

ui:
	cd apps/web && pnpm run dev

seed: ## menu, customers, staff, ovens, stations and couriers from config.yaml
	docker compose exec gateway python manage.py seed
	docker compose exec kitchen python -m kitchen.cli seed
	docker compose exec dispatch python -m dispatch.cli seed

reset: ## fast in-place reset for a fresh demo: clears orders/tickets/trips + the event spine; menu, customers and couriers are untouched, no restart needed
	docker compose exec gateway python manage.py reset
	docker compose exec kitchen python -m kitchen.cli reset
	docker compose exec dispatch python -m dispatch.cli reset
	@echo "make reset: fresh demo state — order codes restart at #1, ovens and couriers back to idle"

demo: up seed ## up + seed + open the board — the one-command entry point
	@echo "make demo: stack is up and seeded — run 'make ui' and open http://localhost:5173/board"
	@echo "sign in as manager/manager or kitchen/kitchen"

sim: ## start the simulator at baseline rate — runs until Ctrl-C / `docker compose stop`
	docker compose --profile simulator run --rm simulator python -m simulator.cli

rush: ## trigger the friday_rush scenario — runs for its duration_seconds, then stops
	docker compose --profile simulator run --rm simulator python -m simulator.cli --scenario friday_rush

test: ## all Python tests, against real Postgres + Redis — safe to run alongside a live `make demo`
	docker compose up -d --wait --wait-timeout 90 gateway-db kitchen-db dispatch-db redis
	POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0 \
		KITCHEN_POSTGRES_HOST=localhost KITCHEN_POSTGRES_PORT=5433 KITCHEN_POSTGRES_DB=kitchen_test \
		DISPATCH_POSTGRES_HOST=localhost DISPATCH_POSTGRES_PORT=5434 DISPATCH_POSTGRES_DB=dispatch_test \
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
	uv run python services/kitchen/scripts/export_openapi.py
	git diff --exit-code -- services/kitchen/openapi.json
	uv run python services/dispatch/scripts/export_openapi.py
	git diff --exit-code -- services/dispatch/openapi.json
	uv run python services/simulator/scripts/generate_client.py
	git diff --exit-code -- services/simulator/src/simulator/client/models.py
	cd apps/web && pnpm run tokens:check
	cd apps/web && pnpm run api:check
	cd apps/web && pnpm run lint

storybook: ## design system — tokens, primitives, DINNER RUSH wordmark
	cd apps/web && pnpm run storybook

load: ## k6 run; writes docs/load/latest.json — lands in Phase 9
	@echo "make load: not implemented yet — see PHASES.md Phase 9"
	@exit 1
