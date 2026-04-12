"""Google Agent Development Kit (ADK) runtime builder.

Validates Google ADK agent code, generates a Dockerfile, and prepares
the build context for containerized deployment.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from engine.config_parser import AgentConfig
from engine.runtimes.base import ContainerImage, RuntimeBuilder, RuntimeValidationResult, build_env_block

logger = logging.getLogger(__name__)

GOOGLE_ADK_SERVER_TEMPLATE = Path(__file__).parent / "templates" / "google_adk_server.py"

DOCKERFILE_TEMPLATE = """\
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY . .

# Google ADK uses Application Default Credentials (ADC).
# To authenticate, mount your service account key and set this env var:
#   ENV GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
# Or use Workload Identity when running on GCP (no key file needed).

# Non-root user for security
RUN useradd -m -r agent && chown -R agent:agent /app
USER agent

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
"""



class GoogleADKRuntime(RuntimeBuilder):
    """Runtime builder for Google Agent Development Kit (ADK) agents."""

    def validate(self, agent_dir: Path, config: AgentConfig) -> RuntimeValidationResult:
        errors: list[str] = []

        # Check for agent source file
        agent_file = agent_dir / "agent.py"
        if not agent_file.exists():
            errors.append(
                f"Missing agent.py in {agent_dir}. "
                "Google ADK agents must have an agent.py with a 'root_agent', 'agent', "
                "or 'app' variable (a google.adk.agents.Agent instance)."
            )

        # Check for requirements
        has_requirements = (agent_dir / "requirements.txt").exists()
        has_pyproject = (agent_dir / "pyproject.toml").exists()
        if not has_requirements and not has_pyproject:
            errors.append(
                "Missing requirements.txt or pyproject.toml. "
                "Add one with your agent's dependencies (must include google-adk)."
            )

        # Warn if GOOGLE_CLOUD_PROJECT is not referenced (non-fatal)
        if agent_file.exists():
            agent_source = agent_file.read_text()
            if "GOOGLE_CLOUD_PROJECT" not in agent_source:
                logger.warning(
                    "agent.py does not reference GOOGLE_CLOUD_PROJECT. "
                    "Set this environment variable for Google Cloud API access. "
                    "The server will fall back to 'agentbreeder-local' if unset."
                )

        return RuntimeValidationResult(valid=len(errors) == 0, errors=errors)

    def build(self, agent_dir: Path, config: AgentConfig) -> ContainerImage:
        """Generate Dockerfile and prepare build context."""
        # Create a temp build context
        build_dir = Path(tempfile.mkdtemp(prefix="agentbreeder-build-"))

        # Copy agent source code
        for item in agent_dir.iterdir():
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            dest = build_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__", ".git"))
            else:
                shutil.copy2(item, dest)

        # Ensure requirements.txt exists with framework deps
        requirements_file = build_dir / "requirements.txt"
        existing_requirements = ""
        if requirements_file.exists():
            existing_requirements = requirements_file.read_text()

        framework_deps = self.get_requirements(config)
        all_deps = set(existing_requirements.strip().splitlines()) | set(framework_deps)
        requirements_file.write_text("\n".join(sorted(all_deps)) + "\n")

        # Copy the server wrapper template
        if GOOGLE_ADK_SERVER_TEMPLATE.exists():
            shutil.copy2(GOOGLE_ADK_SERVER_TEMPLATE, build_dir / "server.py")

        # Write Dockerfile
        dockerfile = build_dir / "Dockerfile"
        env_block = build_env_block(config, "google_adk")
        dockerfile_content = DOCKERFILE_TEMPLATE.rstrip() + "\n\n# Agent configuration\n" + env_block + "\n"
        dockerfile.write_text(dockerfile_content)

        tag = f"agentbreeder/{config.name}:{config.version}"

        return ContainerImage(
            tag=tag,
            dockerfile_content=dockerfile_content,
            context_dir=build_dir,
        )

    def get_entrypoint(self, config: AgentConfig) -> str:
        return "uvicorn server:app --host 0.0.0.0 --port 8080"

    def get_requirements(self, config: AgentConfig) -> list[str]:
        return [
            "google-adk>=0.3.0",
            "google-generativeai>=0.8.0",
            "fastapi>=0.110.0",
            "uvicorn[standard]>=0.27.0",
            "httpx>=0.27.0",
            "pydantic>=2.0.0",
        ]
