.PHONY: help install dev lint format type-check test check clean run

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make dev          - Install development dependencies"
	@echo "  make lint         - Run ruff linter"
	@echo "  make format       - Format code with ruff"
	@echo "  make type-check   - Run type checking with ty"
	@echo "  make test         - Run tests with pytest"
	@echo "  make check        - Run all non-mutating checks"
	@echo "  make clean        - Remove cache and build files"
	@echo "  make run          - Run the application"

install:
	uv sync --no-dev
	uv run --no-dev playwright install chromium

dev:
	uv sync --group dev
	uv run playwright install chromium

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

type-check:
	uv run ty check

test:
	uv run pytest

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check
	uv run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	uv run hireme
