from pathlib import Path
from typing import Annotated

import typer

from hireme.cli.commands.profile.common import set_profile
from hireme.config import cfg

app = typer.Typer()


@app.command("set")
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
    set_profile(
        profile_name=profile_name,
        profile_dir=profile_dir,
    )

    # env_file = Path(".env")

    # if profile_dir is None:
    #     if profile_name is None:
    #         typer.echo("You must provide a profile name or a path.")
    #         raise typer.Exit(code=1)
    #     profile_dir = cfg.profiles_dir / profile_name
    # if not profile_dir.exists() or not profile_dir.is_dir():
    #     typer.echo(f"This profile does not exist or is not a directory: {profile_dir}")
    #     raise typer.Exit(code=1)
    # # Prepare the line to write
    # new_line = f"HIREME_DEFAULT_PROFILE_PATH={profile_dir}\n"

    # lines = []
    # if env_file.exists():
    #     # Read the existing file to avoid overwriting other configs
    #     with open(env_file, "r") as f:
    #         lines = f.readlines()

    # # Check if the variable already exists to replace it
    # variable_found = False
    # with open(env_file, "w") as f:
    #     for line in lines:
    #         if line.startswith("HIREME_DEFAULT_PROFILE_PATH="):
    #             f.write(new_line)
    #             variable_found = True
    #         else:
    #             f.write(line)

    #     # If it didn't exist, add it at the end
    #     if not variable_found:
    #         f.write(new_line)

    # typer.echo(f"Configuration saved! The profile is now: {profile_dir.stem}")
