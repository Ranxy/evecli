"""EVE Online ESI Token management."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


TOKEN_DIR = Path.home() / ".config" / "evecli"
TOKEN_FILE = TOKEN_DIR / "tokens.json"

ESI_BASE = "https://esi.evetech.net/latest"
SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token"
CHAR_INFO = "https://login.eveonline.com/oauth/verify"


class TokenManager:
    """Manage OAuth2 access and refresh tokens for EVE ESI."""

    def __init__(self, token_path: Optional[Path] = None):
        self._path = token_path or TOKEN_FILE
        self._ensure_dir()

    def _ensure_dir(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        character_id: int,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """Persist tokens to disk."""
        data = self.load_tokens() or {}
        data.update({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": datetime.now(timezone.utc).timestamp() + expires_in,
            "character_id": character_id,
        })
        if client_id:
            data["client_id"] = client_id
        if client_secret:
            data["client_secret"] = client_secret
        self._path.write_text(json.dumps(data, indent=2))

    def load_tokens(self) -> Optional[dict]:
        """Return tokens dict if valid, None if missing/expired."""
        if not self._path.exists():
            return None
        try:
            return json.loads(self._path.read_text())
        except (json.JSONDecodeError, KeyError):
            return None

    def is_token_valid(self) -> bool:
        """Check whether the current access token is still valid."""
        data = self.load_tokens()
        if not data:
            return False
        return data.get("expires_at", 0) > datetime.now(timezone.utc).timestamp()

    def get_access_token(self) -> Optional[str]:
        """Return access token, auto-refresh if expired."""
        data = self.load_tokens()
        if not data:
            return None

        if not self.is_token_valid():
            from evecli.auth.sso import refresh_access_token

            rt = data.get("refresh_token")
            cid = data.get("client_id")
            cs = data.get("client_secret")

            if not rt or not cid or not cs:
                return None

            token_data = refresh_access_token(rt, cid, cs)
            if not token_data:
                return None

            self.save_tokens(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", rt),
                expires_in=token_data["expires_in"],
                character_id=data.get("character_id", 0),
            )
            return token_data["access_token"]

        return data["access_token"]

    def get_character_id(self) -> Optional[int]:
        data = self.load_tokens()
        return data.get("character_id") if data else None

    def get_refresh_token(self) -> Optional[str]:
        data = self.load_tokens()
        return data.get("refresh_token") if data else None

    def get_character_info(self) -> Optional[dict]:
        """Return character info from local storage."""
        data = self.load_tokens()
        if not data:
            return None
        return {
            "character_id": data.get("character_id"),
        }

    def get_status(self) -> str:
        """Human-readable auth status."""
        data = self.load_tokens()
        if not data:
            return "Not authenticated. Run 'evecli auth login' first."

        expires_at = datetime.fromtimestamp(data.get("expires_at", 0), tz=timezone.utc)
        return json.dumps({
            "authenticated": True,
            "character_id": data.get("character_id"),
            "token_expires_at": expires_at.isoformat(),
        }, indent=2)

    def remove_tokens(self) -> bool:
        """Delete stored tokens. Returns True if file was removed."""
        if self._path.exists():
            self._path.unlink()
            return True
        return False
