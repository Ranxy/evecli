"""EVE Online ESI CLI entry point."""

import click

from evecli.auth.commands import auth
from evecli.mail.commands import mail


@click.group()
@click.version_option(version="0.1.0")
def main():
    """EVE Online ESI CLI - Manage your EVE Online game data."""
    pass


main.add_command(auth)
main.add_command(mail)


if __name__ == "__main__":
    main()
