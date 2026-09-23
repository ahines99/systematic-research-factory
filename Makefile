.PHONY: install lint test eval demo serve replay-check
install:      ; uv sync --locked --all-extras
lint:         ; uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy
test:         ; uv run pytest
eval:         ; uv run rsf eval --out var/scorecard.json
demo:         ; uv run rsf demo --out-dir var/reports --manifest var/demo_manifest.json
serve:        ; uv run rsf serve
