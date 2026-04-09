.DEFAULT_GOAL := help

LOG ?=

.PHONY: help run viewer test lint format clean save

help:
	@echo "Usage:"
	@echo "  make run              Run the simulation (Ctrl+E to stop mid-run)"
	@echo "  make viewer LOG=<path> Replay a semantic log in the terminal"
	@echo "  make test             Run the full pytest test suite"
	@echo "  make lint             Lint with ruff"
	@echo "  make format           Format with ruff"
	@echo "  make clean            Delete all logs from the data/ directory"
	@echo "  make save LOG=<path>   Copy a log from data/ to saved_logs/"

run:
	python -m src.loop.run_simulation

viewer:
ifeq ($(LOG),)
	$(error LOG is required. Usage: make viewer LOG=data/run_<timestamp>.json)
endif
	python -m src.cli.diagnostic_viewer --log-file $(LOG)

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

clean:
	@echo "Deleting all logs in data/..."
	@python -c "import glob, os; [os.remove(f) for f in glob.glob('data/run_*.json')]"
	@echo "Done."

save:
ifeq ($(LOG),)
	$(error LOG is required. Usage: make save LOG=data/run_<timestamp>.json)
endif
	@python -c "import os; os.makedirs('saved_logs', exist_ok=True)"
	@python -c "import shutil; shutil.copy('$(LOG)', 'saved_logs/')"
	@echo "Saved $(LOG) -> saved_logs/"