"""
dropbox_client.py — Dropbox OAuth2 PKCE authentication and file upload.

No PySide6 or other UI dependencies; safe to import from non-GUI contexts.

Public API
----------
``run_auth_flow(app_key, open_browser_fn, timeout_secs)``
    Complete OAuth2 PKCE flow. Opens the browser, waits for the local
    callback, and returns a ``TokenResult``.  Call from a background thread.

``upload_file(local_path, dropbox_folder, access_token, app_key, refresh_token)``
    Upload *local_path* to *dropbox_folder* on Dropbox (overwrite mode).
    Refreshes the access token automatically on 401.  Returns a
    ``TokenResult`` with potentially-updated tokens that the caller must
    persist.

``TokenResult``
    Dataclass holding ``access_token`` and ``refresh_token``.

``DropboxAuthError``
    Raised for authentication / token-exchange failures.

Dropbox App setup
-----------------
Register an app at https://www.dropbox.com/developers/apps and add
``http://127.0.0.1`` as a redirect URI.  Copy the App Key (not the
App Secret — PKCE does not need a secret) into the settings dialog.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass

import requests

# ---------------------------------------------------------------------------
# Dropbox API endpoints
# ---------------------------------------------------------------------------

_AUTH_URL   = "https://www.dropbox.com/oauth2/authorize"
_TOKEN_URL  = "https://api.dropboxapi.com/oauth2/token"
_UPLOAD_URL = "https://content.dropboxapi.com/2/files/upload"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class TokenResult:
    """Tokens returned by a successful auth exchange or refresh."""
    access_token: str
    refresh_token: str


class DropboxAuthError(Exception):
    """Raised when authentication or token exchange fails."""


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` using the S256 method."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _build_auth_url(app_key: str, code_challenge: str, redirect_uri: str) -> str:
    params = {
        "client_id": app_key,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": redirect_uri,
        "token_access_type": "offline",   # request a long-lived refresh token
    }
    return _AUTH_URL + "?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# Local callback server
# ---------------------------------------------------------------------------

class _CallbackServer(http.server.HTTPServer):
    """HTTPServer that stores the auth code delivered via the redirect."""

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type[http.server.BaseHTTPRequestHandler],
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.auth_code: str | None = None
        self.auth_error: str | None = None
        self.callback_event = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the ``?code=`` parameter."""

    def do_GET(self) -> None:
        server: _CallbackServer = self.server  # type: ignore[assignment]
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            server.auth_code = params["code"][0]
            body = b"<html><body><h2>Authenticated! You may close this tab.</h2></body></html>"
        else:
            server.auth_error = params.get("error", ["cancelled"])[0]
            body = (
                b"<html><body><h2>Authentication cancelled or failed. "
                b"You may close this tab.</h2></body></html>"
            )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        server.callback_event.set()

    def log_message(self, *args: object) -> None:  # suppress request logging
        pass


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------

def _exchange_code(
    app_key: str,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> TokenResult:
    """Exchange an authorisation code for access + refresh tokens."""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "code": code,
            "grant_type": "authorization_code",
            "client_id": app_key,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if not resp.ok:
        raise DropboxAuthError(f"Token exchange failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    if "access_token" not in data:
        raise DropboxAuthError(f"Unexpected token response: {data}")
    return TokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", ""),
    )


def run_auth_flow(
    app_key: str,
    open_browser_fn: Callable[[str], object],
    timeout_secs: float = 120.0,
) -> TokenResult:
    """
    Run the full OAuth2 PKCE flow synchronously.

    Should be called from a **background thread** — it opens the browser
    and then blocks until the local callback arrives or *timeout_secs*
    elapses.

    Parameters
    ----------
    app_key:
        Your Dropbox application key (from the developer console).
    open_browser_fn:
        Callable that accepts a URL string and opens it in a browser.
        Pass ``webbrowser.open`` for normal desktop use.
    timeout_secs:
        Seconds to wait for the user to complete authentication.

    Returns
    -------
    TokenResult
        Contains ``access_token`` and ``refresh_token``.
    """
    if not callable(open_browser_fn):
        raise TypeError("open_browser_fn must be callable")

    verifier, challenge = _generate_pkce()

    # Bind to port 0 so the OS assigns a free port automatically.
    server = _CallbackServer(("127.0.0.1", 0), _CallbackHandler)
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}"

    auth_url = _build_auth_url(app_key, challenge, redirect_uri)
    open_browser_fn(auth_url)

    # handle_request() blocks until one HTTP request arrives; run it in a
    # daemon thread so the timeout below can interrupt the wait gracefully.
    serve_thread = threading.Thread(target=server.handle_request, daemon=True)
    serve_thread.start()

    got_callback = server.callback_event.wait(timeout=timeout_secs)
    server.server_close()

    if not got_callback:
        raise DropboxAuthError(
            "Timed out waiting for Dropbox authentication. "
            "Please try again."
        )
    if server.auth_error:
        raise DropboxAuthError(
            f"Dropbox returned an error: {server.auth_error}"
        )
    assert server.auth_code is not None
    return _exchange_code(app_key, server.auth_code, verifier, redirect_uri)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def refresh_access_token(app_key: str, refresh_token: str) -> TokenResult:
    """
    Use *refresh_token* to obtain a fresh access token.

    Dropbox may or may not issue a new refresh token; the existing one is
    returned as a fallback when the response omits it.
    """
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": app_key,
        },
        timeout=30,
    )
    if not resp.ok:
        raise DropboxAuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")
    data = resp.json()
    return TokenResult(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
    )


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

def upload_file(
    local_path: str,
    dropbox_folder: str,
    access_token: str,
    app_key: str,
    refresh_token: str,
) -> TokenResult:
    """
    Upload *local_path* to ``dropbox_folder/filename`` (overwrite mode).

    If the server responds with 401 (token expired), the access token is
    refreshed automatically and the upload is retried once.

    Returns
    -------
    TokenResult
        Tokens after the upload (access token may have changed if a refresh
        was needed).  The caller is responsible for persisting updated tokens.
    """
    filename = os.path.basename(local_path)
    dropbox_path = dropbox_folder.rstrip("/") + "/" + filename

    with open(local_path, "rb") as fh:
        data = fh.read()

    api_arg = json.dumps({
        "path": dropbox_path,
        "mode": "overwrite",
        "autorename": False,
        "mute": True,
    })

    def _post(token: str) -> requests.Response:
        return requests.post(
            _UPLOAD_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": api_arg,
                "Content-Type": "application/octet-stream",
            },
            data=data,
            timeout=60,
        )

    current = TokenResult(access_token=access_token, refresh_token=refresh_token)
    resp = _post(current.access_token)

    if resp.status_code == 401:
        # Access token expired — refresh and retry once.
        current = refresh_access_token(app_key, current.refresh_token)
        resp = _post(current.access_token)

    if not resp.ok:
        raise OSError(f"Dropbox upload failed ({resp.status_code}): {resp.text}")

    return current
