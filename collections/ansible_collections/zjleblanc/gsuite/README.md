# zjleblanc.gsuite

Ansible collection for interacting with Google Workspace (gsuite) services.

## Modules

- `gsheet_update` -- Update one or more Google Spreadsheet cells by row lookup or direct A1 reference (service
  account or OAuth2). Supports writing several cells in a single `batchUpdate` API call via `updates`, so a
  playbook can loop over records (e.g. accounts) without also looping over columns.
- `gsheet_read` -- Read values (and optionally hyperlink URLs) from an A1-notation range (service account or
  OAuth2).
- `gmail_search` -- Search Gmail messages with basic filters (to/from/subject/labels) and retrieve their contents.

## Filters

- `parse_sf_tasks` -- Parse a Salesforce "Activities" report email (HTML) into structured
  account/opportunity/task data with summary counts at every level.
- `match_sf_accounts` -- Match `parse_sf_tasks` accounts to rows read via `gsheet_read` by the Salesforce record ID
  embedded in each account's URL, ignoring report accounts with no matching row.

### `gsheet_update` usage modes

```yaml
# Single cell, by row lookup (original behavior)
- zjleblanc.gsuite.gsheet_update:
    lookup_column: A
    lookup_value: "{{ account_name }}"
    update_column: C
    update_value: "{{ case_count }}"

# Multiple columns on one looked-up row, in a single API call
- zjleblanc.gsuite.gsheet_update:
    sheet: Data
    lookup_column: A
    lookup_value: "{{ account_name }}"
    updates:
      - column: D
        value: "{{ total_opps }}"
      - column: E
        value: "{{ total_tasks }}"

# Direct cell references, no row lookup (e.g. a totals row)
- zjleblanc.gsuite.gsheet_update:
    sheet: Data
    updates:
      - cell: D17
        value: "{{ total_opps }}"
      - cell: E17
        value: "{{ total_tasks }}"
```

Within `updates`, each item sets exactly one of `column` (resolved against `lookup_column`/`lookup_value`) or `cell`
(a direct A1 reference such as `E17`). `update_column`/`update_value` remain available for a single-cell update and
are mutually exclusive with `updates`.

## Requirements

- `google-api-python-client`
- `google-auth`
- `beautifulsoup4` (required by `parse_sf_tasks`)

Install with:

```bash
pip install google-api-python-client google-auth beautifulsoup4
```

## Authentication

This collection supports two Google authentication models: a service account (no per-user consent required) and OAuth2
installed-app credentials (authenticates as a specific human user). `gmail_search` requires OAuth2 because service
accounts can't read a personal/Workspace Gmail mailbox without domain-wide delegation. `gsheet_update` and
`gsheet_read` accept **either** model, so you can reuse a single OAuth2 client/refresh_token across all three modules,
or keep using a service account for Sheets if you don't need Gmail access at all.

### `gsheet_update` / `gsheet_read` -- service account or OAuth2 installed-app credentials

Provide exactly one of the following credential sets (mixing the two is rejected as mutually exclusive):

- Service account:
  - `credentials_path` module argument (path to a service account JSON key file)
  - `credentials` module argument (service account JSON key as a dict, e.g. from Ansible Vault)
  - `GOOGLE_SA_CRED_PATH` environment variable (path to a service account JSON key file)
- OAuth2 installed-app client:
  - `client_id` / `client_secret` / `refresh_token` module arguments (e.g. from Ansible Vault)
  - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` environment variables

When using OAuth2, the `refresh_token` must have been obtained with the `https://www.googleapis.com/auth/spreadsheets`
scope (see the helper script below).

The target spreadsheet is identified via the `gsheet_id` module argument or the `GOOGLE_SHEET_ID` environment variable.

### `gmail_search` -- OAuth2 installed-app credentials

Authenticates as a specific user via OAuth2. Provide credentials via one of:

- `client_id` / `client_secret` / `refresh_token` module arguments (e.g. from Ansible Vault)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` environment variables -- this is the mechanism an
  AAP custom credential type should use to inject these values at job run time

### Obtaining an OAuth2 refresh token

The `refresh_token` must be obtained once via a human OAuth2 consent flow -- it cannot be generated automatically from
just the `client_id` and `client_secret`. Use the included helper script to do this:

```bash
pip install google-auth-oauthlib
python3 scripts/google_oauth_setup.py /path/to/client_id.json
```

By default this requests both the `gmail.readonly` and `spreadsheets` scopes, so the resulting refresh_token works for
both `gmail_search` and `gsheet_update`. Pass `--scopes` to request only one, e.g.:

```bash
python3 scripts/google_oauth_setup.py client_id.json \
    --scopes https://www.googleapis.com/auth/spreadsheets
```

This opens a browser for you to sign in and consent, then prints the `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and
`GOOGLE_REFRESH_TOKEN` values to store in AAP. The `client_id.json` here is an OAuth2 **installed-app** client
downloaded from Google Cloud Console (APIs & Services > Credentials) -- see `ansible_client_id.example.json` at the
repo root for its shape -- not a service account key. The refresh token does not expire unless revoked, so this only
needs to be run once per Google account. If you have an existing refresh_token that was obtained with only the
`gmail.readonly` scope, you'll need to re-run this script to get a new one that also covers `spreadsheets` before
using it with `gsheet_update`.
