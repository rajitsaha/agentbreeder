"""AWS App Runner integration test.

Requires real AWS credentials and an existing ECR repository.

Setup:
    - AWS credentials in environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS_ACCOUNT_ID set in environment
    - ECR repository 'agentbreeder' created in target region

Run:
    RUN_AWS_INTEGRATION_TESTS=1 pytest tests/integration/test_aws_app_runner_integration.py -v -s
"""

from __future__ import annotations

import os

import pytest

SKIP_REASON = "Set RUN_AWS_INTEGRATION_TESTS=1 to run AWS integration tests"
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_AWS_INTEGRATION_TESTS") != "1",
    reason=SKIP_REASON,
)


@pytest.mark.asyncio
async def test_app_runner_full_deploy_and_teardown() -> None:
    """Deploy the langgraph example agent to App Runner, verify health, then tear down."""
    from pathlib import Path

    from engine.builder import DeployEngine
    from engine.config_parser import (
        AccessConfig,
        AgentConfig,
        CloudType,
        DeployConfig,
        FrameworkType,
        ModelConfig,
        ResourceConfig,
        ScalingConfig,
    )
    from engine.deployers.aws_app_runner import AWSAppRunnerDeployer
    from engine.runtimes import get_runtime

    account_id = os.environ["AWS_ACCOUNT_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")

    config = AgentConfig(
        name="agentbreeder-app-runner-integration-test",
        version="1.0.0",
        description="Integration test for App Runner deployer",
        team="engineering",
        owner="test@agentbreeder.dev",
        framework=FrameworkType.langgraph,
        model=ModelConfig(primary="claude-haiku-4-5-20251001"),
        deploy=DeployConfig(
            cloud=CloudType.aws,
            runtime="app-runner",
            region=region,
            scaling=ScalingConfig(min=1, max=1),
            resources=ResourceConfig(cpu="1", memory="2Gi"),
            env_vars={
                "AWS_ACCOUNT_ID": account_id,
                "AWS_REGION": region,
                "AWS_ECR_REPO": "agentbreeder",
                "LOG_LEVEL": "info",
            },
        ),
        access=AccessConfig(),
    )

    deployer = AWSAppRunnerDeployer()

    # 1. Provision (ensures ECR repo exists, sets up image URI)
    infra = await deployer.provision(config)
    assert infra.endpoint_url
    print(f"\nProvisioned App Runner infra. Image URI: {infra.resource_ids['image_uri']}")

    # 2. Build container image from examples/langgraph-agent
    agent_dir = Path("examples/langgraph-agent")
    runtime = get_runtime(config.framework)
    image = runtime.build(agent_dir, config)

    # 3. Deploy
    result = await deployer.deploy(config, image)
    assert result.status == "running"
    assert "awsapprunner.com" in result.endpoint_url
    print(f"Deployed to: {result.endpoint_url}")

    # 4. Health check
    health = await deployer.health_check(result)
    assert health.healthy, f"Health check failed: {health.checks}"
    print("Health check passed.")

    # 5. Logs
    logs = await deployer.get_logs(config.name)
    print(f"Logs ({len(logs)} entries): {logs[:3]}")

    # 6. Teardown
    await deployer.teardown(config.name)
    print("Teardown complete.")
