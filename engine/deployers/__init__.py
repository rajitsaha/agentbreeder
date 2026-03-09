"""Deployer registry.

Maps cloud types to their deployer implementations.
"""

from __future__ import annotations

from engine.config_parser import CloudType
from engine.deployers.base import BaseDeployer
from engine.deployers.docker_compose import DockerComposeDeployer

DEPLOYERS: dict[CloudType, type[BaseDeployer]] = {
    CloudType.local: DockerComposeDeployer,
    CloudType.kubernetes: DockerComposeDeployer,  # local K8s uses Docker Compose for M1
}


def get_deployer(cloud: CloudType) -> BaseDeployer:
    """Get the deployer for a given cloud target.

    Raises KeyError if the cloud target is not yet supported.
    """
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
