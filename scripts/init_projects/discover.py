from __future__ import annotations

import re
from pathlib import Path

from .common import relpath
from .errors import fail

KUSTOMIZATION_NAMES = ("kustomization.yaml", "kustomization.yml", "Kustomization")


def find_kustomize_path(iac_dir: Path) -> str:
    candidates = []
    for name in KUSTOMIZATION_NAMES:
        candidates.extend(iac_dir.rglob(name))
    if not candidates:
        fail(f"Aucun kustomization.yaml trouve dans {iac_dir}")
    selected = next((path for path in candidates if path.parent.name == "k8s"), None)
    selected = selected or min(candidates, key=lambda path: len(str(path)))
    return relpath(iac_dir, selected.parent)


def services_from_code(code_dir: Path) -> list[str]:
    services = []
    for child in sorted(code_dir.iterdir(), key=lambda path: path.name):
        if child.is_dir() and (child / "Dockerfile").is_file():
            services.append(child.name)
    return services


def services_from_kustomization(iac_dir: Path, kustomize_path: str) -> list[str]:
    kustomize_dir = iac_dir / kustomize_path
    file = next((kustomize_dir / name for name in KUSTOMIZATION_NAMES if (kustomize_dir / name).is_file()), None)
    if file is None:
        return []

    services: list[str] = []
    in_images = False
    current: dict[str, str] | None = None
    for raw_line in file.read_text().splitlines():
        line = raw_line.rstrip()
        if re.match(r"^images:\s*$", line):
            in_images = True
            current = None
            continue
        if in_images and re.match(r"^[A-Za-z0-9_][A-Za-z0-9_-]*:\s*", line):
            break
        if not in_images:
            continue

        item_match = re.match(r"^\s*-\s+([A-Za-z0-9_-]+):\s*(.+?)\s*$", line)
        if item_match:
            if current:
                add_service_from_image(services, current)
            current = {item_match.group(1): item_match.group(2)}
            continue
        field_match = re.match(r"^\s+([A-Za-z0-9_-]+):\s*(.+?)\s*$", line)
        if field_match and current is not None:
            current[field_match.group(1)] = field_match.group(2)

    if current:
        add_service_from_image(services, current)
    return services


def add_service_from_image(services: list[str], image: dict[str, str]) -> None:
    service = image.get("name") or image.get("newName", "").split("/")[-1]
    if service and service not in services:
        services.append(service)
