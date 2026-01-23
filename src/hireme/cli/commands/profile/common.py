from pathlib import Path
from typing import Annotated

import typer

from hireme.config import cfg


def get_profile_names() -> list[str]:
    profiles_dir = cfg.profiles_dir
    if not profiles_dir.exists() or not profiles_dir.is_dir():
        return []
    profile_names = [p.name for p in profiles_dir.iterdir() if p.is_dir()]
    return profile_names


def complete_profile_names(incomplete: str) -> list[str]:
    profiles_dir = cfg.profiles_dir
    if not profiles_dir.exists() or not profiles_dir.is_dir():
        return []
    profile_names = [
        p.name
        for p in profiles_dir.iterdir()
        if p.is_dir() and p.name.startswith(incomplete)
    ]
    return profile_names


def find_profile_dir_by_name(profile_name: str) -> Path | None:
    profiles_dir = cfg.profiles_dir
    profile_dir = profiles_dir / profile_name
    if profile_dir.exists() and profile_dir.is_dir():
        return profile_dir
    return None


def set_profile(
    profile: Path | str | None = None,
):
    env_file = Path(".env")
    profile_dir: Path | None = None
    if isinstance(profile, str):
        profile_dir = find_profile_dir_by_name(profile)
    elif isinstance(profile, Path):
        profile_dir = profile

    if profile is None:
        typer.echo("You must provide a profile name or a path.")
        raise typer.Exit(code=1)

    if profile_dir is None or not profile_dir.exists() or not profile_dir.is_dir():
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
