.PHONY: setup setup-data test lint
PYTHON ?= python

setup:
	$(PYTHON) -m pip install -r conf/requirements-mvp.lock -e ".[mvp]"

setup-data:
	$(PYTHON) -m pip install -e ".[dev,data]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
