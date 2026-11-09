#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gsheet_read
short_description: Read values and hyperlinks from a Google Spreadsheet range
version_added: "1.2.0"
description:
    - Reads all cell values from an A1-notation O(range) on a worksheet.
    - Optionally also returns the hyperlink URL of each cell (e.g. account links added via "Insert link" in Google
      Sheets), which the plain values API does not expose.
    - Requires the Google Sheets API and either a service account JSON key or OAuth2 installed-app credentials with
      access to the spreadsheet.
    - Authenticates using a Google service account (O(credentials_path) / O(credentials)) OR OAuth2 installed-app
      credentials (O(client_id) / O(client_secret) / O(refresh_token)), whichever set of options is provided.
author:
    - Zachary LeBlanc
options:
    credentials_path:
        description:
            - Path to the Google service account JSON key file.
            - When omitted, the module uses the C(GOOGLE_SA_CRED_PATH) environment variable.
            - Mutually exclusive with O(credentials), O(client_id), and O(refresh_token).
        type: path
    credentials:
        description:
            - Service account JSON key as a dictionary (e.g. from Ansible Vault).
            - Mutually exclusive with O(credentials_path), O(client_id), and O(refresh_token).
        type: dict
        no_log: true
    client_id:
        description:
            - OAuth2 client ID from the Google Cloud project's installed-app credentials.
            - When omitted, the module uses the C(GOOGLE_CLIENT_ID) environment variable.
            - Mutually exclusive with O(credentials_path) and O(credentials).
            - Requires O(client_secret) and O(refresh_token) to also be set.
        type: str
    client_secret:
        description:
            - OAuth2 client secret paired with O(client_id).
            - When omitted, the module uses the C(GOOGLE_CLIENT_SECRET) environment variable.
        type: str
        no_log: true
    refresh_token:
        description:
            - OAuth2 refresh token obtained via a one-time consent flow (see C(scripts/google_oauth_setup.py)),
              requested with the C(https://www.googleapis.com/auth/spreadsheets) scope.
            - When omitted, the module uses the C(GOOGLE_REFRESH_TOKEN) environment variable.
            - Mutually exclusive with O(credentials_path) and O(credentials).
        type: str
        no_log: true
    gsheet_id:
        description:
            - The spreadsheet ID from the Google Sheets URL.
            - When omitted, the module uses the C(GOOGLE_SHEET_ID) environment variable.
        type: str
        aliases: [spreadsheet_id]
    sheet:
        description:
            - Worksheet name within the spreadsheet.
        type: str
        default: Sheet1
    range:
        description:
            - A1 notation range to read, relative to O(sheet) (e.g. C(A1), C(E17), C(A2:G14)).
        required: true
        type: str
    include_hyperlinks:
        description:
            - When C(true), also returns the hyperlink URL of each cell (e.g. links added via "Insert link" in
              Google Sheets) in the O(hyperlinks) return value.
            - Requires an additional Sheets API call.
        type: bool
        default: false
requirements:
    - google-api-python-client
    - google-auth
'''

EXAMPLES = r'''
- name: Read a single cell (uses GOOGLE_SA_CRED_PATH and GOOGLE_SHEET_ID)
  zjleblanc.gsuite.gsheet_read:
    sheet: Data
    range: "E17"
  register: total_tasks_cell

- name: Read account names alongside their hyperlink URLs
  zjleblanc.gsuite.gsheet_read:
    credentials_path: /path/to/service-account.json
    gsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    sheet: Data
    range: "A2:A14"
    include_hyperlinks: true
  register: gsheet_accounts

- name: Read using explicit OAuth2 credentials instead of a service account
  zjleblanc.gsuite.gsheet_read:
    client_id: "{{ google_client_id }}"
    client_secret: "{{ google_client_secret }}"
    refresh_token: "{{ google_refresh_token }}"
    gsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    sheet: Data
    range: "A2:G14"
'''

RETURN = r'''
values:
    description: >-
        Row-major list of cell values within the requested range. Trailing empty rows/columns are omitted by the
        Sheets API, so rows may have fewer elements than the range width.
    type: list
    elements: list
    returned: success
hyperlinks:
    description: >-
        Row-major list of cell hyperlink URLs, aligned with O(values) (empty string when a cell has no hyperlink).
        Only returned when O(include_hyperlinks=true).
    type: list
    elements: list
    returned: when include_hyperlinks=true
gsheet_id:
    description: The spreadsheet ID that was read.
    type: str
    returned: success
spreadsheet_id:
    description: Alias of O(gsheet_id) for consistency with C(gsheet_update).
    type: str
    returned: success
range:
    description: Full A1 notation range that was read, including the worksheet name.
    type: str
    returned: success
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.zjleblanc.gsuite.plugins.module_utils.auth import (
    GOOGLE_CLIENT_ID_ENV,
    GOOGLE_CLIENT_SECRET_ENV,
    GOOGLE_REFRESH_TOKEN_ENV,
    SHEETS_COMBINED_ARGSPEC,
    SHEETS_COMBINED_MUTUALLY_EXCLUSIVE,
    SHEETS_SCOPES,
    HttpError,
    build,
    check_google_deps,
    load_credentials,
    load_oauth_credentials,
    resolve_credentials_path,
    resolve_gsheet_id,
    resolve_oauth_param,
)
from ansible_collections.zjleblanc.gsuite.plugins.module_utils.gsheets import (
    sheet_range,
)


def get_values(service, spreadsheet_id, range_name):
    """Read all values from an A1-notation range."""
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def get_hyperlinks(service, spreadsheet_id, range_name):
    """Read the hyperlink URL (if any) of every cell in an A1-notation range."""
    result = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            fields="sheets.data.rowData.values.hyperlink",
        )
        .execute()
    )

    sheets = result.get("sheets", [])
    row_data = sheets[0].get("data", [{}])[0].get("rowData", []) if sheets else []

    hyperlinks = []
    for row in row_data:
        hyperlinks.append([cell.get("hyperlink") or "" for cell in row.get("values", [])])
    return hyperlinks


def main():
    module = AnsibleModule(
        argument_spec=dict(
            SHEETS_COMBINED_ARGSPEC,
            sheet=dict(type="str", default="Sheet1"),
            range=dict(type="str", required=True),
            include_hyperlinks=dict(type="bool", default=False),
        ),
        mutually_exclusive=SHEETS_COMBINED_MUTUALLY_EXCLUSIVE,
        supports_check_mode=True,
    )

    check_google_deps(module)

    credentials_dict = module.params["credentials"]
    credentials_path = module.params["credentials_path"]
    if not credentials_dict:
        credentials_path = resolve_credentials_path(credentials_path)

    client_id = resolve_oauth_param(module.params["client_id"], GOOGLE_CLIENT_ID_ENV)
    client_secret = resolve_oauth_param(module.params["client_secret"], GOOGLE_CLIENT_SECRET_ENV)
    refresh_token = resolve_oauth_param(module.params["refresh_token"], GOOGLE_REFRESH_TOKEN_ENV)
    use_oauth = bool(client_id and client_secret and refresh_token)

    gsheet_id = resolve_gsheet_id(module.params["gsheet_id"])
    sheet = module.params["sheet"]
    include_hyperlinks = module.params["include_hyperlinks"]
    target_range = sheet_range(sheet, module.params["range"])

    if not gsheet_id:
        module.fail_json(
            msg=(
                "Spreadsheet ID required: set gsheet_id "
                "or GOOGLE_SHEET_ID environment variable"
            )
        )

    if not use_oauth and not credentials_dict and not credentials_path:
        module.fail_json(
            msg=(
                "Google credentials required: set credentials_path, credentials, or the "
                "GOOGLE_SA_CRED_PATH environment variable for a service account, or set "
                "client_id, client_secret, and refresh_token (or the GOOGLE_CLIENT_ID, "
                "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN environment variables) "
                "for OAuth2"
            )
        )

    try:
        if use_oauth:
            creds = load_oauth_credentials(
                client_id, client_secret, refresh_token, scopes=SHEETS_SCOPES
            )
        else:
            creds = load_credentials(credentials_path, credentials_dict)
    except (ValueError, OSError) as exc:
        module.fail_json(msg=str(exc))
    except Exception as exc:
        module.fail_json(msg=f"Failed to obtain OAuth2 access token: {exc}")

    try:
        service = build("sheets", "v4", credentials=creds)
        values = get_values(service, gsheet_id, target_range)
        hyperlinks = get_hyperlinks(service, gsheet_id, target_range) if include_hyperlinks else None
    except HttpError as exc:
        module.fail_json(msg=f"Google Sheets API error: {exc}")
    except Exception as exc:
        module.fail_json(msg=f"Failed to read spreadsheet: {exc}")

    result = dict(
        changed=False,
        gsheet_id=gsheet_id,
        spreadsheet_id=gsheet_id,
        range=target_range,
        values=values,
    )
    if include_hyperlinks:
        result["hyperlinks"] = hyperlinks

    module.exit_json(**result)


if __name__ == "__main__":
    main()
