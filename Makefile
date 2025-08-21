.PHONY: lint fmt test

lint:
	ruff check apex tests
	black --check apex tests

fmt:
	ruff check --fix apex tests
	isort apex tests
	black apex tests

test:
	@if [ -n "$$ARTIFACTS_DIR" ]; then \
		mkdir -p "$$ARTIFACTS_DIR"; \
		python3 -c 'import json, platform, subprocess, sys, os; ver = lambda cmd: subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True).strip() if True else ""; info = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(), "pytest": ver("pytest --version"), "ruff": ver("ruff --version"), "black": ver("black --version")}; json.dump(info, open(os.path.join(os.environ["ARTIFACTS_DIR"], "env.json"), "w"), indent=2)'; \
		pytest -q --junitxml "$$ARTIFACTS_DIR/junit.xml" | tee "$$ARTIFACTS_DIR/pytest_stdout.txt"; \
	else \
		pytest -q; \
	fi