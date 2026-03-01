"""
get_refresh_token.py
One-time OAuth2 authorization flow for EVE ESI.

Run this script once to obtain a refresh_token and save it to
config/credentials.json. After that, token_manager.py handles
everything automatically.

Usage:
    python3 scripts/get_refresh_token.py

Steps:
    1. Script reads client_id and scopes from credentials.json
    2. Prints an authorization URL — open it in any browser
    3. Log in with your EVE character and click Authorize
    4. EVE redirects to your callback URL (browser may show an error — that's fine)
    5. Copy the full URL from the browser address bar and paste it here
    6. Script exchanges the code for tokens and saves refresh_token automatically
"""

import json
import os
import sys
import secrets
import hashlib
import base64
import urllib.parse
import requests
from base64 import b64encode

# ============================================
# PATHS
# ============================================

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR  = os.path.dirname(SCRIPT_DIR)

CREDENTIALS_PATH = os.path.join(PROJECT_DIR, 'config', 'credentials.json')

ESI_AUTH_URL  = 'https://login.eveonline.com/v2/oauth/authorize'
ESI_TOKEN_URL = 'https://login.eveonline.com/v2/oauth/token'

# ============================================
# HELPERS
# ============================================

def load_credentials():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"[ERROR] credentials.json not found at:\n  {CREDENTIALS_PATH}")
        sys.exit(1)
    with open(CREDENTIALS_PATH, 'r') as f:
        return json.load(f)


def save_refresh_token(creds, refresh_token):
    """Write the refresh_token into credentials.json, preserving all other fields."""
    creds['refresh_token'] = refresh_token
    with open(CREDENTIALS_PATH, 'w') as f:
        json.dump(creds, f, indent=2)
    print(f"\n[OK] refresh_token saved to:\n  {CREDENTIALS_PATH}")


def get_scopes(creds):
    """
    Pull scopes from credentials.json.
    Looks for a 'scopes' key (list), then 'required_scopes', then
    '_required_scopes_example'.
    Filters out any non-scope strings (those that don't start with 'esi-' or
    equal 'publicData').
    """
    raw = (
        creds.get('scopes')
        or creds.get('required_scopes')
        or creds.get('_required_scopes_example', [])
    )

    flattened = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, list):
                flattened.extend(item)
            else:
                flattened.append(item)
    elif isinstance(raw, str):
        flattened = raw.split()

    valid_scopes = [
        scope for scope in flattened
        if isinstance(scope, str) and (scope.startswith('esi-') or scope == 'publicData')
    ]

    seen = set()
    deduped = []
    for scope in valid_scopes:
        if scope not in seen:
            deduped.append(scope)
            seen.add(scope)

    return deduped


def exchange_code(client_id, client_secret, code, redirect_uri):
    """Exchange an authorization code for access + refresh tokens."""
    auth_header = b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type':  'application/x-www-form-urlencoded',
        'Host':          'login.eveonline.com',
    }
    data = {
        'grant_type':   'authorization_code',
        'code':          code,
        'redirect_uri':  redirect_uri,
    }

    resp = requests.post(ESI_TOKEN_URL, headers=headers, data=data, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"\n[ERROR] Token exchange failed ({resp.status_code}):\n  {resp.text}")
        sys.exit(1)


def verify_token(access_token):
    """Call ESI verify to confirm the token and show character info."""
    resp = requests.get(
        'https://esi.evetech.net/verify/',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def parse_callback_url(raw_input):
    """
    Accept either:
      - A full callback URL:  https://localhost/callback?code=XXX&state=YYY
      - Just the code value:  XXX
    Returns the code string.
    """
    raw_input = raw_input.strip()
    if raw_input.startswith('http'):
        parsed = urllib.parse.urlparse(raw_input)
        params = urllib.parse.parse_qs(parsed.query)
        if 'code' not in params:
            print("[ERROR] No 'code' parameter found in the URL.")
            sys.exit(1)
        return params['code'][0]
    # Assume the user pasted just the code
    return raw_input


# ============================================
# MAIN
# ============================================

def main():
    print("=" * 60)
    print("EVE ESI — ONE-TIME OAUTH AUTHORIZATION")
    print("=" * 60)

    # --- Load credentials ---
    creds = load_credentials()
    client_id     = creds.get('client_id', '').strip()
    client_secret = creds.get('client_secret', '').strip()

    if not client_id or client_id == 'YOUR_ESI_CLIENT_ID':
        print("[ERROR] client_id is missing or still a placeholder in credentials.json")
        sys.exit(1)
    if not client_secret or client_secret == 'YOUR_ESI_CLIENT_SECRET':
        print("[ERROR] client_secret is missing or still a placeholder in credentials.json")
        sys.exit(1)

    # --- Scopes ---
    scopes = get_scopes(creds)
    if not scopes:
        print("[WARN] No scopes found in credentials.json.")
        print("       Add a 'scopes' list to credentials.json, e.g.:")
        print('       "scopes": ["esi-assets.read_assets.v1", "esi-wallet.read_character_wallet.v1"]')
        print()
        manual = input("Enter space-separated scopes to request (or press Enter to use publicData only): ").strip()
        scopes = manual.split() if manual else ['publicData']

    scope_str = ' '.join(scopes)

    # --- Callback URL ---
    print(f"\nClient ID : {client_id[:8]}...")
    print(f"Scopes    : {scope_str[:80]}{'...' if len(scope_str) > 80 else ''}")

    print("\n" + "-" * 60)
    print("What callback URL is registered in your ESI app?")
    print("  (Found at https://developers.eveonline.com/ → your app → Edit)")
    print("  Default suggestion: https://localhost/callback")
    print("-" * 60)
    redirect_uri = input("Callback URL [https://localhost/callback]: ").strip()
    if not redirect_uri:
        redirect_uri = 'https://localhost/callback'

    # --- State (CSRF protection) ---
    state = secrets.token_urlsafe(16)

    # --- Build authorization URL ---
    params = {
        'response_type': 'code',
        'redirect_uri':  redirect_uri,
        'client_id':     client_id,
        'scope':         scope_str,
        'state':         state,
    }
    auth_url = ESI_AUTH_URL + '?' + urllib.parse.urlencode(params)

    print("\n" + "=" * 60)
    print("STEP 1 — Open this URL in your browser:")
    print("=" * 60)
    print(f"\n{auth_url}\n")
    print("=" * 60)
    print("STEP 2 — Log in as your EVE character and click Authorize.")
    print()
    print("STEP 3 — Your browser will be redirected to your callback URL.")
    print("         It may show a connection error — that's normal.")
    print("         Copy the FULL URL from the browser address bar.")
    print("=" * 60)

    # --- Wait for user to paste callback URL or code ---
    print()
    raw = input("Paste the full redirect URL (or just the 'code' value): ").strip()
    if not raw:
        print("[ERROR] No input received.")
        sys.exit(1)

    code = parse_callback_url(raw)
    print(f"\n[OK] Authorization code received ({code[:10]}...)")

    # --- Exchange code for tokens ---
    print("\nExchanging authorization code for tokens...")
    token_data = exchange_code(client_id, client_secret, code, redirect_uri)

    access_token  = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')

    if not refresh_token:
        print("[ERROR] No refresh_token in ESI response. Make sure your ESI app")
        print("        has 'offline_access' or a scope that grants a refresh token.")
        print(f"        Full response: {token_data}")
        sys.exit(1)

    print(f"[OK] Access token  : {access_token[:20]}...")
    print(f"[OK] Refresh token : {refresh_token[:20]}...")

    # --- Verify and show character info ---
    char = verify_token(access_token)
    if char:
        print(f"\n[OK] Authorized as  : {char.get('CharacterName')} (ID: {char.get('CharacterID')})")

    # --- Save refresh token ---
    save_refresh_token(creds, refresh_token)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print("You can now run any script that uses token_manager.py.")
    print("The refresh_token will be used automatically to fetch")
    print("access tokens as needed — no further manual steps required.")
    print("=" * 60)


if __name__ == '__main__':
    main()
