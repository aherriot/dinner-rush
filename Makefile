.PHONY: up down seed demo sim rush test test-fe lint storybook load

up: ## bring the stack up; every container healthy in <90s
	docker compose up -d --build
	docker compose ps

down:
	docker compose down -v

seed: ## menu, customers, couriers, ovens from config.yaml — lands in Phase 2
	@echo "make seed: not implemented yet — see PHASES.md Phase 2"
	@exit 1

demo: up seed ## up + seed + open the board — the one-command entry point
	@echo "make demo: board UI lands in Phase 8 — see PHASES.md"

sim: ## start the simulator at baseline rate — lands in Phase 6
	@echo "make sim: not implemented yet — see PHASES.md Phase 6"
	@exit 1

rush: ## trigger the friday_rush scenario — lands in Phase 6
	@echo "make rush: not implemented yet — see PHASES.md Phase 6"
	@exit 1

test: ## all Python tests, against real Postgres + Redis
	docker compose up -d gateway-db redis
	POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0 uv run pytest

test-fe: ## vitest + Playwright visual regression
	cd apps/web && pnpm run test:unit
	cd apps/web && pnpm run test:storybook
	cd apps/web && pnpm exec playwright install --with-deps chromium
	cd apps/web && pnpm run test:visual

lint: ## ruff, mypy, stylelint, eslint, token build check
	uv run ruff check .
	uv run mypy
	cd apps/web && pnpm run tokens:check
	cd apps/web && pnpm run lint

storybook: ## design system — tokens, primitives, DINNER RUSH wordmark
	cd apps/web && pnpm run storybook

load: ## k6 run; writes docs/load/latest.json — lands in Phase 9
	@echo "make load: not implemented yet — see PHASES.md Phase 9"
	@exit 1
