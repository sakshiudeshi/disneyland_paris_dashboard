.PHONY: install run test clean fetch-prices help

PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTEST := .venv/bin/pytest
STREAMLIT := .venv/bin/streamlit

help:
	@echo "Available targets:"
	@echo "  install       - Install all dependencies"
	@echo "  run           - Run the Streamlit dashboard"
	@echo "  test          - Run all tests"
	@echo "  fetch-prices  - Fetch latest prices from Disney API"
	@echo "  clean         - Remove generated files and cache"

install:
	$(PIP) install -r requirements.txt

run:
	$(STREAMLIT) run src/app.py

test:
	$(PYTEST) tests/ -v

fetch-prices:
	$(PYTHON) -m src.api.disney_api

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
