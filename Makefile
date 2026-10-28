.PHONY: setup setup-data test lint
setup:
	python -m pip install -e ".[dev]"

setup-data:
	python -m pip install -e ".[dev,data]"

test:
	python -m pytest -q

lint:
	python -m ruff check .
