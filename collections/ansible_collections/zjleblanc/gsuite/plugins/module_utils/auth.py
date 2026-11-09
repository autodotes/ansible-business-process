# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared Google authentication helpers for the zjleblanc.gsuite collection.

Centralizes service account credential resolution and loading so every
module in this collection authenticates the same way without duplicating
this logic.
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os

try:
    from google.oauth2.service_account import Credentials
    from google.oauth2.credentials import Credentials as OAuthCredentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    HAS_GOOGLE = True
except ImportError:
    # Left unbound on failure; safe because every module MUST call
    # check_google_deps() (which fail_json()/exits) before referencing these.
    Credentials = None
    OAuthCredentials = None
    Request = None
    build = None
    HttpError = None
    HAS_GOOGLE = False

GOOGLE_SA_CRED_ENV = "GOOGLE_SA_CRED_PATH"
GOOGLE_SHEET_ID_ENV = "GOOGLE_SHEET_ID"
GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
GOOGLE_REFRESH_TOKEN_ENV = "GOOGLE_REFRESH_TOKEN"

#: Default OAuth scope granting read/write access to Google Sheets.
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

#: Default OAuth scope granting read-only access to Gmail.
GMAIL_READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

#: Google's OAuth2 token endpoint used to refresh access tokens.
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"

#: Shared argument_spec entries for modules that authenticate against Google.
#: Merge into a module's argument_spec, e.g.:
#:   argument_spec=dict(AUTH_ARGSPEC, **{"sheet": dict(type="str", ...)})
AUTH_ARGSPEC = dict(
    credentials_path=dict(type="path"),
    credentials=dict(type="dict", no_log=True),
    gsheet_id=dict(type="str", aliases=["spreadsheet_id"]),
)

#: Shared mutually_exclusive entries corresponding to AUTH_ARGSPEC.
AUTH_MUTUALLY_EXCLUSIVE = [["credentials_path", "credentials"]]

#: Shared argument_spec entries for modules that authenticate using an OAuth2
#: installed-app client (client_id/client_secret) plus a previously obtained
#: refresh_token. Each value falls back to an environment variable when the
#: module argument is omitted, which lets an AAP custom credential type
#: inject these via GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN.
#: Merge into a module's argument_spec, e.g.:
#:   argument_spec=dict(OAUTH_ARGSPEC, **{"query": dict(type="str", ...)})
OAUTH_ARGSPEC = dict(
    client_id=dict(type="str"),
    client_secret=dict(type="str", no_log=True),
    refresh_token=dict(type="str", no_log=True),
)

#: Combined argument_spec for modules (e.g. gsheet_update) that accept either
#: a service account (AUTH_ARGSPEC) or an OAuth2 installed-app client
#: (OAUTH_ARGSPEC) for authentication.
SHEETS_COMBINED_ARGSPEC = dict(AUTH_ARGSPEC, **OAUTH_ARGSPEC)

#: Mutually exclusive groups for SHEETS_COMBINED_ARGSPEC: callers must use
#: either service account credentials or OAuth2 credentials, never both.
SHEETS_COMBINED_MUTUALLY_EXCLUSIVE = [
    ["credentials_path", "credentials"],
    ["credentials_path", "client_id"],
    ["credentials_path", "refresh_token"],
    ["credentials", "client_id"],
    ["credentials", "refresh_token"],
]


def check_google_deps(module):
    """Fail the module with a clear message if the Google client libs are missing."""
    if not HAS_GOOGLE:
        module.fail_json(
            msg=(
                "google-api-python-client and google-auth are required. "
                "Install with: pip install google-api-python-client google-auth"
            )
        )


def resolve_credentials_path(credentials_path):
    """Return explicit path or fall back to GOOGLE_SA_CRED_PATH."""
    if credentials_path:
        return credentials_path
    return os.environ.get(GOOGLE_SA_CRED_ENV)


def resolve_gsheet_id(gsheet_id):
    """Return explicit spreadsheet ID or fall back to GOOGLE_SHEET_ID."""
    if gsheet_id:
        return gsheet_id
    return os.environ.get(GOOGLE_SHEET_ID_ENV)


def load_credentials(credentials_path, credentials_dict, scopes=None):
    """Build Google service account credentials from a file path or dict."""
    scopes = scopes or SHEETS_SCOPES
    if credentials_path:
        if not os.path.isfile(credentials_path):
            raise ValueError(f"credentials file not found: {credentials_path}")
        return Credentials.from_service_account_file(credentials_path, scopes=scopes)
    return Credentials.from_service_account_info(credentials_dict, scopes=scopes)


def resolve_oauth_param(value, env_var):
    """Return an explicit OAuth2 param value or fall back to an environment variable.

    Used to resolve client_id / client_secret / refresh_token so an AAP
    custom credential type can inject them as env vars while still allowing
    module arguments (e.g. from Ansible Vault) to take precedence.
    """
    if value:
        return value
    return os.environ.get(env_var)


def load_oauth_credentials(client_id, client_secret, refresh_token, scopes=None):
    """Build OAuth2 user credentials from a client_id/secret and refresh_token.

    Unlike service accounts, OAuth2 installed-app credentials require a
    refresh_token obtained once via a human consent flow (see
    scripts/google_oauth_setup.py). This immediately refreshes the
    credentials so callers get a valid access token.
    """
    scopes = scopes or GMAIL_READONLY_SCOPES
    creds = OAuthCredentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=GOOGLE_TOKEN_URI,
        scopes=scopes,
    )
    creds.refresh(Request())
    return creds
