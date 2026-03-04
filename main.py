"""
Ecobee thermostat API integration.

This script authenticates with the Ecobee API using the PIN-based OAuth2
flow and retrieves thermostat data.

Usage:
    1. Set your Ecobee API key in the ECOBEE_API_KEY environment variable
       or pass it as a command-line argument:
           python main.py --api-key YOUR_API_KEY

    2. On first run, you will be given a PIN to authorize the app at
       https://www.ecobee.com/home/ecobeeLogin.jsp -> My Apps -> Add Application

    3. Press Enter after authorizing the app to retrieve your thermostat data.
"""

import argparse
import json
import os
import sys

import requests

ECOBEE_API_BASE = "https://api.ecobee.com"
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ecobee_tokens.json")

# Ecobee PIN authorizations expire after 9 minutes by default
DEFAULT_PIN_EXPIRY_MINUTES = 9


def load_tokens():
    """Load stored OAuth tokens from disk."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return {}


def save_tokens(tokens):
    """Persist OAuth tokens to disk with owner-only read/write permissions."""
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tokens, f, indent=2)


def request_pin(api_key):
    """Request a PIN for the user to authorize this application."""
    url = f"{ECOBEE_API_BASE}/authorize"
    params = {
        "response_type": "ecobeePin",
        "client_id": api_key,
        "scope": "smartRead",
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:
        print(
            f"Error requesting PIN from Ecobee (HTTP {exc.response.status_code}). "
            "Please verify your API key is correct and that your Ecobee developer "
            "application has the 'smartRead' scope enabled.",
            file=sys.stderr,
        )
        raise
    return response.json()


def request_tokens(api_key, auth_code):
    """Exchange an authorization code for access and refresh tokens."""
    url = f"{ECOBEE_API_BASE}/token"
    params = {
        "grant_type": "ecobeePin",
        "code": auth_code,
        "client_id": api_key,
    }
    try:
        response = requests.post(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:
        print(
            f"Error exchanging PIN for tokens (HTTP {exc.response.status_code}). "
            "Make sure you authorized the PIN at https://www.ecobee.com before the "
            f"{DEFAULT_PIN_EXPIRY_MINUTES}-minute expiry and then retry.",
            file=sys.stderr,
        )
        raise
    return response.json()


def refresh_tokens(api_key, refresh_token):
    """Use a refresh token to obtain a new access token."""
    url = f"{ECOBEE_API_BASE}/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": api_key,
    }
    response = requests.post(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_thermostats(access_token):
    """Retrieve the thermostat summary from the Ecobee API."""
    url = f"{ECOBEE_API_BASE}/1/thermostatSummary"
    headers = {"Authorization": f"Bearer {access_token}"}
    body = json.dumps({
        "selection": {
            "selectionType": "registered",
            "selectionMatch": "",
            "includeRuntime": True,
            "includeSettings": True,
        }
    })
    try:
        response = requests.get(url, headers=headers, params={"json": body}, timeout=10)
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code
        if status in (401, 403):
            print(
                "Authentication error retrieving thermostat data. "
                "Your access token may be invalid or expired — delete "
                f"'{TOKEN_FILE}' and re-run to re-authenticate.",
                file=sys.stderr,
            )
        else:
            print(
                f"Error retrieving thermostat data (HTTP {status}).",
                file=sys.stderr,
            )
        raise
    return response.json()


def authenticate(api_key):
    """
    Full PIN-based OAuth2 flow.

    Returns a dict with ``access_token`` and ``refresh_token``.
    """
    pin_data = request_pin(api_key)
    pin = pin_data.get("ecobeePin")
    auth_code = pin_data.get("code")
    expires_in = pin_data.get("expires_in", DEFAULT_PIN_EXPIRY_MINUTES)

    print(f"\nPlease log in to https://www.ecobee.com and add the following PIN")
    print(f"under My Apps -> Add Application:\n")
    print(f"    PIN: {pin}\n")
    print(f"The PIN expires in {expires_in} minutes.")
    input("Press Enter after you have authorized the application...")

    tokens = request_tokens(api_key, auth_code)
    save_tokens(tokens)
    print("Tokens saved successfully.")
    return tokens


def ensure_valid_token(api_key):
    """
    Return a valid access token, refreshing or re-authenticating as needed.
    """
    tokens = load_tokens()

    if not tokens:
        tokens = authenticate(api_key)
        return tokens["access_token"]

    # Attempt to refresh with the stored refresh token
    try:
        refreshed = refresh_tokens(api_key, tokens["refresh_token"])
        save_tokens(refreshed)
        return refreshed["access_token"]
    except requests.HTTPError as exc:
        print(f"Token refresh failed ({exc}). Re-authenticating...")
        tokens = authenticate(api_key)
        return tokens["access_token"]


def display_thermostats(data):
    """Print thermostat revision list in a human-readable format."""
    revision_list = data.get("revisionList", [])
    if not revision_list:
        print("No thermostats found on this account.")
        return

    print(f"\nFound {len(revision_list)} thermostat(s):\n")
    for entry in revision_list:
        # Each entry is a colon-separated string:
        # thermostatIdentifier:name:connected:thermostatRevision:alertsRevision:
        # runtimeRevision:intervalRevision
        parts = entry.split(":")
        if len(parts) >= 3:
            identifier = parts[0]
            name = parts[1]
            connected = parts[2]
            print(f"  [{identifier}] {name} — {'online' if connected == 'true' else 'offline'}")
        else:
            print(f"  {entry}")


def main():
    parser = argparse.ArgumentParser(description="Ecobee thermostat API client")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ECOBEE_API_KEY"),
        help="Ecobee application API key (or set ECOBEE_API_KEY env var)",
    )
    args = parser.parse_args()

    if not args.api_key:
        print(
            "Error: No API key provided. Set the ECOBEE_API_KEY environment variable "
            "or pass --api-key YOUR_API_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)

    access_token = ensure_valid_token(args.api_key)
    data = get_thermostats(access_token)
    display_thermostats(data)


if __name__ == "__main__":
    main()
