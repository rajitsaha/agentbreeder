"""Tests for cli/commands/compliance.py."""

from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from cli.commands.compliance import _build_report_locally, _parse_since, compliance_app

runner = CliRunner()


class TestParseSince:
    def test_parse_days(self) -> None:
        result = _parse_since("90d")
        assert (date.today() - result).days == 90

    def test_parse_months(self) -> None:
        result = _parse_since("6m")
        delta = (date.today() - result).days
        assert 170 <= delta <= 190

    def test_parse_years(self) -> None:
        result = _parse_since("1y")
        assert result.year == date.today().year - 1

    def test_parse_strips_whitespace(self) -> None:
        result = _parse_since("  30d  ")
        assert (date.today() - result).days == 30

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises((typer.BadParameter, ValueError)):
            _parse_since("invalid")

    def test_parse_bad_format_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter):
            _parse_since("abc")

    def test_parse_30d(self) -> None:
        result = _parse_since("30d")
        assert (date.today() - result).days == 30


class TestBuildReportLocally:
    def test_returns_dict_with_required_keys(self) -> None:
        result = _build_report_locally("soc2", None, date(2024, 1, 1), date(2024, 12, 31))
        assert result["standard"] == "soc2"
        assert result["period_start"] == "2024-01-01"
        assert result["period_end"] == "2024-12-31"
        assert "sections" in result
        assert "summary" in result

    def test_team_filtering_passed_through(self) -> None:
        result = _build_report_locally("gdpr", "engineering", date(2024, 1, 1), date(2024, 6, 30))
        assert result["team"] == "engineering"

    def test_fallback_when_api_not_importable(self) -> None:
        import sys
        from unittest.mock import patch

        with patch.dict(sys.modules, {"api.routes.compliance": None}):
            result = _build_report_locally("hipaa", None, date(2024, 1, 1), date(2024, 12, 31))
        assert result["standard"] == "hipaa"
        assert result["sections"] == {}
        assert "data_note" in result["summary"]

    def test_all_supported_standards(self) -> None:
        for std in ["soc2", "hipaa", "gdpr", "iso27001"]:
            result = _build_report_locally(std, None, date(2024, 1, 1), date(2024, 12, 31))
            assert result["standard"] == std


class TestExportCommand:
    def test_export_to_stdout(self) -> None:
        result = runner.invoke(compliance_app, ["export", "--standard", "soc2"])
        assert result.exit_code == 0
        assert "soc2" in result.output

    def test_export_invalid_standard_exits_1(self) -> None:
        result = runner.invoke(compliance_app, ["export", "--standard", "unknown"])
        assert result.exit_code == 1

    def test_export_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.json"
            result = runner.invoke(
                compliance_app, ["export", "--standard", "gdpr", "--output", str(out)]
            )
            assert result.exit_code == 0
            assert out.exists()
            data = json.loads(out.read_text())
            assert data["standard"] == "gdpr"

    def test_export_with_team_filter(self) -> None:
        result = runner.invoke(
            compliance_app,
            ["export", "--standard", "soc2", "--team", "platform"],
        )
        assert result.exit_code == 0

    def test_export_with_since_flag(self) -> None:
        result = runner.invoke(
            compliance_app,
            ["export", "--standard", "hipaa", "--since", "30d"],
        )
        assert result.exit_code == 0

    def test_export_unsupported_format_falls_back(self) -> None:
        result = runner.invoke(
            compliance_app,
            ["export", "--standard", "soc2", "--format", "xml"],
        )
        assert result.exit_code == 0

    def test_export_invalid_since_exits_1(self) -> None:
        result = runner.invoke(
            compliance_app,
            ["export", "--standard", "soc2", "--since", "bad-value"],
        )
        assert result.exit_code == 1


class TestListStandards:
    def test_list_standards_shows_all_four(self) -> None:
        result = runner.invoke(compliance_app, ["list-standards"])
        assert result.exit_code == 0
        for std in ["soc2", "hipaa", "gdpr", "iso27001"]:
            assert std in result.output

    def test_list_standards_shows_labels(self) -> None:
        result = runner.invoke(compliance_app, ["list-standards"])
        assert "SOC 2" in result.output
        assert "HIPAA" in result.output
        assert "GDPR" in result.output
        assert "ISO" in result.output
