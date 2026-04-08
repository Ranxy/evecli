"""EVE Online SSO OAuth2 flow."""

import base64
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser
from typing import Optional

import httpx

from evecli.auth.token import SSO_TOKEN, TOKEN_FILE, TokenManager

EVE_SCOPES = [
    "esi-mail.read_mail.v1",
    "esi-mail.send_mail.v1",
    "publicData",
]


def _basic_auth(client_id: str, secret: str) -> str:
    """Return Basic auth header value for SSO."""
    credentials = f"{client_id}:{secret}"
    return base64.b64encode(credentials.encode()).decode()


def login_flow(client_id: str, secret: str, port: int = 8088) -> None:
    """Run the full OAuth2 login flow with local redirect."""
    import click

    redirect_uri = f"http://127.0.0.1:{port}/callback"
    state = secrets.token_urlsafe(32)
    auth_url = (
        "https://login.eveonline.com/v2/oauth/authorize/"
        f"?response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&client_id={client_id}"
        f"&scope={'+'.join(EVE_SCOPES)}"
        f"&state={state}"
    )

    click.echo("\nPlease open the following URL in your browser to authenticate:")
    click.echo(f"\033[1;34m{auth_url}\033[0m")
    click.echo()

    code_event = threading.Event()
    auth_code: list[str] = [None]  # type: ignore

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
            if code:
                auth_code[0] = code
                code_event.set()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authentication successful! You can close this tab.</h1>"
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Authentication failed.</h1>")

        def log_message(self, format, *args):
            pass  # suppress logs

    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Try to open browser, but URL is already printed above for manual copy
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    click.echo("Waiting for authentication callback (5 min timeout)...")

    # Wait for callback
    success = code_event.wait(timeout=300)  # 5 min
    server.shutdown()

    if not success or not auth_code[0]:
        click.echo("Authentication timed out or failed.", err=True)
        raise SystemExit(1)

    click.echo("\nGot authorization code. Exchanging for tokens...")

    headers = {"Authorization": f"Basic {_basic_auth(client_id, secret)}"}
    resp = httpx.post(
        SSO_TOKEN,
        headers=headers,
        data={"grant_type": "authorization_code", "code": auth_code[0]},
    )
    if resp.status_code != 200:
        click.echo(f"Token exchange failed: {resp.text}", err=True)
        raise SystemExit(1)

    token_data = resp.json()
    access_token = token_data["access_token"]
    character_id = _decode_character_id(access_token)

    from datetime import datetime, timezone

    token_json = {
        "access_token": access_token,
        "refresh_token": token_data["refresh_token"],
        "expires_at": datetime.now(timezone.utc).timestamp() + token_data["expires_in"],
        "character_id": character_id,
        "client_id": client_id,
        "client_secret": secret,
    }
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(token_json, indent=2))

    click.echo(f"\nAuthenticated! Character ID: {character_id}")
    click.echo(f"Tokens saved to {TOKEN_FILE}")


def _decode_character_id(access_token: str) -> int:
    """Extract character ID from JWT payload."""
    parts = access_token.split(".")
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload))
    return int(decoded.get("sub", "").split(":")[-1])


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[dict]:
    """Refresh access token using stored client credentials."""
    import click

    headers = {"Authorization": f"Basic {_basic_auth(client_id, client_secret)}"}
    resp = httpx.post(
        SSO_TOKEN,
        headers=headers,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )

    if resp.status_code != 200:
        click.echo(f"Token refresh failed: {resp.text}", err=True)
        return None

    return resp.json()
