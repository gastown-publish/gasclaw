.PHONY: install dev test test-unit test-all lint format clean docker docker-run

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test: test-unit

test-unit:
	python -m pytest tests/unit -v

test-all:
	python -m pytest tests/ -v

lint:
	ruff check src/ tests/

type-check:
	python -m mypy src/gasclaw --ignore-missing-imports

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker:
	docker build -t gasclaw .

docker-run:
	docker run --env-file .env -v ./project:/project -p 18789:18789 gasclaw
