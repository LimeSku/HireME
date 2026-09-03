import re
from pathlib import Path

import typer
from rich.console import Console

from hireme.config import cfg

PROFILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_profile_name(profile_name: str) -> str:
    if not PROFILE_NAME_PATTERN.fullmatch(profile_name):
        raise ValueError(
            "Profile names must use 1-64 ASCII letters, digits, underscores or hyphens."
        )
    return profile_name


def profile_dir_for_name(profile_name: str) -> Path:
    validate_profile_name(profile_name)
    root = cfg.profiles_dir.resolve()
    profile_dir = (root / profile_name).resolve()
    if not profile_dir.is_relative_to(root):
        raise ValueError("Profile path must remain inside the profiles directory.")
    return profile_dir


def get_profile_names() -> list[str]:
    if not cfg.profiles_dir.is_dir():
        return []
    return sorted(path.name for path in cfg.profiles_dir.iterdir() if path.is_dir())


def complete_profile_names(incomplete: str) -> list[str]:
    return [name for name in get_profile_names() if name.startswith(incomplete)]


def find_profile_dir_by_name(profile_name: str) -> Path | None:
    try:
        profile_dir = profile_dir_for_name(profile_name)
    except ValueError:
        return None
    return profile_dir if profile_dir.is_dir() else None


def validate_profile(profile: str | Path | None) -> Path:
    if profile is None:
        raise typer.BadParameter("Provide a profile name or path.")
    profile_dir = (
        find_profile_dir_by_name(profile) if isinstance(profile, str) else profile
    )
    if profile_dir is None or not profile_dir.is_dir():
        raise typer.BadParameter(f"Profile directory does not exist: {profile_dir}")
    return profile_dir


def select_profile(console: Console) -> str:
    profile_names = get_profile_names()
    if not profile_names:
        raise typer.BadParameter("No profiles found. Run 'hireme profile new' first.")

    default_name = cfg.default_profile_dir.name
    default_index = (
        profile_names.index(default_name) + 1 if default_name in profile_names else 1
    )
    for index, name in enumerate(profile_names, start=1):
        console.print(f"  {index}. {name}")
    selected = typer.prompt("Select a profile", type=int, default=default_index)
    if selected < 1 or selected > len(profile_names):
        raise typer.BadParameter("Invalid profile selection.")
    return profile_names[selected - 1]


def set_profile(profile: Path | str | None = None) -> None:
    profile_dir = validate_profile(profile).resolve()
    env_file = Path.cwd() / ".env"
    new_line = f"HIREME_DEFAULT_PROFILE_PATH={profile_dir}\n"
    lines = (
        env_file.read_text(encoding="utf-8").splitlines(keepends=True)
        if env_file.exists()
        else []
    )

    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("HIREME_DEFAULT_PROFILE_PATH="):
            updated.append(new_line)
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        if updated and not updated[-1].endswith("\n"):
            updated[-1] += "\n"
        updated.append(new_line)

    temporary = env_file.with_name(f".{env_file.name}.tmp")
    temporary.write_text("".join(updated), encoding="utf-8")
    temporary.replace(env_file)
    typer.echo(f"Configuration saved. Default profile: {profile_dir.name}")
