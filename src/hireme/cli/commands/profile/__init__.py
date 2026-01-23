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

# from pathlib import Path
# from typing import Annotated

import typer

# from hireme.config import cfg
from .create import app as create_app
from .delete import app as delete_app
from .setprofile import app as setprofile_app
from .show import app as show_app

# app = typer.Typer(name="profile", help="Manage user profile data.")
app = typer.Typer(help="Manage user profile data.")
app.add_typer(create_app)  # , name="create", help="Create a new profile.")
app.add_typer(delete_app)  # , name="delete", help="Delete an existing profile.")
app.add_typer(setprofile_app)  # , name="set", help="Set the active profile.")
app.add_typer(show_app)
