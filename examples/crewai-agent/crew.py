"""CrewAI research-writer crew example.

Two agents work together:
  - Researcher: searches for information on a given topic.
  - Writer: turns the researcher's findings into a concise report.

The `crew` variable is the entry point that AgentBreeder picks up at runtime.
"""

from __future__ import annotations

from crewai import Agent, Crew, Task

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

researcher = Agent(
    role="Senior Researcher",
    goal="Uncover accurate and up-to-date facts on the given topic",
    backstory=(
        "You are an experienced research analyst with a talent for finding "
        "reliable information quickly. You always cite sources and flag uncertainty."
    ),
    verbose=True,
)

writer = Agent(
    role="Content Writer",
    goal="Produce a clear, engaging report from the researcher's findings",
    backstory=(
        "You are a skilled technical writer who can distil complex research "
        "into concise, readable summaries for a general audience."
    ),
    verbose=True,
)

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

research_task = Task(
    description=(
        "Research the following topic thoroughly: {topic}. "
        "Provide key facts, recent developments, and any important caveats."
    ),
    expected_output="A bullet-point summary of findings with source notes.",
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the researcher's findings, write a concise report (3–5 paragraphs) "
        "on: {topic}. The report should be factual, engaging, and suitable for "
        "a general audience."
    ),
    expected_output="A polished written report of 3–5 paragraphs.",
    agent=writer,
    context=[research_task],
)

# ---------------------------------------------------------------------------
# Crew — this is what AgentBreeder loads at runtime
# ---------------------------------------------------------------------------

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    verbose=True,
)
