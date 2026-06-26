from __future__ import annotations

import os
import re

from .common import relpath
from .config import InitProjectConfig
from .inventory import read_internal_gitlab_host


def build_app(config: InitProjectConfig) -> dict:
    internal_gitlab_host = read_internal_gitlab_host(config.apps_file)
    iac_project_path = f"{config.gitlab_root_namespace}/{config.iac_project_name}"
    code_project_path = f"{config.gitlab_root_namespace}/{config.code_project_name}"
    repo_url = f"http://{internal_gitlab_host}/{iac_project_path}.git"
    env_specs = environment_specs(config.has_preprod)

    return {
        "name": config.app_name,
        "hasPreprod": config.has_preprod,
        "showcaseService": showcase_service(config.services),
        "manifests": {
            "projectPath": iac_project_path,
            "projectName": config.iac_project_name,
            "sourceDir": relpath(config.repo_root, config.iac_dir),
            "repoURL": repo_url,
            "mainPushAccessLevel": 40,
            "argocdSecretName": f"gitlab-{config.app_name}-iac-repo",
            "path": config.kustomize_path,
        },
        "code": {
            "projectPath": code_project_path,
            "projectName": config.code_project_name,
            "sourceDir": relpath(config.repo_root, config.code_dir),
            "mainPushAccessLevel": 0,
        },
        "services": [
            {"name": service, "image": f"{config.registry_host}/{service}"}
            for service in config.services
        ],
        "environments": [
            environment(config.app_name, name, branch, config.services, config.domain)
            for name, branch in env_specs
        ],
        "argocd": {
            "project": config.app_name,
            "sourceRepos": [repo_url],
            "destinations": [
                {
                    "server": "https://kubernetes.default.svc",
                    "namespace": f"{config.app_name}{'' if name == 'prod' else '-' + name}",
                }
                for name, _branch in env_specs
            ],
        },
    }


def environment_specs(has_preprod: bool) -> list[tuple[str, str]]:
    env_specs = [("dev", "dev"), ("rec", "rec")]
    if has_preprod:
        env_specs.append(("preprod", "preprod"))
    env_specs.append(("prod", "main"))
    return env_specs


def environment(app_name: str, env_name: str, branch: str, services: list[str], domain: str) -> dict:
    suffix = "" if env_name == "prod" else f"-{env_name}"
    env_services = []
    for service in services:
        host = f"{service}.{domain}" if env_name == "prod" else f"{service}-{env_name}.{domain}"
        env_services.append({"name": service, "url": f"http://{host}", "ingressHost": host})
    return {
        "name": env_name,
        "branch": branch,
        "namespace": f"{app_name}{suffix}",
        "services": env_services,
    }


def showcase_service(services: list[str]) -> str:
    explicit = os.environ.get("SHOWCASE_SERVICE")
    if explicit:
        return explicit
    for service in services:
        if re.search(r"(gui|ui|web|front|frontend)$", service):
            return service
    return services[0]
