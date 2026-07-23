from typer.testing import CliRunner
from app.cli.main import app

runner = CliRunner()


def test_cli_root_help() -> None:
    """Verify that root cli --help works and exit code is 0."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "discover" in result.stdout
    assert "sync" in result.stdout
    assert "intelligence" in result.stdout
    assert "recommend" in result.stdout
    assert "apply" in result.stdout
    assert "monitor" in result.stdout
    assert "jobs" in result.stdout


def test_cli_discover_help() -> None:
    """Verify discover --help works and exit code is 0."""
    result = runner.invoke(app, ["discover", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout


def test_cli_sync_help() -> None:
    """Verify sync --help works and exit code is 0."""
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "provider" in result.stdout
    assert "status" in result.stdout
    assert "history" in result.stdout


def test_cli_intelligence_help() -> None:
    """Verify intelligence --help works and exit code is 0."""
    result = runner.invoke(app, ["intelligence", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "company" in result.stdout
    assert "summary" in result.stdout


def test_cli_recommend_help() -> None:
    """Verify recommend --help works and exit code is 0."""
    result = runner.invoke(app, ["recommend", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "resume" in result.stdout
    assert "top" in result.stdout


def test_cli_apply_help() -> None:
    """Verify apply --help works and exit code is 0."""
    result = runner.invoke(app, ["apply", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "prepare" in result.stdout
    assert "list" in result.stdout


def test_cli_monitor_help() -> None:
    """Verify monitor --help works and exit code is 0."""
    result = runner.invoke(app, ["monitor", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "run" in result.stdout
    assert "events" in result.stdout
    assert "alerts" in result.stdout


def test_cli_jobs_help() -> None:
    """Verify jobs --help works and exit code is 0."""
    result = runner.invoke(app, ["jobs", "--help"])
    assert result.exit_code == 0
    assert "Usage: " in result.stdout
    assert "list" in result.stdout
    assert "history" in result.stdout
