"""One-time local script to obtain a Canva OAuth2 refresh token using PKCE.

Usage:
    1. Go to canva.dev > Developer Portal > Create Integration
    2. Note your client_id and generate a client_secret (starts with cnvca.)
    3. Add http://localhost:8090/callback as a redirect URI
    4. Enable scopes: design:content:read, design:content:write, design:meta:read,
       brandtemplate:content:read, brandtemplate:meta:read, asset:read, asset:write, folder:read
    5. Set environment variables:
         export CANVA_CLIENT_ID=your_client_id
         export CANVA_CLIENT_SECRET=your_client_secret
    6. Run: python src/get_refresh_token.py
    7. Copy the printed values into your Railway/Render environment variables
"""

import os
import sys
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
REDIRECT_URI = "http://127.0.0.1:8090/callback"
SCOPES = (
    "design:content:read design:content:write design:meta:read "
    "brandtemplate:content:read brandtemplate:meta:read "
    "asset:read asset:write folder:read"
)

auth_code: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")

    def log_message(self, format, *args):
        pass  # Suppress request logs


def main():
    client_id = os.environ.get("CANVA_CLIENT_ID")
    client_secret = os.environ.get("CANVA_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("Error: Set CANVA_CLIENT_ID and CANVA_CLIENT_SECRET environment variables.")
        sys.exit(1)

    # PKCE: generate code_verifier and code_challenge
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    state = secrets.token_urlsafe(16)

    params = {
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "scope": SCOPES,
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }

    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    print(f"Opening browser for authorization...\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(("127.0.0.1", 8090), CallbackHandler)
    print("Waiting for callback on http://localhost:8090/callback ...")
    while auth_code is None:
        server.handle_request()

    print("Got authorization code, exchanging for tokens...")

    # Exchange code for tokens
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    resp = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "code_verifier": code_verifier,
            "redirect_uri": REDIRECT_URI,
        },
    )

    if resp.status_code != 200:
        print(f"Error: {resp.status_code} {resp.text}")
        sys.exit(1)

    data = resp.json()

    print("\n--- Canva OAuth2 Credentials ---")
    print(f"CANVA_REFRESH_TOKEN={data['refresh_token']}")
    print(f"CANVA_CLIENT_ID={client_id}")
    print(f"CANVA_CLIENT_SECRET={client_secret}")
    print("\nSet these as environment variables in Railway/Render.")


if __name__ == "__main__":
    main()
