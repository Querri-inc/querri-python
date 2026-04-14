"""Token storage, OAuth browser flow, and credential management."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import secrets
import stat
import sys
import webbrowser
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKOS_CLIENT_ID = "client_01HGV989QK3KDNN4JJNGCD87RH"
WORKOS_AUTHORIZE_URL = "https://api.workos.com/user_management/authorize"
OAUTH_TIMEOUT_SECONDS = 120
OAUTH_CALLBACK_PORT = 11847  # Fixed port for WorkOS redirect URI registration
REFRESH_BUFFER_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# TokenProfile
# ---------------------------------------------------------------------------


@dataclass
class TokenProfile:
    """Stored credentials for a single auth profile."""

    auth_type: str = "jwt"  # always "jwt" for OAuth tokens
    access_token: str = ""
    refresh_token: str = ""
    expires_at: str = ""  # ISO 8601
    org_id: str = ""
    user_email: str = ""
    user_id: str = ""
    user_name: str = ""
    org_name: str = ""
    host: str = ""  # server used for login (used for token refresh)
    all_organizations: dict[str, str] = field(default_factory=dict)
    # Active workspace state
    active_project_id: str = ""
    active_project_name: str = ""
    active_chat_id: str = ""

    def __repr__(self) -> str:
        """Redact tokens to prevent accidental exposure."""
        return (
            f"TokenProfile(auth_type={self.auth_type!r}, "
            f"access_token='***', refresh_token='***', "
            f"expires_at={self.expires_at!r}, org_id={self.org_id!r}, "
            f"org_name={self.org_name!r}, user_email={self.user_email!r}, "
            f"user_id={self.user_id!r})"
        )


# ---------------------------------------------------------------------------
# TokenStore
# ---------------------------------------------------------------------------


class TokenStore:
    """Manages persistent token storage in ``~/.querri/tokens.json``.

    Schema::

        {
            "profiles": {
                "default": { ...TokenProfile fields... }
            },
            "active_profile": "default"
        }
    """

    STORE_DIR: Path = Path.home() / ".querri"
    STORE_FILE: Path = STORE_DIR / "tokens.json"

    def __init__(
        self,
        profiles: dict[str, TokenProfile] | None = None,
        active_profile: str = "default",
    ) -> None:
        self.profiles: dict[str, TokenProfile] = profiles or {}
        self.active_profile = active_profile

    # -- Persistence --------------------------------------------------------

    @classmethod
    def load(cls) -> TokenStore:
        """Load the token store from disk.

        Returns an empty store (without crashing) if the file is missing,
        unreadable, or contains invalid JSON.
        """
        store = cls()
        if not cls.STORE_FILE.exists():
            return store

        # Warn if file permissions are too open
        try:
            mode = cls.STORE_FILE.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                print(
                    f"Warning: {cls.STORE_FILE} has overly permissive permissions "
                    f"({oct(mode & 0o777)}). Expected 0600.",
                    file=sys.stderr,
                )
        except OSError:
            pass

        try:
            raw = cls.STORE_FILE.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"Warning: Could not read token store ({exc}). "
                "Starting with empty credentials.",
                file=sys.stderr,
            )
            return store

        store.active_profile = data.get("active_profile", "default")
        for name, profile_data in data.get("profiles", {}).items():
            if isinstance(profile_data, dict):
                store.profiles[name] = TokenProfile(
                    auth_type=profile_data.get("auth_type", "jwt"),
                    access_token=profile_data.get("access_token", ""),
                    refresh_token=profile_data.get("refresh_token", ""),
                    expires_at=profile_data.get("expires_at", ""),
                    org_id=profile_data.get("org_id", ""),
                    user_email=profile_data.get("user_email", ""),
                    user_id=profile_data.get("user_id", ""),
                    user_name=profile_data.get("user_name", ""),
                    org_name=profile_data.get("org_name", ""),
                    host=profile_data.get("host", ""),
                    all_organizations=profile_data.get("all_organizations", {}),
                    active_project_id=profile_data.get("active_project_id", ""),
                    active_project_name=profile_data.get("active_project_name", ""),
                    active_chat_id=profile_data.get("active_chat_id", ""),
                )
        return store

    def save(self) -> None:
        """Atomically write the token store to disk with secure permissions.

        Writes to a temp file first, then renames to prevent corruption.
        Skips persistence only in explicit CI environments to avoid
        accidentally writing credentials in automated pipelines.
        """
        # Only skip in clearly automated environments. The old isatty() check
        # was too aggressive — it blocked saves from VSCode terminals, tmux,
        # screen, WSL, Claude Code, and any piped context. CI pipelines set
        # a CI env var; that's the right signal.
        if os.environ.get("CI"):
            return

        # Ensure directory exists with 0700
        os.makedirs(self.STORE_DIR, mode=0o700, exist_ok=True)

        data = {
            "profiles": {
                name: asdict(profile) for name, profile in self.profiles.items()
            },
            "active_profile": self.active_profile,
        }
        content = json.dumps(data, indent=2)

        # Atomic write: create temp file with 0600 permissions, then rename
        tmp_path_obj = self.STORE_DIR / ".tokens_tmp"
        try:
            # Create file with restricted permissions — no race window
            fd = os.open(
                str(tmp_path_obj),
                os.O_CREAT | os.O_WRONLY | os.O_TRUNC,
                0o600,
            )
            try:
                os.write(fd, content.encode("utf-8"))
            finally:
                os.close(fd)

            # Atomic rename
            os.rename(str(tmp_path_obj), str(self.STORE_FILE))
        except OSError:
            # Clean up temp file on failure
            with contextlib.suppress(OSError):
                tmp_path_obj.unlink(missing_ok=True)
            raise

    # -- Profile management -------------------------------------------------

    def get_active_profile(self) -> TokenProfile | None:
        """Return the active profile, or ``None`` if not found."""
        return self.profiles.get(self.active_profile)

    def save_profile(self, name: str, profile: TokenProfile) -> None:
        """Persist a profile and write to disk."""
        self.profiles[name] = profile
        self.save()

    def switch_profile(self, name: str) -> None:
        """Change the active profile.

        Raises:
            KeyError: If the named profile does not exist.
        """
        if name not in self.profiles:
            raise KeyError(
                f"Profile {name!r} not found. Available: {list(self.profiles)}"
            )
        self.active_profile = name
        self.save()

    def delete_profile(self, name: str) -> None:
        """Remove a profile from the store.

        Raises:
            KeyError: If the named profile does not exist.
        """
        if name not in self.profiles:
            raise KeyError(f"Profile {name!r} not found.")
        del self.profiles[name]
        # If we deleted the active profile, reset to default or first available
        if self.active_profile == name:
            self.active_profile = next(iter(self.profiles), "default")
        self.save()


# ---------------------------------------------------------------------------
# Token refresh helpers
# ---------------------------------------------------------------------------


def needs_refresh(profile: TokenProfile) -> bool:
    """Return True if the profile's access token is within 5 minutes of expiry."""
    if not profile.expires_at:
        return True  # No expiry info — assume refresh needed

    try:
        from datetime import datetime, timezone

        expires = datetime.fromisoformat(profile.expires_at)
        # Ensure timezone-aware comparison
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        remaining = (expires - now).total_seconds()
        return remaining < REFRESH_BUFFER_SECONDS
    except (ValueError, TypeError):
        return True


def refresh_tokens(
    profile: TokenProfile,
    host: str,
    *,
    organization_id: str | None = None,
) -> TokenProfile:
    """Refresh an expired access token using the refresh token.

    Args:
        profile: The profile whose tokens to refresh.
        host: The Querri server host (e.g. ``https://app.querri.com``).
        organization_id: Optional org ID to switch to during refresh.

    Returns:
        Updated TokenProfile with new tokens.

    Raises:
        httpx.HTTPStatusError: On server error.
        RuntimeError: If refresh fails.
    """
    url = host.rstrip("/") + "/api/v1/auth/cli/token"
    payload: dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": profile.refresh_token,
    }
    if organization_id:
        payload["organization_id"] = organization_id
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            "Token refresh failed. Please run 'querri auth login' again."
        ) from exc

    data = response.json()
    profile.access_token = data["access_token"]
    profile.refresh_token = data.get("refresh_token", profile.refresh_token)

    # Update expiry — try expires_in first, fall back to JWT exp claim
    expires_in = data.get("expires_in")
    if expires_in is not None:
        from datetime import datetime, timedelta, timezone

        expires = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        profile.expires_at = expires.isoformat()
    else:
        claims = _decode_jwt_payload(data["access_token"])
        if "exp" in claims:
            from datetime import datetime, timezone

            profile.expires_at = datetime.fromtimestamp(
                claims["exp"], tz=timezone.utc
            ).isoformat()

    # Decode JWT for updated user info
    claims = _decode_jwt_payload(profile.access_token)
    if claims:
        profile.user_id = claims.get("sub", profile.user_id)
        profile.org_id = claims.get("org_id", profile.org_id)
        profile.user_email = claims.get("email", profile.user_email)

    return profile


# ---------------------------------------------------------------------------
# JWT payload decoding (no verification — server already validated)
# ---------------------------------------------------------------------------


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Base64-decode the payload segment of a JWT.

    No signature verification — the server already validated the token.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        # Add padding
        payload = parts[1] + "=="
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)  # type: ignore[no-any-return]
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# OAuth browser flow
# ---------------------------------------------------------------------------


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the local OAuth callback server."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path != "/callback":
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)
        server: _OAuthCallbackServer = self.server  # type: ignore[assignment]

        # Validate state
        received_state = params.get("state", [""])[0]
        if received_state != server.expected_state:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authentication failed</h1>"
                b"<p>Invalid state parameter. Please try again.</p>"
                b"</body></html>"
            )
            server.error = "State parameter mismatch"
            server.shutdown_flag = True
            return

        # Check for error from provider
        if "error" in params:
            error_msg = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Authentication failed</h1>"
                f"<p>{error_msg}</p></body></html>".encode()
            )
            server.error = error_msg
            server.shutdown_flag = True
            return

        # Extract authorization code
        code = params.get("code", [""])[0]
        if not code:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body><h1>Authentication failed</h1>"
                b"<p>No authorization code received.</p>"
                b"</body></html>"
            )
            server.error = "No authorization code received"
            server.shutdown_flag = True
            return

        # Success
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Querri CLI - Authenticated</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Poppins:wght@600;700&family=Source+Sans+3:wght@400;600&display=swap"
rel="stylesheet">
<link rel="icon" href="https://querri.com/favicon.svg" type="image/svg+xml">
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{
    font-family:'Source Sans 3','Open Sans',-apple-system,sans-serif;
    background:#0e0e12;
    color:#c5c8cb;
    display:flex;align-items:center;justify-content:center;
    min-height:100vh;
    overflow:auto;
  }
  /* animated grid background */
  body::before{
    content:'';position:fixed;inset:0;z-index:0;
    background-image:
      linear-gradient(rgba(241,90,36,.04) 1px,transparent 1px),
      linear-gradient(90deg,rgba(241,90,36,.04) 1px,transparent 1px);
    background-size:48px 48px;
    animation:gridPulse 8s ease-in-out infinite;
  }
  @keyframes gridPulse{
    0%,100%{opacity:.5} 50%{opacity:1}
  }
  /* subtle glow behind card */
  body::after{
    content:'';position:fixed;
    width:600px;height:600px;
    top:50%;left:50%;transform:translate(-50%,-50%);
    background:radial-gradient(circle,rgba(241,90,36,.08) 0%,transparent 70%);
    z-index:0;pointer-events:none;
  }
  .card{
    position:relative;z-index:1;
    max-width:640px;width:92vw;
    background:rgba(22,22,28,.85);
    backdrop-filter:blur(20px);
    border:1px solid rgba(255,255,255,.06);
    border-radius:16px;
    padding:48px 52px;
    box-shadow:0 0 80px rgba(241,90,36,.06),0 32px 64px rgba(0,0,0,.5);
  }
  .header{text-align:center;margin-bottom:32px}
  .logo{margin-bottom:24px}
  .logo img{height:28px;filter:brightness(1.1)}
  .status{
    display:inline-flex;align-items:center;gap:8px;
    padding:6px 16px;
    background:rgba(55,151,100,.1);
    border:1px solid rgba(55,151,100,.25);
    border-radius:100px;
    font-family:'JetBrains Mono',monospace;
    font-size:13px;font-weight:500;
    color:#379764;
    margin-bottom:16px;
  }
  .status .dot{
    width:8px;height:8px;border-radius:50%;
    background:#379764;
    box-shadow:0 0 8px rgba(55,151,100,.6);
    animation:pulse 2s ease-in-out infinite;
  }
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  h1{
    font-family:'Poppins',sans-serif;
    font-size:24px;font-weight:700;
    color:#fff;margin-bottom:6px;
  }
  .subtitle{color:#757980;font-size:14px;line-height:1.5}
  /* terminal block */
  .terminal{
    text-align:left;
    background:#0a0a0e;
    border:1px solid rgba(255,255,255,.06);
    border-radius:12px;
    overflow:hidden;
    margin-bottom:20px;
  }
  .terminal-bar{
    display:flex;align-items:center;gap:6px;
    padding:10px 16px;
    background:rgba(255,255,255,.03);
    border-bottom:1px solid rgba(255,255,255,.04);
  }
  .terminal-dot{width:10px;height:10px;border-radius:50%}
  .terminal-dot.r{background:#ff5f57}
  .terminal-dot.y{background:#febc2e}
  .terminal-dot.g{background:#28c840}
  .terminal-title{
    flex:1;text-align:center;
    font-family:'JetBrains Mono',monospace;
    font-size:11px;color:#515357;
    margin-right:42px;
  }
  .terminal-body{padding:20px 20px 24px}
  .cmd{
    padding:6px 0;
    font-family:'JetBrains Mono',monospace;
    font-size:13px;line-height:1.7;
  }
  .cmd .prompt{color:#F15A24;font-weight:700}
  .cmd .command{color:#e4e4e7}
  .cmd .comment{color:#515357;font-size:12px;margin-left:8px}
  .cmd .flag{color:#41A1B6}
  .cmd .string{color:#379764}
  .cmd .arg{color:#757980;font-style:italic}
  .sep{
    border:none;border-top:1px solid rgba(255,255,255,.04);
    margin:8px 0;
  }
  .section-label{
    font-family:'JetBrains Mono',monospace;
    font-size:11px;color:#515357;
    text-transform:uppercase;
    letter-spacing:1.5px;
    margin:12px 0 4px;
  }
  .close-hint{
    text-align:center;font-size:12px;color:#515357;
    font-family:'JetBrains Mono',monospace;
  }
  .fade-in{animation:fadeIn .5s ease-out}
  @keyframes fadeIn{from{opacity:0;transform:translateY(12px)}to{opacity:1}}
  .typing{animation:fadeIn .5s ease-out both}
  .typing:nth-child(2){animation-delay:.05s}
  .typing:nth-child(3){animation-delay:.1s}
  .typing:nth-child(4){animation-delay:.15s}
  .typing:nth-child(5){animation-delay:.2s}
  .typing:nth-child(6){animation-delay:.25s}
  .typing:nth-child(7){animation-delay:.3s}
  .typing:nth-child(8){animation-delay:.35s}
  .typing:nth-child(9){animation-delay:.4s}
  .typing:nth-child(10){animation-delay:.45s}
  .typing:nth-child(11){animation-delay:.5s}
  .typing:nth-child(12){animation-delay:.55s}
</style>
</head>
<body>
<div class="card fade-in">
  <div class="header">
    <div class="logo">
      <img src="https://querri.com/querri_logo.svg" alt="Querri" height="28">
    </div>
    <div class="status"><span class="dot"></span> authenticated</div>
    <h1>You're in.</h1>
    <p class="subtitle">Return to your terminal and start exploring.</p>
  </div>

  <div class="terminal">
    <div class="terminal-bar">
      <span class="terminal-dot r"></span>
      <span class="terminal-dot y"></span>
      <span class="terminal-dot g"></span>
      <span class="terminal-title">querri-cli</span>
    </div>
    <div class="terminal-body">
      <div class="section-label typing" style="margin-top:0">verify</div>
      <div class="cmd typing">
        <span class="prompt">$</span>
        <span class="command"> querri </span><span class="command">whoami</span>
      </div>

      <hr class="sep">
      <div class="section-label typing">create &amp; upload</div>
      <div class="cmd typing">
        <span class="prompt">$</span>
        <span class="command"> querri project new</span>
        <span class="string"> "Q1 Analysis"</span>
      </div>
      <div class="cmd typing">
        <span class="prompt">$</span>
        <span class="command"> querri file upload</span>
        <span class="string"> sales.csv</span>
      </div>

      <hr class="sep">
      <div class="section-label typing">chat with your data</div>
      <div class="cmd typing">
        <span class="prompt">$</span>
        <span class="command"> querri project chat</span>
        <span class="flag"> -m</span>
        <span class="string"> "summarize revenue by region"</span>
      </div>

      <hr class="sep">
      <div class="section-label typing">explore</div>
      <div class="cmd typing">
        <span class="prompt">$</span>
        <span class="command"> querri</span>
        <span class="flag"> --help</span>
      </div>
    </div>
  </div>

  <p class="close-hint">close this tab and return to your terminal</p>
</div>
</body>
</html>"""
        )
        server.auth_code = code
        server.shutdown_flag = True

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging."""
        pass


class _OAuthCallbackServer(HTTPServer):
    """Single-use HTTP server for receiving the OAuth callback."""

    def __init__(self, expected_state: str) -> None:
        # Bind to 127.0.0.1 only, fixed port (must be registered in WorkOS)
        super().__init__(("127.0.0.1", OAUTH_CALLBACK_PORT), _OAuthCallbackHandler)
        self.timeout = OAUTH_TIMEOUT_SECONDS
        self.expected_state = expected_state
        self.auth_code: str = ""
        self.error: str = ""
        self.shutdown_flag: bool = False

    def serve_until_callback(self) -> None:
        """Handle requests until a callback is received or timeout."""
        while not self.shutdown_flag:
            self.handle_request()


def start_oauth_flow(
    host: str,
    callback: Any = None,
    *,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Run the browser-based OAuth login flow.

    1. Starts a local HTTP server on 127.0.0.1:11847 (fixed port)
    2. Opens the browser to the WorkOS authorize URL
    3. Waits for the callback with the authorization code
    4. Exchanges the code for tokens via the Querri server proxy

    Args:
        host: The Querri server host (e.g. ``https://app.querri.com``).
        callback: Unused — reserved for future progress callbacks.
        organization_id: Optional WorkOS organization ID to scope the login.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``expires_at``,
        ``user_id``, ``org_id``, ``user_email``.

    Raises:
        RuntimeError: If not in an interactive terminal, or if the flow
            fails at any stage.
    """
    if not sys.stdin.isatty():
        raise RuntimeError(
            "OAuth login requires an interactive terminal. "
            "For CI/scripts, use QUERRI_API_KEY instead."
        )

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Start local callback server
    server = _OAuthCallbackServer(expected_state=state)
    port = server.server_address[1]

    redirect_uri = f"http://127.0.0.1:{port}/callback"

    # Build authorize URL
    client_id = os.environ.get("QUERRI_WORKOS_CLIENT_ID", WORKOS_CLIENT_ID)
    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
        "provider": "authkit",
    }
    if organization_id:
        params["organization_id"] = organization_id
    authorize_params = urlencode(params)
    authorize_url = f"{WORKOS_AUTHORIZE_URL}?{authorize_params}"

    # Open browser
    print("Opening browser for authentication...", file=sys.stderr)
    webbrowser.open(authorize_url)
    print(
        f"If your browser didn't open, visit:\n  {authorize_url}",
        file=sys.stderr,
    )
    print("Waiting for authentication...", file=sys.stderr)

    # Wait for callback in a background thread (so timeout works)
    server_thread = Thread(target=server.serve_until_callback, daemon=True)
    server_thread.start()
    server_thread.join(timeout=OAUTH_TIMEOUT_SECONDS)

    # Clean up server
    server.server_close()

    if server.error:
        raise RuntimeError(f"Authentication failed: {server.error}")
    if not server.auth_code:
        raise RuntimeError(
            "Authentication timed out. No callback received within "
            f"{OAUTH_TIMEOUT_SECONDS} seconds."
        )

    # Exchange authorization code for tokens
    token_url = host.rstrip("/") + "/api/v1/auth/cli/token"
    try:
        response = httpx.post(
            token_url,
            json={
                "grant_type": "authorization_code",
                "code": server.auth_code,
                "redirect_uri": redirect_uri,
            },
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        with contextlib.suppress(Exception):
            detail = exc.response.text[:200]
        raise RuntimeError(
            f"Token exchange failed (HTTP {exc.response.status_code}). {detail}"
        ) from exc

    data = response.json()
    access_token = data["access_token"]
    refresh_token = data.get("refresh_token", "")

    # Calculate expiry
    expires_at = ""
    expires_in = data.get("expires_in")
    if expires_in is not None:
        from datetime import datetime, timedelta, timezone

        expires = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        expires_at = expires.isoformat()
    else:
        # WorkOS may not return expires_in; decode exp from JWT instead
        claims_for_exp = _decode_jwt_payload(data["access_token"])
        if "exp" in claims_for_exp:
            from datetime import datetime, timezone

            expires_at = datetime.fromtimestamp(
                claims_for_exp["exp"], tz=timezone.utc
            ).isoformat()

    # Extract user info from response (WorkOS returns user object alongside tokens)
    # Fall back to JWT claims if user object not present
    user_info = data.get("user") or {}
    claims = _decode_jwt_payload(access_token)

    user_email = user_info.get("email") or claims.get("email", "")
    user_id = user_info.get("id") or claims.get("sub", "")
    org_id = data.get("organization_id") or claims.get("org_id", "")
    org_name = claims.get("urn:querri:organization_name", "")
    first_name = user_info.get("first_name", "")
    last_name = user_info.get("last_name", "")
    full_name = (
        f"{first_name} {last_name}".strip()
        if first_name or last_name
        else claims.get("urn:querri:full_name", "")
    )

    # org_name from server response (looked up from WorkOS)
    all_organizations = data.get("all_organizations") or {}
    if not org_name and org_id:
        org_name = all_organizations.get(org_id, org_name)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "user_id": user_id,
        "org_id": org_id,
        "org_name": org_name,
        "user_email": user_email,
        "user_name": full_name,
        "all_organizations": all_organizations,
    }
