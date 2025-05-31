.PHONY: help install install-dev clean lint format test test-coverage build upload upload-test check-version bump-patch bump-minor bump-major dev tag release pre-commit

SHELL := /bin/bash

PYTHON := python3
PIP := $(PYTHON) -m pip
VENV := venv
VENV_ACTIVATE := source $(VENV)/bin/activate

PACKAGE_NAME := tavor
VERSION_FILE := src/tavor/__version__.py
CURRENT_VERSION := $(shell grep -oE '[0-9]+\.[0-9]+\.[0-9]+' src/tavor/__init__.py | head -1)

BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo -e "${BLUE}Tavor Python SDK - Available Commands${NC}"
	@echo -e "${BLUE}=====================================${NC}"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  ${GREEN}%-15s${NC} %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

install: ## Install package in production mode
	$(PIP) install .

install-dev: ## Install package in development mode with all dependencies
	$(PIP) install -e ".[dev,async]"

venv: ## Create virtual environment
	$(PYTHON) -m venv $(VENV)
	@echo -e "${GREEN}Virtual environment created. Activate with: source $(VENV)/bin/activate${NC}"

clean: ## Clean build artifacts and cache
	rm -rf build/ dist/ *.egg-info
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache

lint: ## Run linting checks (ruff + mypy)
	@echo -e "${BLUE}Running ruff linter...${NC}"
	ruff check src/ tests/
	@echo -e "${BLUE}Running mypy type checker...${NC}"
	mypy src/ --ignore-missing-imports

format: ## Format code with ruff
	@echo -e "${BLUE}Formatting code with ruff...${NC}"
	ruff format src/ tests/ examples/
	@echo -e "${BLUE}Fixing lint issues with ruff...${NC}"
	ruff check --fix src/ tests/ examples/
	@echo -e "${GREEN}Code formatted successfully!${NC}"

test: ## Run tests
	@echo -e "${BLUE}Running tests...${NC}"
	pytest tests/ -v

test-coverage: ## Run tests with coverage report
	@echo -e "${BLUE}Running tests with coverage...${NC}"
	pytest tests/ -v --cov=src/tavor --cov-report=html --cov-report=term
	@echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"

check-version: ## Check current version
	@echo -e "${BLUE}Current version: ${GREEN}$(CURRENT_VERSION)${NC}"
	@echo -e "${BLUE}Checking version consistency...${NC}"
	@if grep -q "__version__ = \"$(CURRENT_VERSION)\"" src/tavor/__init__.py && \
	    grep -q "version = \"$(CURRENT_VERSION)\"" pyproject.toml; then \
		echo -e "${GREEN}✓ Version is consistent across files${NC}"; \
	else \
		echo -e "${RED}✗ Version mismatch detected!${NC}"; \
		echo "  __init__.py: $$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' src/tavor/__init__.py | head -1)"; \
		echo "  pyproject.toml: $$(grep -oE 'version = "[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"; \
		exit 1; \
	fi

bump-patch: ## Bump patch version (0.0.X)
	@$(MAKE) _bump TYPE=patch

bump-minor: ## Bump minor version (0.X.0)
	@$(MAKE) _bump TYPE=minor

bump-major: ## Bump major version (X.0.0)
	@$(MAKE) _bump TYPE=major

_bump:
	@echo -e "${BLUE}Bumping $(TYPE) version from $(CURRENT_VERSION)...${NC}"
	@NEW_VERSION=$$(python -c "v='$(CURRENT_VERSION)'.split('.'); major,minor,patch=int(v[0]),int(v[1]),int(v[2]); major,minor,patch=(major+1,0,0) if '$(TYPE)'=='major' else (major,minor+1,0) if '$(TYPE)'=='minor' else (major,minor,patch+1); print('{}.{}.{}'.format(major,minor,patch))"); \
	echo -e "${BLUE}New version: ${GREEN}$$NEW_VERSION${NC}"; \
	sed -i '' "s/__version__ = \"$(CURRENT_VERSION)\"/__version__ = \"$$NEW_VERSION\"/" src/tavor/__init__.py; \
	sed -i '' "s/version = \"$(CURRENT_VERSION)\"/version = \"$$NEW_VERSION\"/" pyproject.toml; \
	echo -e "${GREEN}✓ Version bumped to $$NEW_VERSION${NC}"

build: clean check-version ## Build distribution packages
	@echo -e "${BLUE}Building distribution packages...${NC}"
	$(PYTHON) -m build
	@echo -e "${GREEN}✓ Build complete! Packages in dist/${NC}"
	@ls -la dist/

upload-test: build ## Upload to TestPyPI
	@echo -e "${YELLOW}Uploading to TestPyPI...${NC}"
	$(PYTHON) -m twine upload --repository testpypi dist/*
	@echo -e "${GREEN}✓ Package uploaded to TestPyPI${NC}"
	@echo -e "${BLUE}Test installation with:${NC}"
	@echo "  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ $(PACKAGE_NAME)"

upload: build ## Upload to PyPI (production)
	@echo -e "${RED}⚠️  About to upload to production PyPI!${NC}"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo -e "${YELLOW}Uploading to PyPI...${NC}"; \
		$(PYTHON) -m twine upload dist/*; \
		echo -e "${GREEN}✓ Package uploaded to PyPI${NC}"; \
	else \
		echo -e "${YELLOW}Upload cancelled${NC}"; \
	fi

dev: install-dev ## Set up development environment
	@echo -e "${GREEN}✓ Development environment ready!${NC}"
	@echo -e "${BLUE}Run tests with:${NC} make test"
	@echo -e "${BLUE}Format code with:${NC} make format"
	@echo -e "${BLUE}Run linting with:${NC} make lint"

pre-commit: format lint test ## Run all checks before committing
	@echo -e "${GREEN}✓ All pre-commit checks passed!${NC}"

tag: ## Create and push a git tag for the current version
	@echo -e "${BLUE}Creating tag v$(CURRENT_VERSION)...${NC}"
	git tag -a v$(CURRENT_VERSION) -m "Release v$(CURRENT_VERSION)"
	@echo -e "${GREEN}✓ Tag created${NC}"
	@echo -e "${BLUE}Pushing tag to origin...${NC}"
	git push origin v$(CURRENT_VERSION)
	@echo -e "${GREEN}✓ Tag pushed successfully${NC}"

release: pre-commit check-version ## Full release process (test, build, tag, upload)
	@echo -e "${BLUE}Starting release process for version $(CURRENT_VERSION)...${NC}"
	@echo -e "${YELLOW}This will:${NC}"
	@echo "  1. Run all tests"
	@echo "  2. Build packages"
	@echo "  3. Create and push a git tag"
	@echo "  4. Upload to TestPyPI"
	@echo "  5. Optionally upload to PyPI"
	@read -p "Continue? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		$(MAKE) tag; \
		$(MAKE) upload-test; \
		echo -e "${YELLOW}Package uploaded to TestPyPI. Test it before uploading to PyPI.${NC}"; \
		read -p "Upload to PyPI now? (y/N) " -n 1 -r; \
		echo; \
		if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
			$(MAKE) upload; \
			echo -e "${GREEN}✓ Release complete!${NC}"; \
			echo -e "${YELLOW}Next steps:${NC}"; \
			echo "  1. Create a release on GitHub for v$(CURRENT_VERSION)"; \
			echo "  2. The package is now available on PyPI as $(PACKAGE_NAME)==$(CURRENT_VERSION)"; \
		fi; \
	fi