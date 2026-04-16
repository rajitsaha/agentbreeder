"""Base interface for cloud-specific deployers.

Every cloud target implements this interface.
Cloud-specific logic MUST stay inside engine/deployers/ — never leak it elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from engine.config_parser import AgentConfig
from engine.runtimes.base import ContainerImage


class InfraResult(BaseModel):
    """Result of provisioning cloud infrastructure."""

    endpoint_url: str
    resource_ids: dict[str, str]


class DeployResult(BaseModel):
    """Result of deploying an agent."""

    endpoint_url: str
    container_id: str
    status: str
    agent_name: str
    version: str


class HealthStatus(BaseModel):
    """Result of a health check."""

    healthy: bool
    checks: dict[str, bool]


class BaseDeployer(ABC):
    """Abstract base class for cloud-specific deployers.

    Each cloud target (AWS ECS, GCP Cloud Run, local Docker Compose, etc.)
    implements this to handle infrastructure provisioning and agent deployment.
    """

    @abstractmethod
    async def provision(self, config: AgentConfig) -> InfraResult:
        """Provision cloud infrastructure for the agent."""
        ...

    @abstractmethod
    async def deploy(self, config: AgentConfig, image: ContainerImage | None) -> DeployResult:
        """Build and deploy the agent container."""
        ...

    @abstractmethod
    async def health_check(self, deploy_result: DeployResult) -> HealthStatus:
        """Verify the deployed agent is healthy."""
        ...

    @abstractmethod
    async def teardown(self, agent_name: str) -> None:
        """Remove a deployed agent and clean up resources."""
        ...

    @abstractmethod
    async def get_logs(self, agent_name: str, since: datetime | None = None) -> list[str]:
        """Retrieve logs from a deployed agent."""
        ...
