.PHONY: setup test test-docker lint benchmark clean docker-build docker-up docker-down

# ── Development ─────────────────────────────────
setup:
	pip install -e ".[dev,server]"
	cd frontend && npm ci

test:
	pytest -v --tb=short --cov=infra_auditor --cov=aggregator

lint:
	python -m py_compile infra_auditor/cli.py
	python -m py_compile aggregator/app.py
	cd frontend && npx tsc --noEmit

benchmark:
	@echo "Running scan benchmark..."
	@time infra-auditor scan --role auto > /dev/null

# ── Docker ──────────────────────────────────────
docker-build:
	docker compose build

docker-up: docker-build
	docker compose up -d
	@echo "Waiting for services..."
	@sleep 5
	@echo "Stack is up → http://localhost:3000"

docker-down:
	docker compose down -v

docker-test: docker-up
	@sleep 10
	bash scripts/test-docker.sh
	$(MAKE) docker-down

# ── Cleanup ─────────────────────────────────────
clean:
	docker compose down -v --rmi local 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
