from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .common import env_bool, slug
from .discover import find_kustomize_path, services_from_code, services_from_kustomization
from .errors import fail


@dataclass(frozen=True)
class InitProjectConfig:
    repo_root: Path
    apps_file: Path
    code_dir: Path
    iac_dir: Path
    app_name: str
    code_project_name: str
    iac_project_name: str
    kustomize_path: str
    services: list[str]
    has_preprod: bool
    domain: str
    registry_host: str
    gitlab_root_namespace: str
    apps_dir: Path


def load_config(argv: list[str]) -> InitProjectConfig:
    if len(argv) != 3:
        fail(f"Usage: {argv[0]} <code-repo> <iac-repo>")

    repo_root = Path(__file__).resolve().parents[2]
    apps_file = Path(os.environ.get("APPS_FILE", repo_root / "argocd/apps.yaml")).resolve()
    code_dir = Path(argv[1]).resolve()
    iac_dir = Path(argv[2]).resolve()

    require_git_repo(code_dir, "Depot code")
    require_git_repo(iac_dir, "Depot IaC")

    app_name = slug(os.environ.get("APP_NAME", code_dir.name))
    kustomize_path = os.environ.get("MANIFESTS_PATH") or find_kustomize_path(iac_dir)
    services = discover_services(code_dir, iac_dir, kustomize_path)

    return InitProjectConfig(
        repo_root=repo_root,
        apps_file=apps_file,
        code_dir=code_dir,
        iac_dir=iac_dir,
        app_name=app_name,
        code_project_name=os.environ.get("CODE_PROJECT_NAME", code_dir.name),
        iac_project_name=os.environ.get("IAC_PROJECT_NAME", iac_dir.name),
        kustomize_path=kustomize_path,
        services=services,
        has_preprod=env_bool("HAS_PREPROD", True),
        domain=os.environ.get("GITLAB_DOMAIN", "192.168.33.100.nip.io"),
        registry_host=os.environ.get("REGISTRY_HOST", "registry.registry.svc.cluster.local:5000"),
        gitlab_root_namespace=os.environ.get("GITLAB_ROOT_NAMESPACE", "root"),
        apps_dir=resolve_apps_dir(apps_file),
    )


def require_git_repo(path: Path, label: str) -> None:
    if not path.is_dir():
        fail(f"{label} introuvable: {path}")
    if not (path / ".git").is_dir():
        fail(f"{label} n'est pas un depot git: {path}")


def discover_services(code_dir: Path, iac_dir: Path, kustomize_path: str) -> list[str]:
    services = os.environ.get("SERVICES", "").split()
    if not services:
        services = services_from_kustomization(iac_dir, kustomize_path)
    if not services:
        services = services_from_code(code_dir)
    if not services:
        fail('Aucun service detecte: ajoute un Dockerfile par sous-dossier du depot code, ou passe SERVICES="svc-a svc-b"')
    return services


def resolve_apps_dir(apps_file: Path) -> Path:
    apps_dir = os.environ.get("APPS_DIR")
    if not apps_dir:
        apps_dir = read_apps_dir(apps_file)
    path = Path(apps_dir or "apps")
    if not path.is_absolute():
        path = apps_file.parent / path
    return path.resolve()


def read_apps_dir(apps_file: Path) -> str | None:
    if not apps_file.is_file():
        return None
    for line in apps_file.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("appsDir:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return None
