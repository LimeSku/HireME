from typer.testing import CliRunner

from hireme.cli.main import app


def test_run_help_exposes_the_orchestrated_workflow() -> None:
    result = CliRunner().invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "start" in result.output
    assert "resume" in result.output
    assert "list" in result.output
    assert "show" in result.output
