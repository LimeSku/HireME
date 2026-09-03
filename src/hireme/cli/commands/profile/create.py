import shutil
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from hireme.cli.commands.profile.common import (
    profile_dir_for_name,
    set_profile,
    validate_profile_name,
)
from hireme.config import cfg

app = typer.Typer()


def populate_new_profile(
    profile_name: str | None = None, is_example: bool = False
) -> Path:
    name = validate_profile_name(profile_name or "default")
    template = (
        cfg.assets_dir
        / "profiles"
        / ("default_profile" if is_example else "empty_profile")
    )
    if not template.is_dir():
        raise FileNotFoundError(f"Profile template not found: {template}")

    cfg.ensure_directories()
    target = profile_dir_for_name(name)
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Profile already exists and is not empty: {target}")
    shutil.copytree(template, target, dirs_exist_ok=True)
    return target


@app.command("new")
def create(
    profile_name: Annotated[
        str,
        typer.Argument(help="Name of the profile to create."),
    ] = "default",
    is_example: Annotated[
        bool,
        typer.Option("--example", help="Populate with the example candidate."),
    ] = False,
) -> None:
    """Create a candidate profile from a packaged template."""
    console = Console()
    try:
        profile_dir = populate_new_profile(
            profile_name,
            is_example=is_example or profile_name.lower() == "default",
        )
    except (ValueError, FileExistsError) as error:
        raise typer.BadParameter(str(error)) from error

    console.print(Panel(f"[green]Created profile: {profile_dir}[/green]"))
    if profile_name != "default" and typer.confirm(
        "Set this profile as default?", default=True
    ):
        set_profile(profile_name)
