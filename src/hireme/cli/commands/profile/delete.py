from pathlib import Path
from typing import Annotated

import typer

from hireme.cli.commands.profile.common import (
    complete_profile_names,
    get_profile_names,
    set_profile,
)
from hireme.config import cfg

app = typer.Typer()


@app.command("delete")
def delete(
    profile_name: Annotated[
        str | None,
        typer.Option(
            # None,
            ...,
            "--name",
            "-n",
            help="Name of the profile to delete.",
            autocompletion=complete_profile_names,
        ),
    ] = None,
):
    """Deletes an existing profile and its data."""
    import shutil

    from beaupy import select
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    profiles_dir = cfg.profiles_dir
    if not profile_name:
        profiles_list: list[str] = get_profile_names()
        if not profiles_list:
            console.print("[yellow]No profiles available to delete.[/yellow]")
            raise typer.Exit()

        selected_profile = select(profiles_list, return_index=False)
        if selected_profile is None:
            console.print("[yellow]No profile selected. Exiting.[/yellow]")
            raise typer.Exit()
        if isinstance(selected_profile, str):
            profile_name = selected_profile

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
        set_profile(profile="default")
        console.print(f"[green]Reverted to default profile.[/green]")
    else:
        console.print(f"[yellow]Deletion cancelled.[/yellow]")
