"""Profile management commands."""

import typer

from .create import app as create_app
from .delete import app as delete_app
from .setprofile import app as setprofile_app
from .show import app as show_app

app = typer.Typer(help="Manage user profile data.", no_args_is_help=True)
app.add_typer(create_app)
app.add_typer(delete_app)
app.add_typer(setprofile_app)
app.add_typer(show_app)
