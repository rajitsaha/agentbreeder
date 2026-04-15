"""Deployer registry.

Maps cloud types to their deployer implementations.
"""

from __future__ import annotations

from engine.config_parser import CloudType
from engine.deployers.aws_app_runner import AWSAppRunnerDeployer
from engine.deployers.aws_ecs import AWSECSDeployer
from engine.deployers.azure_container_apps import AzureContainerAppsDeployer
from engine.deployers.base import BaseDeployer
from engine.deployers.claude_managed import ClaudeManagedDeployer
from engine.deployers.docker_compose import DockerComposeDeployer
from engine.deployers.gcp_cloudrun import GCPCloudRunDeployer
from engine.deployers.kubernetes import KubernetesDeployer

DEPLOYERS: dict[CloudType, type[BaseDeployer]] = {
    CloudType.local: DockerComposeDeployer,
    CloudType.aws: AWSECSDeployer,
    CloudType.azure: AzureContainerAppsDeployer,
    CloudType.gcp: GCPCloudRunDeployer,
    CloudType.kubernetes: KubernetesDeployer,
    CloudType.claude_managed: ClaudeManagedDeployer,
}

# Maps runtime strings (from deploy.runtime) to deployer classes.
RUNTIME_DEPLOYERS: dict[str, type[BaseDeployer]] = {
    "cloud-run": GCPCloudRunDeployer,
    "cloudrun": GCPCloudRunDeployer,
    "ecs-fargate": AWSECSDeployer,
    "ecs": AWSECSDeployer,
    "app-runner": AWSAppRunnerDeployer,
    "apprunner": AWSAppRunnerDeployer,
    "container-apps": AzureContainerAppsDeployer,
    "eks": KubernetesDeployer,
    "gke": KubernetesDeployer,
    "aks": KubernetesDeployer,
}


def get_deployer(cloud: CloudType, runtime: str | None = None) -> BaseDeployer:
    """Get the deployer for a given cloud target and optional runtime.

    If runtime is specified and matches a known deployer, use that.
    Otherwise fall back to the default deployer for the cloud type.
    Raises KeyError if the cloud target is not yet supported.
    """
    # Check runtime-specific deployer first
    if runtime:
        runtime_key = runtime.lower().strip()
        deployer_cls = RUNTIME_DEPLOYERS.get(runtime_key)
        if deployer_cls is not None:
            return deployer_cls()

    deployer_cls = DEPLOYERS.get(cloud)
    if deployer_cls is None:
        supported = ", ".join(d.value for d in DEPLOYERS)
        msg = (
            f"Cloud target '{cloud.value}' is not yet supported. "
            f"Supported targets: {supported}. "
            f"See CONTRIBUTING.md for how to add a new deployer."
        )
        raise KeyError(msg)
    return deployer_cls()
