# Contributing to Gasclaw

## Setup

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
python -m venv .venv
source .venv/bin/activate
make dev
```

## Testing

```bash
make test          # Unit tests (no API keys needed)
make test-all      # All tests including integration
make lint          # Ruff linting
```

All external calls are mocked in unit tests. No API keys or running services needed.

## Adding a New Module

1. Write tests in `tests/unit/test_<module>.py`
2. Implement in `src/gasclaw/<module>.py`
3. Run `make test` to verify
4. Add to bootstrap sequence if needed

## Adding an OpenClaw Skill

1. Create `skills/<skill-name>/SKILL.md` with YAML frontmatter
2. Add scripts in `skills/<skill-name>/scripts/`
3. Make scripts executable (`chmod +x`)
4. Skills are auto-installed on `gasclaw start`
