# Repository Guidelines

## Project Structure & Module Organization
Core packages live in `src/`: `src/api/routes` hosts FastAPI endpoints, `src/agents/<domain>` contains LangGraph agents, `src/models` houses SQLAlchemy tables, `src/schemas` Pydantic payloads, and shared utilities sit in `src/services` and `src/utils`. `src/config/settings.py` sources environment values from `.env`. Tests mirror the modules under `tests/` (notably `tests/test_agents`, `tests/test_api`, `tests/test_e2e`) with logs in `tests/logs/`. Operational helpers sit in `scripts/`, specification docs in `docs/`, and sample fixtures in `data/`.

## Build, Test, and Development Commands
- `python -m pip install -r requirements.txt` (or `uv sync`) installs dependencies declared in `pyproject.toml`.
- `python -m uvicorn src.main:app --reload` launches the development API.
- `python scripts/seed_data.py` seeds demo equities when Postgres is available; export `ENV=test` for the SQLite fallback.
- `pytest` runs the default suite; `pytest tests/test_agents/test_end_to_end.py -v` exercises the full HITL flow.
- `pytest --cov=src tests/` records coverage for release branches.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation, snake_case modules, and PascalCase classes such as `ResearchAgent`. Co-locate new nodes with their agent peers and expose orchestration changes through `src/agents/graph_master.py`. Apply type hints on public boundaries and prefer dependency injection over imports inside functions. Format with `black src/ tests/`, lint via `flake8`, and type-check with `mypy src/` as documented in `docs/completed/phase1/tech-stack-setup.md`.

## Testing Guidelines
`pytest` is configured in `pytest.ini` with async support and strict markers (`unit`, `integration`, `e2e`, `slow`, `performance`). Mirror source paths when authoring specs (e.g. `src/agents/trading` → `tests/test_agents/test_trading_*`). Use fixtures from `tests/conftest.py` or seed datasets via `scripts/seed_data.py`, keeping probabilistic logic deterministic for CI. Capture regressions with `pytest --cov` and share relevant files from `tests/logs/` in reviews.

## Commit & Pull Request Guidelines
Commits typically use Conventional-style prefixes (`Feat:`, `Fix:`, `Test:`); keep scopes tight and messages in the imperative mood. PRs should outline intent, list touched subsystems (agents, services, API), include proof of validation (`pytest`, local curl traces), and flag any configuration or schema changes. Request reviewers only after checks pass and secrets are scrubbed.

## Security & Configuration Tips
Secrets load through `.env` into `Settings`; never commit live API keys, KIS credentials, or DART tokens. Guard optional integrations (LangSmith, KIS) behind configuration toggles or mocks under `src/services` so the agents remain testable in offline environments.

## 커뮤니케이션 원칙
모든 사고 과정, 리뷰, 답변은 한국어로 작성합니다. 코드 주석 등 외부 시스템 제약이 있는 경우를 제외하고는 한국어 사용을 유지해 팀 간 컨텍스트를 일관되게 공유하세요.
