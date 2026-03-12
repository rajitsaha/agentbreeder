"""Basic Agent Garden SDK example.

Demonstrates the builder-pattern API for defining an agent, validating it,
exporting to YAML, and saving to disk.

Usage:
    python agent.py
"""

from agenthub import Agent, Tool

agent = (
    Agent("customer-support", version="1.0.0", team="support")
    .with_model(primary="claude-sonnet-4", fallback="gpt-4o")
    .with_prompt(system="You are a helpful customer support agent...")
    .with_tool(Tool.from_ref("tools/zendesk-mcp"))
    .with_tool(Tool.from_ref("tools/order-lookup"))
    .with_memory(backend="postgresql", max_messages=50)
    .with_guardrail("pii_detection")
    .with_guardrail("content_filter")
    .with_deploy(cloud="aws", runtime="ecs-fargate", region="us-east-1")
    .tag("support", "production")
)

if __name__ == "__main__":
    # Validate the agent config
    errors = agent.validate()
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("Agent is valid!")

    # Export as YAML
    print("\n--- agent.yaml ---")
    print(agent.to_yaml())

    # Save to file
    agent.save("agent.yaml")
    print("Saved to agent.yaml")
