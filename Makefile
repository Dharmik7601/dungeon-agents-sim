.DEFAULT_GOAL := help

LOG ?=
DIR ?= saved_logs/
RUNS ?= 10

.PHONY: help run batch viewer test lint format clean save analyze analyze-all streamlit

help:
	@echo "Usage:"
	@echo "  make run              Run the simulation (Ctrl+E to stop mid-run)"
	@echo "  make batch [RUNS=N]   Run the simulation N times in sequence (default: 10)"
	@echo "  make viewer LOG=<path> Replay a semantic log in the terminal"
	@echo "  make test             Run the full pytest test suite"
	@echo "  make lint             Lint with ruff"
	@echo "  make format           Format with ruff"
	@echo "  make clean            Delete all logs from the data/ directory"
	@echo "  make save LOG=<path>   Copy a log from data/ to saved_logs/"
	@echo "  make analyze LOG=<path> Print single-run analysis for a log file"
	@echo "  make analyze-all [DIR=<path>] Print cross-run analysis (default: saved_logs/)"
	@echo "  make streamlit        Launch the Streamlit observability dashboard"

run:
	python -m src.loop.run_simulation

batch:
	python -m src.loop.run_batch --runs $(RUNS)

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

analyze:
ifeq ($(LOG),)
	$(error LOG is required. Usage: make analyze LOG=data/run_<timestamp>.json)
endif
	python -m src.cli.single_run_analysis --log-file $(LOG)

analyze-all:
	python -m src.cli.cross_run_analysis --dir $(DIR)

streamlit:
	streamlit run src/cli/streamlit_app.py