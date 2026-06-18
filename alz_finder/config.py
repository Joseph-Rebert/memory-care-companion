"""Load config.yaml and optional .env (no external dotenv dependency)."""
from __future__ import annotations

import os

import yaml

ROOT = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT, "config.yaml")
ENV_PATH = os.path.join(ROOT, ".env")


def load_env() -> None:
    """Minimal .env loader: KEY=VALUE lines into os.environ (won't overwrite)."""
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def load_config() -> dict:
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh)


def get_profile(cfg: dict, name: str) -> dict:
    profiles = cfg.get("profiles", {})
    if name not in profiles:
        raise KeyError(
            f"unknown profile '{name}'. Available: {', '.join(profiles)}"
        )
    return profiles[name]
