"""Gasclaw — Gastown + OpenClaw + KimiGas in one container.

A single-container deployment combining:
- Gastown: Multi-agent workspace with crew workers
- OpenClaw: Overseer bot for monitoring and control
- KimiGas: Kimi K2.5 LLM integration with key rotation

Example:
    >>> from gasclaw import load_config, bootstrap
    >>> config = load_config()
    >>> bootstrap(config)
"""

from __future__ import annotations

__version__ = "0.2.0"
__all__ = ["__version__"]
