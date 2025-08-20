.PHONY: lint fmt test

lint:
	ruff check apex tests
	black --check apex tests

fmt:
	black apex tests
	ruff check --fix apex tests
	isort apex tests

test:
	pytest -q