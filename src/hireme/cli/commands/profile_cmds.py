"""
Profile command for HireME CLI.
Manages user profile data including resumes and personal information.

Commands:
- init: Initialize a new profile directory with example files.
- load: Load and validate profile data from a specified directory.
- edit: Open profile files in the default editor.
- show: Display summary of the current profile data.
- validate: Validate the profile data for completeness and correctness.
- export: Export profile data to different formats.
"""

from pathlib import Path
from typing import Annotated

import typer

from hireme.config import cfg

app = typer.Typer(name="profile", help="Manage user profile data.")


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
        cfg.profiles_dir / profile_name if profile_name else cfg.default_profile_dir
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in template_profile_dir.iterdir():
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
        # default profile
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
            set_profile(profile_name=profile_name)
            console.print(
                f"[green]Set profile '{profile_name}' as the default profile.[/green]"
            )
        return new_profile_path


@app.command("delete")
def delete(
    profile_name: Annotated[
        str,
        typer.Argument(help="Name of the profile to delete."),
    ],
):
    """Deletes an existing profile and its data."""
    import shutil

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
        console.print("[red]Cannot delete the default profile.[/red]")
        raise typer.Exit()

    if not profile_dir.exists():
        console.print(
            f"[yellow]Profile directory does not exist: {profile_dir.relative_to(cfg.project_root)}[/yellow]"
        )
        raise typer.Exit()

    console.print(
        Panel(
            f"[bold yellow]⚠️  Warning:[/bold yellow] You are about to delete the profile [cyan]{profile_name}[/cyan]\n"
            f"[dim]Location: {profile_dir.relative_to(cfg.project_root)}[/dim]",
            title="[bold red]Delete Profile[/bold red]",
            border_style="red",
        )
    )
    force = typer.confirm("Are you sure you want to proceed?")
    if force:
        shutil.rmtree(profile_dir)
        console.print(
            Panel(
                f"[green]Deleted profile at: {profile_dir.relative_to(cfg.project_root)}[/green]",
                style="green",
            )
        )
        set_profile(profile_name="default")
        console.print(f"[green]Reverted to default profile.[/green]")
    else:
        console.print(f"[yellow]Deletion cancelled.[/yellow]")


@app.command()
def set_profile(
    # profile_dir: Path = typer.Argument(..., help="Path to the profile directory."),
    profile_name: Annotated[
        str | None,
        typer.Option(
            "--name", "-n", help="Name of the profile in the profiles directory."
        ),
    ] = None,
    profile_dir: Annotated[
        Path | None,
        typer.Option("--path", "-p", help="Direct path to the profile directory."),
    ] = None,
):
    """
    Set the default profile by updating the .env configuration file.
    """
    env_file = Path(".env")

    if profile_dir is None:
        if profile_name is None:
            typer.echo("You must provide a profile name or a path.")
            raise typer.Exit(code=1)
        profile_dir = cfg.profiles_dir / profile_name
    if not profile_dir.exists() or not profile_dir.is_dir():
        typer.echo(f"This profile does not exist or is not a directory: {profile_dir}")
        raise typer.Exit(code=1)
    # Prepare the line to write
    new_line = f"HIREME_DEFAULT_PROFILE_PATH={profile_dir}\n"

    lines = []
    if env_file.exists():
        # Read the existing file to avoid overwriting other configs
        with open(env_file, "r") as f:
            lines = f.readlines()

    # Check if the variable already exists to replace it
    variable_found = False
    with open(env_file, "w") as f:
        for line in lines:
            if line.startswith("HIREME_DEFAULT_PROFILE_PATH="):
                f.write(new_line)
                variable_found = True
            else:
                f.write(line)

        # If it didn't exist, add it at the end
        if not variable_found:
            f.write(new_line)

    typer.echo(f"Configuration saved! The profile is now: {profile_dir.stem}")

    # def load_yaml_profile(profile_dir: Path) -> dict:
    """Load and parse the profile.yaml file from the profile directory.

    Args:
        profile_dir: Path to the profile directory.
    Returns:
        Parsed profile data as a dictionary.
    """
    # from hireme.utils.common import load_yaml_content

    # profile_yaml_path = profile_dir / "profile.yaml"
    # if not profile_yaml_path.exists():
    #     raise FileNotFoundError(f"Profile file not found: {profile_yaml_path}")

    # profile_data = load_yaml_content(profile_yaml_path)
    # return profile_data


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
