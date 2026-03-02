# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added validation in `check_agent_activity()` to verify `project_dir` exists and is a git repository (#23)
- Added warning logs when `_parse_positive_int()` receives invalid config values (#22)
- Added bootstrap rollback mechanism - on failure, started services are stopped (#19)
- Added `error` field to `check_agent_activity()` return value for better diagnostics

### Changed

- `_parse_positive_int()` now accepts optional `name` parameter for logging context
- Improved bootstrap error handling with service cleanup on failure

### Fixed

- Fixed ruff formatting in `test_cli.py` (#50)
- Fixed line length violations in `config.py`
- Fixed silent failures when `project_dir` doesn't exist or isn't a git repo

## [0.1.0] - 2026-03-01

### Added

- Initial release of Gasclaw
- Bootstrap sequence for starting Gastown + OpenClaw + KimiGas
- Health monitoring with activity compliance checks
- Key rotation pool for Gastown agents
- Telegram notifications for system status
- OpenClaw integration as overseer bot
- CLI commands: start, stop, status, update
- Comprehensive unit test suite
- Integration test suite

### Features

- **Bootstrap**: 12-step startup sequence orchestrating all subsystems
- **Health Checks**: Monitor Dolt, daemon, mayor, OpenClaw, and agent activity
- **Key Pool**: LRU key rotation with rate-limit cooldown
- **Activity Compliance**: Enforces code push/PR every hour
- **Telegram Integration**: Bot notifications for alerts and status
- **Skills System**: Auto-install OpenClaw skills on startup

[Unreleased]: https://github.com/gastown-publish/gasclaw/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/gastown-publish/gasclaw/releases/tag/v0.1.0
