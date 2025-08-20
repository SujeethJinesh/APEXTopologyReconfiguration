.PHONY: lint fmt test

lint:
	ruff check apex tests
	black --check apex tests

fmt:
	ruff check --fix apex tests
	isort apex tests
	black apex tests

test:
	pytest -q