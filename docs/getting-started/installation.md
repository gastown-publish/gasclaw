# Installation

## Requirements

- Python 3.11+
- Git
- Dolt
- Gastown CLI (`gt`)
- OpenClaw CLI (`openclaw`)

## Install Dependencies

### 1. Clone the Repository

```bash
git clone https://github.com/gastown-publish/gasclaw.git
cd gasclaw
```

### 2. Set Up Python Environment

```bash
python -m venv .venv
source .venv/bin/activate

# Install in development mode
make dev
```

### 3. Install External Tools

Install Dolt, Gastown, and OpenClaw according to their respective documentation.

## Verify Installation

Run the test suite to verify everything is working:

```bash
make test
```

You should see all tests passing:

```
============================= test session starts ==============================
platform linux -- Python 3.13.12, pytest-9.0.2
collecting ... collected 408 items

tests/unit/... ............................................... [100%]

============================== 408 passed in 11s ==============================
```

## Development Mode

For development, install additional tools:

```bash
make dev        # Install dev dependencies
make lint       # Run ruff linting
make test       # Run unit tests
make test-all   # Run all tests including integration
```

## Next Steps

- [Configure environment variables](configuration.md)
- [Run your first bootstrap](quickstart.md)
