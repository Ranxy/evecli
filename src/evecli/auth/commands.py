"""EVE Online ESI Authentication CLI commands."""

import json

import click


@click.group()
def auth():
    """Manage EVE Online authentication."""


@auth.command()
@click.option("--client-id", prompt=True, help="EVE Online Application Client ID")
@click.option("--secret", prompt=True, hide_input=True, help="EVE Online Application Secret Key")
@click.option(
    "--mode",
    type=click.Choice(["browser", "manual"]),
    default="browser",
    show_default=True,
    help="Authentication mode. Use manual when the CLI runs on a remote server.",
)
@click.option(
    "--code",
    help="Authorization code or full callback URL returned by EVE SSO when using manual mode.",
)
@click.option(
    "--port",
    default=8088,
    show_default=True,
    type=int,
    help="Local callback port used in the registered redirect URI.",
)
def login(client_id: str, secret: str, mode: str, code: str | None, port: int):
    """Authenticate with EVE Online SSO via OAuth2."""
    from evecli.auth.sso import login_flow

    login_flow(client_id, secret, mode=mode, code=code, port=port)


@auth.command("status")
def status_cmd():
    """Show current authentication status."""
    from evecli.auth.token import TokenManager

    tm = TokenManager()
    click.echo(tm.get_status())


@auth.command()
def logout():
    """Remove stored authentication tokens."""
    from evecli.auth.token import TokenManager

    tm = TokenManager()
    if tm.remove_tokens():
        click.echo("Logged out. Tokens removed.")
    else:
        click.echo("No tokens found.")


@auth.command()
def character():
    """Show the currently authenticated character."""
    from evecli.auth.token import TokenManager

    tm = TokenManager()
    info = tm.get_character_info()
    if info:
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo("Not authenticated. Run 'evecli auth login' first.", err=True)
