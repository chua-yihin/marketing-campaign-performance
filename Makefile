.PHONY: all extract analyze report test lint

# `make all` runs from the committed parquet extracts and needs no GCP access.
all: analyze report test

# Queries BigQuery (dry run + 20 GB cap per query) and rewrites data/processed/*.parquet.
extract:
	uv run python -m campaign_perf.extract

analyze:
	uv run python -m campaign_perf.analyze

report:
	uv run python -m campaign_perf.report

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
