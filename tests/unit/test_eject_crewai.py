"""Tests for CrewAI eject scaffold."""

import yaml

_BASE_YAML = (
    "name: test-agent\nversion: 1.0.0\nframework: crewai\n"
    "description: A test agent\nteam: eng\nowner: a@b.com\n"
    "model:\n  primary: gpt-4o\ndeploy:\n  cloud: aws\n"
)

_NO_DESC_YAML = (
    "name: test-agent\nversion: 1.0.0\nframework: crewai\n"
    "team: eng\nowner: a@b.com\n"
    "model:\n  primary: gpt-4o\ndeploy:\n  cloud: aws\n"
)


def test_to_class_name_simple():
    from cli.commands.eject import _to_class_name

    assert _to_class_name("my-agent") == "MyAgent"


def test_to_class_name_underscores():
    from cli.commands.eject import _to_class_name

    assert _to_class_name("customer_support") == "CustomerSupport"


def test_to_class_name_single_word():
    from cli.commands.eject import _to_class_name

    assert _to_class_name("agent") == "Agent"


def test_to_class_name_mixed():
    from cli.commands.eject import _to_class_name

    assert _to_class_name("my-customer_agent") == "MyCustomerAgent"


def test_generate_crewai_writes_crew_py(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    crew_py = (tmp_path / "crew.py").read_text()
    assert "CrewBase" in crew_py
    assert "TestAgent" in crew_py  # _to_class_name("test-agent")


def test_generate_crewai_writes_agents_yaml(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    agents_yaml = yaml.safe_load((tmp_path / "config" / "agents.yaml").read_text())
    assert "primary_agent" in agents_yaml


def test_generate_crewai_writes_tasks_yaml(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    tasks_yaml = yaml.safe_load((tmp_path / "config" / "tasks.yaml").read_text())
    assert "primary_task" in tasks_yaml


def test_generate_crewai_writes_requirements(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    reqs = (tmp_path / "requirements.txt").read_text()
    assert "crewai" in reqs


def test_generate_crewai_no_description_fallback(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    # Should not raise even without description
    _generate_crewai_scaffold(_NO_DESC_YAML, tmp_path)
    assert (tmp_path / "crew.py").exists()


def test_generate_crewai_creates_config_dir(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    assert (tmp_path / "config").is_dir()


def test_generate_crewai_crew_py_has_task_decorator(tmp_path):
    from cli.commands.eject import _generate_crewai_scaffold

    _generate_crewai_scaffold(_BASE_YAML, tmp_path)
    crew_py = (tmp_path / "crew.py").read_text()
    assert "@task" in crew_py
    assert "@agent" in crew_py
    assert "@crew" in crew_py
