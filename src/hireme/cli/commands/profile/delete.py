from typing import Annotated

import typer

from hireme.cli.commands.profile.common import (
    complete_profile_names,
    find_profile_dir_by_name,
    get_profile_names,
    set_profile,
)

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

    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if not profile_name:
        profiles_list: list[str] = get_profile_names()
        if not profiles_list:
            console.print("[yellow]No profiles available to delete.[/yellow]")
            raise typer.Exit()

        for index, name in enumerate(profiles_list, start=1):
            console.print(f"  {index}. {name}")
        selected = typer.prompt("Select a profile", type=int)
        if selected < 1 or selected > len(profiles_list):
            raise typer.BadParameter("Invalid profile selection.")
        profile_name = profiles_list[selected - 1]

    if (
        profile_name
        and profile_name.strip() != ""
        and profile_name.strip().lower() != "default"
    ):
        profile_dir = find_profile_dir_by_name(profile_name)
    else:
        console.print("[red]Cannot delete the default profile.[/red]")
        raise typer.Exit()

    if profile_dir is None or not profile_dir.exists():
        console.print(
            f"[yellow]Profile directory does not exist: {profile_name}[/yellow]"
        )
        raise typer.Exit()

    console.print(
        Panel(
            f"[bold yellow]⚠️  Warning:[/bold yellow] You are about to delete the profile [cyan]{profile_name}[/cyan]\n"
            f"[dim]Location: {profile_dir}[/dim]",
            title="[bold red]Delete Profile[/bold red]",
            border_style="red",
        )
    )
    force = typer.confirm("Are you sure you want to proceed?")
    if force:
        shutil.rmtree(profile_dir)
        console.print(
            Panel(
                f"[green]Deleted profile at: {profile_dir}[/green]",
                style="green",
            )
        )
        if find_profile_dir_by_name("default"):
            set_profile(profile="default")
            console.print("[green]Reverted to default profile.[/green]")
    else:
        console.print("[yellow]Deletion cancelled.[/yellow]")
