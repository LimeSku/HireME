from pathlib import Path
from typing import Annotated

import typer
from rich.progress import track

from hireme.cli.commands.profile.common import set_profile
from hireme.config import cfg

app = typer.Typer()


def populate_new_profile(
    profile_name: str | None = None, is_example: bool = False
) -> Path:
    """Populate a new profile directory with example or empty template files.

    Parameters
    ----------
    profile_name : str, optional
        Name of the profile to initialize, by default ""
    is_example: bool, optional
        Populate with example files or empty template, by default False

    Returns
    -------
    new_profile_path : Path
        Path to the newly created profile directory.

    Files created:
        - profile.yaml : Example structured profile file with personal info -> Required
        - context.md   : Example context note file, detailed background -> Highly recommended
        - attachements/ : Directory for additional files like resume.pdf, projects details or school program
    """
    template_profile_dir = (
        cfg.assets_dir
        / "profiles"
        / ("default_profile" if is_example else "empty_profile")
    )

    if not template_profile_dir.exists():
        raise FileNotFoundError(
            f"Template profile directory not found: {template_profile_dir}"
        )
    # target is the new profile dir, either default example
    target_dir = (
        cfg.profiles_dir / profile_name
        if profile_name
        else cfg.profiles_dir / "default"
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    template_files = list(template_profile_dir.iterdir())
    for _, item in track(
        enumerate(template_files),
        description="Copying profile files...",
        total=len(template_files),
    ):
        target_path = target_dir / item.name
        if item.is_dir():
            if not target_path.exists():
                target_path.mkdir()
            for sub_item in item.iterdir():
                sub_target_path = target_path / sub_item.name
                sub_target_path.write_bytes(sub_item.read_bytes())
        else:
            target_path.write_bytes(item.read_bytes())
    return target_dir


@app.command("new")
def create(
    profile_name: Annotated[
        str,
        typer.Argument(help="Name of the profile to create.", show_default=True),
    ] = "",
    is_example: bool = typer.Option(False, help="Populate with example files."),
):
    """Creates a new profile and populates it with example or empty template files."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    profiles_dir = cfg.profiles_dir
    if (
        profile_name
        and profile_name.strip() != ""
        and profile_name.strip().lower() != "default"
    ):
        profile_dir = profiles_dir / profile_name
    else:
        # default profile")
        default_profile_path = populate_new_profile(is_example=True)
        return default_profile_path

    if profile_dir.exists() and any(profile_dir.iterdir()):
        console.print(
            f"[yellow]Profile directory already exists and is not empty: {profile_dir.relative_to(cfg.project_root)}[/yellow]"
        )
        console.print("[yellow]Specify a different profile name.[/yellow]")
        raise typer.Exit()

    else:
        new_profile_path = populate_new_profile(profile_name, is_example=is_example)
        console.print(
            Panel(
                f"[green]Initialized new profile at: {new_profile_path.relative_to(cfg.project_root)}[/green]",
                style="green",
            )
        )
        set_default = typer.prompt(
            "Do you want to set this as the default profile? (y/n)", default="y"
        )
        if set_default.lower() in ("y", "yes"):
            set_profile(profile=profile_name)
            console.print(
                f"[green]Set profile '{profile_name}' as the default profile.[/green]"
            )
        return new_profile_path
