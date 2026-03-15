"""CrewAI starter — a sequential crew with researcher and writer agents.

Demonstrates:
- Defining agents with roles and backstories
- Creating tasks with expected outputs
- Sequential crew execution
- Agent Garden export pattern

Export the crew as `crew` — Agent Garden's server wrapper looks for this.
"""

from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool


@tool("Search")
def search(query: str) -> str:
    """Search the web for information on a given query.

    Args:
        query: The search query string.

    Returns:
        Search results as a formatted string.
    """
    # Placeholder — integrate with a real search API in production
    return (
        f"Search results for '{query}':\n"
        f"1. Key finding about {query}\n"
        f"2. Recent development in {query}\n"
        f"3. Expert analysis of {query}"
    )


@tool("WriteFile")
def write_file(filename: str, content: str) -> str:
    """Write content to a file.

    Args:
        filename: Name of the file to write.
        content: Content to write to the file.

    Returns:
        Confirmation message.
    """
    # Placeholder — in production, write to actual file or storage
    return f"Successfully wrote {len(content)} characters to {filename}"


# --- Agent definitions ---

researcher = Agent(
    role="Research Analyst",
    goal="Find accurate, comprehensive information on the given topic",
    backstory=(
        "You are an experienced research analyst with a talent for finding "
        "reliable information and identifying key trends. You always verify "
        "facts across multiple sources."
    ),
    tools=[search],
    verbose=True,
)

writer = Agent(
    role="Content Writer",
    goal="Produce clear, engaging, well-structured content based on research findings",
    backstory=(
        "You are a skilled content writer who transforms research into polished "
        "articles. You focus on clarity, accuracy, and reader engagement."
    ),
    tools=[write_file],
    verbose=True,
)

# --- Task definitions ---

research_task = Task(
    description=(
        "Research the topic '{topic}' thoroughly. Find key facts, recent developments, "
        "and expert opinions. Organize findings into a structured brief."
    ),
    expected_output=(
        "A research brief with: executive summary, key findings (bulleted), "
        "supporting data, and source references."
    ),
    agent=researcher,
)

writing_task = Task(
    description=(
        "Using the research brief, write a comprehensive article about '{topic}'. "
        "The article should be well-structured with an introduction, body sections, "
        "and conclusion."
    ),
    expected_output=(
        "A polished article (500-800 words) with clear headings, "
        "engaging prose, and cited sources."
    ),
    agent=writer,
)

# --- Build the crew ---

# Export as 'crew' — the Agent Garden server wrapper looks for this
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, writing_task],
    process=Process.sequential,
    verbose=True,
)


if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "the impact of AI agents on software development"})
    print(result)  # noqa: T201
