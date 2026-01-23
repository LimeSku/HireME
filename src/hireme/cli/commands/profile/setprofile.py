from pathlib import Path
from typing import Annotated

import typer

from hireme.cli.commands.profile.common import set_profile
from hireme.config import cfg

app = typer.Typer()


@app.command("set")
def set(
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

    if profile_name is not None and profile_dir is not None:
        typer.echo("Please provide either a profile name or a path, not both.")
        raise typer.Exit(code=1)

    if profile_name is not None:
        set_profile(
            profile=profile_name,
        )
    elif profile_dir is not None:
        set_profile(
            profile=profile_dir,
        )
    else:
        typer.echo("You must provide a profile name or a path.")
        raise typer.Exit(code=1)
