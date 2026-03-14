# Repository Guidelines

## Project Structure & Module Organization

Core application code lives in `src/wapu_cli/`.
- `cli.py`: Click command tree and command handlers.
- `client.py`: HTTP client for the WapuPay backend.
- `config.py`: local config and credential resolution.
- `output.py`: JSON/table rendering helpers.
- `errors.py`: CLI-facing exceptions.

Tests live in `tests/`, with CLI coverage in `tests/test_cli.py`. Project metadata is in `pyproject.toml`; locked dependencies are in `uv.lock`. Keep user-specific files such as `.env` out of commits unless explicitly required.

## Build, Test, and Development Commands

Use `uv` for environment and dependency management:

```bash
uv venv
uv sync --dev
uv run wapu --help
uv run pytest
```

- `uv venv`: create the local virtual environment.
- `uv sync --dev`: install runtime and test dependencies from `pyproject.toml` / `uv.lock`.
- `uv run wapu ...`: run the CLI entrypoint.
- `uv run pytest`: run the full test suite.

## Coding Style & Naming Conventions

Target Python 3.10+ and follow standard PEP 8 style:
- 4-space indentation.
- `snake_case` for functions, variables, and modules.
- `PascalCase` for classes.
- Keep Click commands thin; put reusable logic in support modules.

No formatter or linter is configured yet, so keep changes small, readable, and consistent with existing code. Prefer explicit error messages and deterministic CLI behavior.

## Testing Guidelines

Tests use `pytest` plus `responses` for HTTP mocking and `click.testing.CliRunner` for command execution. Add at least one test per new command or backend integration path. Name test files `test_*.py` and test functions `test_<behavior>()`.

Prefer mocked backend tests for repeatability, and only use manual live-endpoint checks as a supplement.

## Commit & Pull Request Guidelines

Recent history uses short, imperative commit messages, for example:
- `Add WapuPay CLI MVP`
- `Remove build artifacts from repo`
- `docs: initial README for wapu-cli beta`

Follow that pattern: concise, imperative, and scoped to one logical change. PRs should include:
- a short summary of behavior changes
- test evidence (`uv run pytest`)
- any manual backend checks performed
- linked issue or spec when applicable

## Security & Configuration Tips

Never commit real credentials. The CLI stores tokens in `~/.config/wapu-cli/config.json`; treat that as sensitive. Prefer environment variables like `WAPU_API_KEY` or `WAPU_ACCESS_TOKEN` for ephemeral usage in scripts and CI.
