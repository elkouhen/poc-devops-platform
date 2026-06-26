from __future__ import annotations

import os
import re
from pathlib import Path


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "y"}


def relpath(root: Path, path: Path) -> str:
    return os.path.relpath(path, root)


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    return re.sub(r"(^-+|-+$)", "", value)
