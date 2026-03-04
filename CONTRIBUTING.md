# Contributing to Gasclaw

## Setup

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
python -m venv .venv
source .venv/bin/activate
make dev
```

## Development Workflow

Gasclaw follows **TDD (Test-Driven Development)**:

1. Write a failing test in `tests/unit/test_<module>.py`
2. Implement the code to make it pass
3. Run `make test` to verify
4. Never modify a test to make it pass — fix the code

## Testing

```bash
make test          # 1021 unit tests (no API keys needed)
make test-all      # Includes integration tests (needs running services)
make lint          # Ruff linting
make type-check    # mypy strict mode
```

All subprocess and HTTP calls are mocked in unit tests via `monkeypatch` and `respx`. No API keys or running services are needed for unit tests.

**Integration tests** (`tests/integration/`) require running services (Dolt, OpenClaw gateway) and are optional for PRs. Unit tests are sufficient.

## Mocking Patterns

```python
# Subprocess calls
monkeypatch.setattr("subprocess.run", mock_run)
# or
@patch("subprocess.run")

# HTTP calls
import respx
respx.get("http://localhost:18789/health").respond(200)

# File I/O
tmp_path  # pytest fixture for isolated file operations

# Environment variables
monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-test1:sk-test2")
monkeypatch.delenv("OPTIONAL_VAR", raising=False)
```

## Branch Naming

| Prefix | Use |
|--------|-----|
| `fix/` | Bug fixes |
| `feat/` | New features |
| `test/` | Test additions |
| `docs/` | Documentation |
| `refactor/` | Code restructuring |

## Commit Messages

Format: `<type>: <description>`

```
fix: resolve race condition in key rotation
feat: add forum topic routing for Telegram groups
docs: update Kimi proxy configuration guide
test: add coverage for edge cases in health checks
refactor: extract subprocess helpers into utils module
```

## Adding a New Module

1. Write tests in `tests/unit/test_<module>.py`
2. Implement in `src/gasclaw/<module>.py`
3. Run `make test` to verify
4. Add to bootstrap sequence if needed

## Adding a New Config Field

1. Add to `GasclawConfig` dataclass in `config.py`
2. Add env var parsing in `load_config()`
3. Add tests in `tests/unit/test_config.py`
4. Document in `.env.example` and docs

## Adding an OpenClaw Skill

1. Create `skills/<skill-name>/SKILL.md` with YAML frontmatter
2. Add scripts in `skills/<skill-name>/scripts/`
3. Make scripts executable (`chmod +x`)
4. Skills are auto-installed on `gasclaw start`

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/update_test_counts.py` | Auto-update test count references across docs |
| `scripts/validate-openclaw-config.sh` | Validate OpenClaw JSON config structure |

## PR Checklist

Before submitting:

- [ ] `make test` passes (all unit tests)
- [ ] `make lint` passes
- [ ] `make type-check` passes (mypy strict)
- [ ] New code has corresponding tests
- [ ] Commit messages follow `<type>: <description>` format

For full contributor guidelines, see [CLAUDE.md](CLAUDE.md).
