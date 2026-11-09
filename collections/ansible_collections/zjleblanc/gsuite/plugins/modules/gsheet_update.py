#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gsheet_update
short_description: Update one or more Google Spreadsheet cells by row lookup or direct reference
version_added: "1.0.0"
description:
    - Finds a row by matching O(lookup_value) in O(lookup_column), then writes O(update_value) to O(update_column) on
      that row.
    - For writing several cells at once (e.g. multiple columns on the same looked-up row, or cells with no row
      lookup at all), use O(updates) instead of O(update_column)/O(update_value). Every cell in O(updates) is written
      in a single Google Sheets C(batchUpdate) API call, so callers can loop over rows/records in the playbook
      without also looping over columns.
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
    lookup_column:
        description:
            - Column letter to search for O(lookup_value) (e.g. C(A)).
            - Required when writing O(update_column)/O(update_value), or when any item in O(updates) uses C(column)
              instead of C(cell).
        type: str
    lookup_value:
        description:
            - Value to find in O(lookup_column); the matching row is updated.
        type: raw
    update_column:
        description:
            - Column letter to write O(update_value) on the matched row (e.g. C(C)).
            - Mutually exclusive with O(updates); use this for a single-cell update.
        type: str
    update_value:
        description:
            - Value written to O(update_column) on the matched row.
            - Mutually exclusive with O(updates).
        type: raw
    updates:
        description:
            - A list of cells to write in a single C(batchUpdate) API call, as an alternative to
              O(update_column)/O(update_value) for writing multiple cells without an Ansible-level loop.
            - Each item must set exactly one of C(column) (resolved against the row matched by O(lookup_column)/
              O(lookup_value)) or C(cell) (a direct A1-notation reference such as C(E17), written with no row
              lookup).
            - Mutually exclusive with O(update_column) and O(update_value).
        type: list
        elements: dict
        suboptions:
            column:
                description:
                    - Column letter to write O(value) on the row matched by O(lookup_column)/O(lookup_value).
                    - Mutually exclusive with C(cell) within the same item.
                type: str
            cell:
                description:
                    - A1-notation cell reference (e.g. C(E17)) to write O(value) to directly, with no row lookup.
                    - Mutually exclusive with C(column) within the same item.
                type: str
            value:
                description: Value to write to this cell.
                type: raw
                required: true
'''

EXAMPLES = r'''
- name: Update case count for a customer row (uses GOOGLE_SA_CRED_PATH and GOOGLE_SHEET_ID)
  zjleblanc.gsuite.gsheet_update:
    sheet: Customers
    lookup_column: A
    lookup_value: "{{ support_case_account_name }}"
    update_column: C
    update_value: "{{ all_cases | length }}"

- name: Update with explicit credentials path
  zjleblanc.gsuite.gsheet_update:
    credentials_path: /path/to/service-account.json
    gsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    lookup_column: B
    lookup_value: "SWA-1024286"
    update_column: E
    update_value: "Closed"
  register: gsheet_result

- name: Update using explicit OAuth2 credentials instead of a service account
  zjleblanc.gsuite.gsheet_update:
    client_id: "{{ google_client_id }}"
    client_secret: "{{ google_client_secret }}"
    refresh_token: "{{ google_refresh_token }}"
    gsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
    sheet: Customers
    lookup_column: A
    lookup_value: "{{ support_case_account_name }}"
    update_column: C
    update_value: "{{ all_cases | length }}"

- name: Write several columns on one account row in a single API call
  zjleblanc.gsuite.gsheet_update:
    sheet: Data
    lookup_column: A
    lookup_value: "{{ account.name }}"
    updates:
      - column: D
        value: "{{ account.total_opps }}"
      - column: E
        value: "{{ account.total_tasks }}"
      - column: F
        value: "{{ account.ai_summary }}"
      - column: G
        value: "{{ account.task_details | to_json }}"
  loop: "{{ matched_accounts }}"
  loop_control:
    loop_var: account

- name: Write totals directly by cell reference, no lookup needed
  zjleblanc.gsuite.gsheet_update:
    sheet: Data
    updates:
      - cell: D17
        value: "{{ report.total_opps }}"
      - cell: E17
        value: "{{ report.total_tasks }}"
'''

RETURN = r'''
row:
    description: 1-based row number that was updated. Omitted when every item in O(updates) used C(cell).
    type: int
    returned: when a row lookup was performed
    sample: 5
updated_range:
    description: A1 notation of the (first) cell that was updated, kept for backward compatibility with single-cell updates.
    type: str
    returned: success
    sample: "Customers!C5"
updated_ranges:
    description: A1 notation of every cell that was updated, in the order given.
    type: list
    elements: str
    returned: success
updated_cells:
    description: Total number of cells written.
    type: int
    returned: success
gsheet_id:
    description: The spreadsheet ID that was updated.
    type: str
    returned: success
spreadsheet_id:
    description: Alias of O(gsheet_id) for backward compatibility.
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
    cell_range,
    column_range,
    coerce_cell_value,
    normalize_cell,
    normalize_column,
    sheet_range,
)

VALUE_INPUT_OPTION = "USER_ENTERED"


def cell_values_match(cell, lookup_value):
    """Compare a sheet cell to the requested lookup value."""
    if cell is None or cell == "":
        return False
    return str(cell) == str(coerce_cell_value(lookup_value))


def find_row_by_lookup(column_values, lookup_value):
    """Return 1-based row number for the first matching lookup_value."""
    for index, row in enumerate(column_values):
        cell = row[0] if row else None
        if cell_values_match(cell, lookup_value):
            return index + 1
    return None


def get_column_values(service, spreadsheet_id, sheet, column):
    """Read all values from a single column."""
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=column_range(sheet, column),
        )
        .execute()
    )
    return result.get("values", [])


def build_update_ops(update_column, update_value, updates):
    """Normalize update_column/update_value or updates into a common list of {column, cell, value} dicts."""
    if updates:
        return updates
    return [{"column": update_column, "cell": None, "value": update_value}]


def validate_update_ops(module, update_ops, lookup_column, lookup_value):
    """Ensure each op specifies exactly one of column/cell, and that lookups are available when needed."""
    for op in update_ops:
        has_column = bool(op.get("column"))
        has_cell = bool(op.get("cell"))
        if has_column == has_cell:
            module.fail_json(
                msg="Each update must specify exactly one of 'column' or 'cell', got: {0}".format(op)
            )

    needs_lookup = any(op.get("column") for op in update_ops)
    if needs_lookup and not (lookup_column and lookup_value is not None):
        module.fail_json(
            msg=(
                "lookup_column and lookup_value are required when writing by column "
                "(via update_column/update_value, or 'column' in updates)"
            )
        )
    return needs_lookup


def batch_update_cells(service, spreadsheet_id, range_values):
    """Write multiple cells in a single batchUpdate call. range_values is a list of (range_name, value) tuples."""
    data = [
        {"range": range_name, "values": [[coerce_cell_value(value)]]}
        for range_name, value in range_values
    ]
    body = {"valueInputOption": VALUE_INPUT_OPTION, "data": data}
    return (
        service.spreadsheets()
        .values()
        .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
        .execute()
    )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            SHEETS_COMBINED_ARGSPEC,
            sheet=dict(type="str", default="Sheet1"),
            lookup_column=dict(type="str"),
            lookup_value=dict(type="raw"),
            update_column=dict(type="str"),
            update_value=dict(type="raw"),
            updates=dict(
                type="list",
                elements="dict",
                options=dict(
                    column=dict(type="str"),
                    cell=dict(type="str"),
                    value=dict(type="raw", required=True),
                ),
                mutually_exclusive=[["column", "cell"]],
            ),
        ),
        mutually_exclusive=SHEETS_COMBINED_MUTUALLY_EXCLUSIVE + [
            ["update_column", "updates"],
            ["update_value", "updates"],
        ],
        required_together=[["update_column", "update_value"], ["lookup_column", "lookup_value"]],
        required_one_of=[["update_column", "updates"]],
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
    lookup_column = module.params["lookup_column"]
    lookup_value = module.params["lookup_value"]

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

    update_ops = build_update_ops(
        module.params["update_column"], module.params["update_value"], module.params["updates"]
    )
    needs_lookup = validate_update_ops(module, update_ops, lookup_column, lookup_value)

    try:
        if needs_lookup:
            lookup_column = normalize_column(lookup_column)
        for op in update_ops:
            if op.get("column"):
                op["column"] = normalize_column(op["column"])
            if op.get("cell"):
                op["cell"] = normalize_cell(op["cell"])
    except ValueError as exc:
        module.fail_json(msg=str(exc))

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
    except Exception as exc:
        module.fail_json(msg=f"Failed to initialize Google Sheets API client: {exc}")

    row = None
    if needs_lookup:
        try:
            column_values = get_column_values(service, gsheet_id, sheet, lookup_column)
        except HttpError as exc:
            module.fail_json(msg=f"Google Sheets API error: {exc}")
        except Exception as exc:
            module.fail_json(msg=f"Failed to read spreadsheet: {exc}")

        row = find_row_by_lookup(column_values, lookup_value)
        if row is None:
            module.fail_json(
                msg=(
                    f"lookup_value {lookup_value!r} not found in column "
                    f"{lookup_column} on sheet {sheet!r}"
                )
            )

    range_values = []
    for op in update_ops:
        if op.get("column"):
            target_range = cell_range(sheet, op["column"], row)
        else:
            target_range = sheet_range(sheet, op["cell"])
        range_values.append((target_range, op["value"]))

    if module.check_mode:
        module.exit_json(
            changed=True,
            gsheet_id=gsheet_id,
            spreadsheet_id=gsheet_id,
            row=row,
            updated_range=range_values[0][0],
            updated_ranges=[range_name for range_name, _ in range_values],
            updated_cells=len(range_values),
            check_mode=True,
        )

    try:
        result = batch_update_cells(service, gsheet_id, range_values)
    except HttpError as exc:
        module.fail_json(msg=f"Google Sheets API error: {exc}")
    except Exception as exc:
        module.fail_json(msg=f"Failed to update spreadsheet: {exc}")

    responses = result.get("responses", [])
    updated_ranges = [
        response.get("updatedRange", range_values[i][0]) for i, response in enumerate(responses)
    ] or [range_name for range_name, _ in range_values]

    module.exit_json(
        changed=True,
        gsheet_id=result.get("spreadsheetId", gsheet_id),
        spreadsheet_id=result.get("spreadsheetId", gsheet_id),
        row=row,
        updated_range=updated_ranges[0],
        updated_ranges=updated_ranges,
        updated_cells=result.get("totalUpdatedCells", len(range_values)),
    )


if __name__ == "__main__":
    main()
