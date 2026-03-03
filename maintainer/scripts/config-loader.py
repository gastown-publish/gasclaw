#!/usr/bin/env python3
"""Gasclaw config loader — reads YAML config with env var overlay."""

import argparse
import json
import os
import sys

try:
    import yaml
except ImportError:
    yaml = None

CONFIG_PATH = os.environ.get("GASCLAW_CONFIG", "/workspace/config/gasclaw.yaml")

DEFAULTS = {
    "maintenance": {
        "loop_interval": 300,
        "max_pr_size": 200,
        "auto_merge": True,
        "repo": "gastown-publish/gasclaw",
        "working_dir": "/workspace/gasclaw",
        "branch_prefixes": ["fix/", "feat/", "test/", "docs/", "refactor/"],
    },
    "claude": {
        "kimi_base_url": "https://api.kimi.com/coding/",
        "dangerously_skip_permissions": True,
    },
    "openclaw": {
        "gateway_port": 18789,
    },
    "logging": {
        "level": "INFO",
        "log_dir": "/workspace/logs",
    },
}


def deep_merge(base, override):
    """Merge override into base (override wins)."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(path=None):
    """Load config from YAML file, falling back to defaults."""
    path = path or CONFIG_PATH
    config = DEFAULTS.copy()

    if os.path.exists(path):
        with open(path) as f:
            if yaml:
                file_config = yaml.safe_load(f) or {}
            else:
                # Minimal YAML-like parsing for simple key: value files
                file_config = _parse_simple_yaml(f.read())
        config = deep_merge(config, file_config)

    return config


def _parse_simple_yaml(text):
    """Fallback parser for simple YAML (no PyYAML)."""
    result = {}
    current_section = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            result[current_section] = {}
        elif current_section and ":" in stripped:
            key, _, val = stripped.partition(":")
            val = val.strip().strip('"').strip("'")
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.isdigit():
                val = int(val)
            result[current_section][key.strip()] = val
    return result


def get_nested(config, key_path):
    """Get a value by dot-notation path (e.g., 'maintenance.loop_interval')."""
    keys = key_path.split(".")
    val = config
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return None
    return val


def set_nested(config, key_path, value):
    """Set a value by dot-notation path."""
    keys = key_path.split(".")
    d = config
    for k in keys[:-1]:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    # Type coercion
    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        else:
            try:
                value = int(value)
            except ValueError:
                pass
    d[keys[-1]] = value
    return config


def save_config(config, path=None):
    """Save config back to YAML file."""
    path = path or CONFIG_PATH
    if yaml:
        with open(path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    else:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)


def mask_value(key, val):
    """Mask secret-looking values."""
    secret_keys = {"api_key", "token", "secret", "password"}
    if any(s in key.lower() for s in secret_keys) and isinstance(val, str) and len(val) > 8:
        return val[:4] + "****" + val[-4:]
    return val


def view_config(config, prefix=""):
    """Pretty-print config with secret masking."""
    lines = []
    for key, val in config.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            lines.append(f"{full_key}:")
            lines.extend(view_config(val, full_key))
        else:
            lines.append(f"  {full_key}: {mask_value(full_key, val)}")
    return lines


def shell_export(config, prefix="GASCLAW"):
    """Output export KEY=VALUE lines for bash sourcing."""
    lines = []
    for key, val in config.items():
        if isinstance(val, dict):
            lines.extend(shell_export(val, f"{prefix}_{key.upper()}"))
        else:
            env_key = f"{prefix}_{key.upper()}"
            lines.append(f'export {env_key}="{val}"')
    return lines


def main():
    parser = argparse.ArgumentParser(description="Gasclaw config loader")
    parser.add_argument("--config", default=CONFIG_PATH, help="Config file path")
    parser.add_argument("--get", metavar="KEY", help="Get value by dot-notation key")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set value")
    parser.add_argument("--view", action="store_true", help="Pretty-print config")
    parser.add_argument("--shell-export", action="store_true", help="Output bash exports")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--validate", action="store_true", help="Validate config")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.get:
        val = get_nested(config, args.get)
        if val is None:
            print(f"Key not found: {args.get}", file=sys.stderr)
            sys.exit(1)
        print(val)
    elif args.set:
        config = set_nested(config, args.set[0], args.set[1])
        save_config(config, args.config)
        print(f"Set {args.set[0]} = {args.set[1]}")
    elif args.view:
        for line in view_config(config):
            print(line)
    elif args.shell_export:
        for line in shell_export(config):
            print(line)
    elif args.validate:
        required = ["maintenance.repo", "maintenance.working_dir"]
        ok = True
        for key in required:
            if get_nested(config, key) is None:
                print(f"MISSING: {key}", file=sys.stderr)
                ok = False
        if ok:
            print("Config valid")
        sys.exit(0 if ok else 1)
    elif args.json:
        print(json.dumps(config, indent=2))
    else:
        print(json.dumps(config, indent=2))


if __name__ == "__main__":
    main()
