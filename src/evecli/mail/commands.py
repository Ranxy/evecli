"""EVE Online ESI Mail CLI commands."""

import json
from typing import Optional

import click
import httpx


ESI_BASE = "https://esi.evetech.net/latest"


def _get_access_token() -> str:
    """Get valid access token or exit."""
    from evecli.auth.token import TokenManager

    tm = TokenManager()
    token = tm.get_access_token()
    if not token:
        click.echo("Not authenticated. Run 'evecli auth login' first.", err=True)
        raise SystemExit(1)
    return token


def _get_character_id() -> int:
    from evecli.auth.token import TokenManager

    tm = TokenManager()
    cid = tm.get_character_id()
    if not cid:
        click.echo("Character ID not found. Re-authenticate with 'evecli auth login'.", err=True)
        raise SystemExit(1)
    return cid


def _output(data, format: str = "json"):
    """Output data in requested format."""
    if format == "json":
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, list):
            for item in data:
                _format_plain(item)
                click.echo("---")
        else:
            _format_plain(data)


def _format_plain(item: dict):
    """Format a single mail item for plain text output."""
    for key, value in item.items():
        display_key = key.replace("_", " ").title()
        if isinstance(value, list):
            click.echo(f"  {display_key}: {', '.join(str(v) for v in value)}")
        else:
            click.echo(f"  {display_key}: {value}")
    click.echo()


@click.group()
def mail():
    """Manage EVE Online mail."""
    pass


@mail.command()
@click.option("--limit", default=50, show_default=True, help="Number of mails to fetch")
@click.option("--offset", default=0, show_default=True, help="Offset for pagination")
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def list(limit: int, offset: int, format: str):
    """List recent mails."""
    token = _get_access_token()
    char_id = _get_character_id()

    url = f"{ESI_BASE}/characters/{char_id}/mail/"
    params = {"limit": limit}
    if offset:
        params["offset"] = offset  # type: ignore

    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    if resp.status_code != 200:
        click.echo(f"ESI error {resp.status_code}: {resp.text}", err=True)
        raise SystemExit(1)

    mails = resp.json()
    _output(mails, format)


@mail.command()
@click.argument("mail_id", type=int)
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def read(mail_id: int, format: str):
    """Read a single mail by ID."""
    token = _get_access_token()
    char_id = _get_character_id()

    resp = httpx.get(
        f"{ESI_BASE}/characters/{char_id}/mail/{mail_id}/",
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        click.echo(f"ESI error {resp.status_code}: {resp.text}", err=True)
        raise SystemExit(1)

    _output(resp.json(), format)


@mail.command()
@click.option("--to", required=True, multiple=True, help="Recipient character ID (can specify multiple)")
@click.option("--subject", required=True, help="Mail subject")
@click.option("--body", required=True, help="Mail body (supports HTML)")
@click.option("--mailing-list", type=int, help="Mailing list ID (conflicts with --to)")
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def send(to: tuple[int, ...], subject: str, body: str, mailing_list: Optional[int], format: str):
    """Send a new mail."""
    token = _get_access_token()
    char_id = _get_character_id()

    recipients = []
    if mailing_list:
        recipients.append({"mailing_list_id": mailing_list})
    else:
        for rec_id in to:
            recipients.append({"recipient_id": int(rec_id)})

    payload = {
        "recipients": recipients,
        "subject": subject,
        "body": body,
    }

    resp = httpx.post(
        f"{ESI_BASE}/characters/{char_id}/mail/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    if resp.status_code != 201:
        click.echo(f"ESI error {resp.status_code}: {resp.text}", err=True)
        raise SystemExit(1)

    result = {"status": "sent", "mail_id": resp.headers.get("X-Mail-ID")}
    _output(result, format)


@mail.command()
@click.argument("mail_ids", nargs=-1, required=True, type=int)
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def delete(mail_ids: tuple[int, ...], format: str):
    """Delete one or more mails."""
    token = _get_access_token()
    char_id = _get_character_id()

    results = []
    for mail_id in mail_ids:
        resp = httpx.delete(
            f"{ESI_BASE}/characters/{char_id}/mail/{mail_id}/",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 204:
            results.append({"mail_id": mail_id, "status": "failed", "error": resp.text})
        else:
            results.append({"mail_id": mail_id, "status": "deleted"})

    _output(results, format)


@mail.command("label")
@click.option(
    "--action",
    type=click.Choice(["list", "create", "delete"]),
    default="list",
    help="Action to perform",
)
@click.option("--name", help="Label name (for create)")
@click.option("--label-id", type=int, help="Label ID (for delete)")
@click.option("--color", default="#ffffff", help="Label color hex (for create)")
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def label_cmd(action: str, name: Optional[str], label_id: Optional[int], color: str, format: str):
    """Manage mail labels."""
    token = _get_access_token()
    char_id = _get_character_id()

    if action == "list":
        resp = httpx.get(
            f"{ESI_BASE}/characters/{char_id}/mail/labels/",
            headers={"Authorization": f"Bearer {token}"},
        )
    elif action == "create":
        if not name:
            click.echo("--name required for create action", err=True)
            raise SystemExit(1)
        resp = httpx.post(
            f"{ESI_BASE}/characters/{char_id}/mail/labels/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"label": name, "color": color},
        )
    elif action == "delete":
        if not label_id:
            click.echo("--label-id required for delete action", err=True)
            raise SystemExit(1)
        resp = httpx.delete(
            f"{ESI_BASE}/characters/{char_id}/mail/labels/{label_id}/",
            headers={"Authorization": f"Bearer {token}"},
        )
    else:
        click.echo(f"Unknown action: {action}", err=True)
        raise SystemExit(1)

    if resp.status_code not in (200, 201, 204):
        click.echo(f"ESI error {resp.status_code}: {resp.text}", err=True)
        raise SystemExit(1)

    if resp.status_code == 204:
        _output({"status": "ok"}, format)
    else:
        _output(resp.json(), format)


@mail.command()
@click.argument("mail_id", type=int)
@click.option("--read/--unread", default=None, help="Mark as read or unread")
@click.option("--label", type=int, help="Add/remove a label ID")
@click.option("--format", type=click.Choice(["json", "plain"]), default="json", help="Output format")
def update(mail_id: int, read: Optional[bool], label: Optional[int], format: str):
    """Update mail metadata (read status, labels)."""
    token = _get_access_token()
    char_id = _get_character_id()

    payload = {}
    if read is not None:
        payload["read"] = read
    if label is not None:
        payload["labels"] = [label]

    if not payload:
        click.echo("Provide at least --read/--unread or --label", err=True)
        raise SystemExit(1)

    resp = httpx.put(
        f"{ESI_BASE}/characters/{char_id}/mail/{mail_id}/",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    if resp.status_code != 204:
        click.echo(f"ESI error {resp.status_code}: {resp.text}", err=True)
        raise SystemExit(1)

    _output({"status": "updated", "mail_id": mail_id}, format)
