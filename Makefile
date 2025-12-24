# Makefile for DC-Area Techies Discovery Pipeline

# Use a virtual environment variable if set, otherwise assume active environment
PYTHON := python
CMD := bluesky_finder

.PHONY: help install discover fetch evaluate run-all export export-jsonl clean

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install the package in editable mode with dependencies
	uv sync

discover: ## Step 1: Run seed discovery (hashtags/anchors)
	$(CMD) discover

fetch: ## Step 2: Download profiles and recent posts for candidates
	$(CMD) fetch

evaluate: ## Step 3: Run LLM scoring on fetched candidates
	$(CMD) evaluate

run-all: ## Run the full pipeline (Discover -> Fetch -> Eval -> Export as HTML)
	$(CMD) run-all

export: ## Step 4: Export qualified candidates to HTML (default)
	$(CMD) export

export-jsonl: ## Export qualified candidates to JSONL format
	$(CMD) export --format jsonl