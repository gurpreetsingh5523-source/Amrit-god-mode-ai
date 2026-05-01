# Core automation for development
.PHONY: test lint coverage precommit install-dev

test:
	.venv/bin/python -m pytest -v

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .

coverage:
	.venv/bin/python -m pytest --cov=. --cov-report=term-missing

precommit:
	pre-commit run --all-files

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt
