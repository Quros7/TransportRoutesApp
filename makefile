VENV ?= .venv
PYTHON_VERSION ?= 3.12
PROJECT_NAME ?= transport_routes_app

.PHONY: init clean pretty lint mypy ruff-lint test test-cov

.create-venv:
	test -d $(VENV) || python$(PYTHON_VERSION) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install poetry

.install-deps:
	$(VENV)/bin/poetry install --no-root

init:
	@echo "Creating virtual environment..."
	@$(MAKE) .create-venv
	@echo "Installing dependencies..."
	@$(MAKE) .install-deps

clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf dist
	rm -rf *.egg-info

pretty:
	$(VENV)/bin/ruff check --fix-only .
	$(VENV)/bin/ruff format .

ruff-lint:
	$(VENV)/bin/ruff check .

mypy:
	$(VENV)/bin/mypy .

lint: ruff-lint mypy

test:
	$(VENV)/bin/pytest ./tests

test-cov:
	$(VENV)/bin/pytest ./tests --cov-branch --cov-fail-under=70
