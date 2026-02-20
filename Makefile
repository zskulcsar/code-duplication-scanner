.PHONY: \
	help

# Python
PY_ROOT := $(CURDIR)
BE_SRC = $(PY_ROOT)/src
PYTHON_SRC_DIRS := $(PY_ROOT)/src tests

## Default
help: ## List available make targets with descriptions.
	@printf "Available targets:\n"
	@grep -hE '.*##\s' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"} {printf "  %-16s %s\n", $$1, $$2}'


## Environment management
venv: ## Create the python virtual environment and download all dependencies
# 	@test -d $(PY_ROOT)/.venv || uv venv  --directory $(PY_ROOT) --prompt lrt3-backend .venv
# 	@uv pip install --directory $(PY_ROOT) --python .venv --upgrade pip
	@uv sync --directory $(PY_ROOT)


## Basic code checkers
fmt-py: venv ## Run `ruff format` over Python sources
	@uv run ruff format $(PYTHON_SRC_DIRS)

lint-py: venv ## Run `ruff check` over Python sources. Pass `FIX=--FIX` to automatically fix the errors
	@PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache uv run ruff check $(PYTHON_SRC_DIRS) $(FIX)
#	@PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache uv run ruff check $(BE_SRC) $(FIX) --select D1,D2,D4

tc-py: venv ## Run `mypy` over Python sources
	@uv run mypy .

vc-py: venv ## Run `pip-audit` over Python dependencies
	@uv run --with pip-audit pip-audit

uv-pip-tree: ## Display the dependcy tree as seen by uv
	@uv pip tree

## TDD targets
test-py: test-unit-py ## Run all test suites

test-unit-py: venv ## Run unit test suites for Python code; extra params can be provided with PAR
	@PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache PYTHONPATH=$(BE_SRC) \
	uv run pytest --cov=$(BE_SRC) tests/unit $(PAR)

test-unit-suite: venv ## Run a unit test suite specified by TEST_SUITE; extra params can be provided with PAR
	@PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache PYTHONPATH=$(BE_SRC) \
	uv run pytest --cov=$(BE_SRC) tests/unit/test_$(TEST_SUITE).py $(PAR)

test-unit-case: ## Run a test case from a specific test suite specified by TEST_SUITE, TEST_CASE. TEST_FILE=manparsers TEST_CASE=mp001
	@PYTHONPATH=$(BE_SRC) PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache \
	uv run pytest -q tests/unit/test_$(TEST_SUITE).py -k $(TEST_CASE) $(PAR)

## Development targets
imp-verify: fmt-py lint-py tc-py test-unit-py ## Helper to run mandatory checks

run-cli: venv ## Run the CLI with parameters passed in ARGS (--command model-build)
	@PYTHONPATH=$(BE_SRC) PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache \
	uv run python -m cli.cli_verification_harness $(ARGS)

# run-exp: venv ## Ran any helper cli class via CLI=page_stats PAR="./tests/fixtures/templates/extraction/opinion/tmp-SOC2-TypeII-F01-opinion.json --pages 5"
# 	@PYTHONPATH=$(BE_SRC) PYTHONPYCACHEPREFIX=$(CURDIR)/.pycache \
# 	uv run python -m experiments.$(CLI) $(PAR)
