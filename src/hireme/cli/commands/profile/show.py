from pathlib import Path
from typing import Annotated

import typer

from hireme.config import cfg

app = typer.Typer()


@app.command("show")
def show_profile(
    profile_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Path to the profile directory to show."),
    ] = None,
):
    """Display a summary of the current profile data."""
    from rich import print_json
    from rich.console import Console, Group
    from rich.json import JSON
    from rich.panel import Panel

    from hireme.utils.common import load_yaml_content

    console = Console()

    if profile_dir is None:
        profile_dir = cfg.default_profile_dir

    if not profile_dir.exists() or not profile_dir.is_dir():
        console.print(f"[red]Profile directory does not exist: {profile_dir}[/red]")
        raise typer.Exit(code=1)

    _, profile = load_yaml_content(profile_dir / "profile.yaml")

    renderables = Group(
        f"[cyan][bold]Profile Directory: {profile_dir}[/bold][/cyan]\n",
        JSON.from_data(profile),
    )
    console.print(Panel(renderables, title="Profile Summary", style="green"))
