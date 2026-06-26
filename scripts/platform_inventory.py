from __future__ import annotations

import os
from pathlib import Path

import yaml


def default_apps_file() -> Path:
    return Path(__file__).parent.parent.resolve() / "argocd/apps.yaml"


def load_inventory(apps_file: Path | None = None) -> dict:
    inventory_path = (apps_file or Path(os.environ.get("APPS_FILE", default_apps_file()))).resolve()
    with open(inventory_path) as f:
        inventory = yaml.safe_load(f) or {}

    inline_apps = inventory.get("apps")
    if inline_apps is not None:
        return inventory

    apps_dir_value = os.environ.get("APPS_DIR") or inventory.get("appsDir", "apps")
    apps_dir = Path(apps_dir_value)
    if not apps_dir.is_absolute():
        apps_dir = inventory_path.parent / apps_dir

    apps = []
    for app_file in sorted(apps_dir.glob("*.yaml")):
        with open(app_file) as f:
            app = yaml.safe_load(f) or {}
        if app:
            apps.append(app)

    inventory["apps"] = apps
    return inventory
