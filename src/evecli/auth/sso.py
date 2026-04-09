"""EVE Online SSO OAuth2 flow."""

import base64
import http.server
import json
import secrets
import threading
import urllib.parse
import webbrowser
from typing import Optional

import click
import httpx

from evecli.auth.token import PENDING_AUTH_FILE, SSO_TOKEN, TOKEN_FILE, TokenManager

EVE_SCOPES = [
    "esi-mail.read_mail.v1",
    "esi-mail.send_mail.v1",
    "publicData",
]

DEFAULT_SSO_PORT = 8088


def _basic_auth(client_id: str, secret: str) -> str:
    """Return Basic auth header value for SSO."""
    credentials = f"{client_id}:{secret}"
    return base64.b64encode(credentials.encode()).decode()


def _build_redirect_uri(port: int) -> str:
    """Return the redirect URI for the configured callback port."""
    return f"http://127.0.0.1:{port}/callback"


def _build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the EVE SSO authorization URL."""
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "scope": " ".join(EVE_SCOPES),
            "state": state,
        },
        quote_via=urllib.parse.quote,
    )
    return f"https://login.eveonline.com/v2/oauth/authorize/?{query}"


def _load_pending_auth() -> Optional[dict]:
    """Load pending manual auth metadata if present."""
    if not PENDING_AUTH_FILE.exists():
        return None
    try:
        return json.loads(PENDING_AUTH_FILE.read_text())
    except json.JSONDecodeError:
        return None


def _save_pending_auth(data: dict) -> None:
    """Persist pending manual auth metadata."""
    PENDING_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_AUTH_FILE.write_text(json.dumps(data, indent=2))


def _clear_pending_auth() -> None:
    """Remove pending manual auth metadata."""
    if PENDING_AUTH_FILE.exists():
        PENDING_AUTH_FILE.unlink()


def _parse_code_input(value: str) -> tuple[str, Optional[str]]:
    """Accept either a raw authorization code or a full callback URL."""
    raw_value = value.strip()
    parsed = urllib.parse.urlparse(raw_value)
    if parsed.scheme and parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        error = params.get("error", [None])[0]
        if error:
            raise click.ClickException(f"EVE SSO returned an error: {error}")

        code = params.get("code", [None])[0]
        if not code:
            raise click.ClickException("Callback URL did not contain a code parameter.")

        return code, params.get("state", [None])[0]

    return raw_value, None


def _exchange_authorization_code(
    client_id: str,
    secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange an authorization code for tokens."""
    headers = {"Authorization": f"Basic {_basic_auth(client_id, secret)}"}
    resp = httpx.post(
        SSO_TOKEN,
        headers=headers,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    if resp.status_code != 200:
        raise click.ClickException(f"Token exchange failed: {resp.text}")
    return resp.json()


def _store_token_response(token_data: dict, client_id: str, secret: str) -> int:
    """Persist token response and return the authenticated character ID."""
    access_token = token_data["access_token"]
    character_id = _decode_character_id(access_token)

    TokenManager().save_tokens(
        access_token=access_token,
        refresh_token=token_data["refresh_token"],
        expires_in=token_data["expires_in"],
        character_id=character_id,
        client_id=client_id,
        client_secret=secret,
    )
    return character_id


def _start_manual_login(client_id: str, port: int) -> None:
    """Generate an authorization URL for a remote/manual login flow."""
    redirect_uri = _build_redirect_uri(port)
    state = secrets.token_urlsafe(32)
    auth_url = _build_auth_url(client_id, redirect_uri, state)

    _save_pending_auth(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )

    click.echo("\nOpen the following URL in a browser on the user's own machine:")
    click.echo(f"\033[1;34m{auth_url}\033[0m")
    click.echo()
    click.echo("After login, EVE SSO will redirect to the registered callback URL.")
    click.echo("If the page fails to load, copy the full callback URL from the browser address bar.")
    click.echo("Then run evecli again with --mode manual --code '<callback-url-or-code>'.")


def _complete_manual_login(client_id: str, secret: str, code_input: str, port: int) -> None:
    """Complete a manual login flow using a user-provided code or callback URL."""
    pending = _load_pending_auth()
    if pending and pending.get("client_id") != client_id:
        raise click.ClickException(
            "Pending manual login was created for a different client ID. Start manual login again."
        )

    redirect_uri = pending.get("redirect_uri") if pending else _build_redirect_uri(port)
    expected_state = pending.get("state") if pending else None
    code, returned_state = _parse_code_input(code_input)

    if expected_state and returned_state and returned_state != expected_state:
        raise click.ClickException("Returned state did not match the pending login request.")

    if expected_state and not returned_state:
        click.echo(
            "Warning: raw code provided without callback URL; state could not be verified.",
            err=True,
        )

    token_data = _exchange_authorization_code(client_id, secret, code, redirect_uri)
    character_id = _store_token_response(token_data, client_id, secret)
    _clear_pending_auth()

    click.echo(f"\nAuthenticated! Character ID: {character_id}")
    click.echo(f"Tokens saved to {TOKEN_FILE}")


def _login_with_browser(client_id: str, secret: str, port: int) -> None:
    """Run the full OAuth2 login flow with a local redirect listener."""
    redirect_uri = _build_redirect_uri(port)
    state = secrets.token_urlsafe(32)
    auth_url = _build_auth_url(client_id, redirect_uri, state)

    click.echo("\nPlease open the following URL in your browser to authenticate:")
    click.echo(f"\033[1;34m{auth_url}\033[0m")
    click.echo()

    code_event = threading.Event()
    callback_result: dict[str, Optional[str]] = {
        "code": None,
        "state": None,
        "error": None,
    }

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            error = params.get("error", [None])[0]
            code = params.get("code", [None])[0]
            returned_state = params.get("state", [None])[0]

            if error:
                callback_result["error"] = f"EVE SSO returned an error: {error}"
                code_event.set()
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Authentication failed.</h1>")
                return

            if code and returned_state == state:
                callback_result["code"] = code
                callback_result["state"] = returned_state
                code_event.set()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authentication successful! You can close this tab.</h1>"
                )
            else:
                callback_result["error"] = "Returned state did not match the login request."
                code_event.set()
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Authentication failed.</h1>")

        def log_request(self, code="-", size="-"):
            pass  # suppress logs

    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Try to open browser, but URL is already printed above for manual copy
    try:
        opened = webbrowser.open(auth_url)
    except webbrowser.Error:
        opened = False

    if not opened:
        click.echo("Browser could not be opened automatically. Open the printed URL manually.", err=True)

    click.echo("Waiting for authentication callback (5 min timeout)...")

    # Wait for callback
    success = code_event.wait(timeout=300)  # 5 min
    server.shutdown()

    if not success:
        raise click.ClickException("Authentication timed out or failed.")

    if callback_result["error"]:
        raise click.ClickException(callback_result["error"])

    click.echo("\nGot authorization code. Exchanging for tokens...")

    token_data = _exchange_authorization_code(
        client_id,
        secret,
        callback_result["code"],
        redirect_uri,
    )
    character_id = _store_token_response(token_data, client_id, secret)

    click.echo(f"\nAuthenticated! Character ID: {character_id}")
    click.echo(f"Tokens saved to {TOKEN_FILE}")


def login_flow(
    client_id: str,
    secret: str,
    mode: str = "browser",
    code: str | None = None,
    port: int = DEFAULT_SSO_PORT,
) -> None:
    """Run the requested OAuth2 login flow."""
    if mode == "browser":
        if code:
            raise click.ClickException("--code can only be used together with --mode manual.")
        _login_with_browser(client_id, secret, port)
        return

    if code:
        _complete_manual_login(client_id, secret, code, port)
        return

    _start_manual_login(client_id, port)


def _decode_character_id(access_token: str) -> int:
    """Extract character ID from JWT payload."""
    parts = access_token.split(".")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = json.loads(base64.urlsafe_b64decode(payload))
    return int(decoded.get("sub", "").split(":")[-1])


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> Optional[dict]:
    """Refresh access token using stored client credentials."""
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
