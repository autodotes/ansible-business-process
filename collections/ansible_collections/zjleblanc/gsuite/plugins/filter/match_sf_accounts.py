# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
    name: match_sf_accounts
    short_description: Match parsed Salesforce report accounts to Google Sheet rows by Salesforce record ID
    version_added: "1.2.0"
    description:
        - Correlates the C(accounts) list produced by the M(zjleblanc.gsuite.parse_sf_tasks) filter to rows read
          from a Google Sheet (via M(zjleblanc.gsuite.gsheet_read)) using the Salesforce record ID embedded in each
          account's Salesforce URL.
        - Salesforce URLs for the same record can differ in shape between contexts (e.g. a report export vs. a
          manually inserted spreadsheet link), such as C(.../r/0016e00.../view) vs. C(.../r/Account/0016e00.../view).
          Extracting and comparing the record ID avoids false negatives from those shape differences.
        - Report accounts with no matching row in the Google Sheet are silently dropped from the result, per the
          business requirement to ignore accounts not tracked in the sheet.
        - Each individual task across an account's opportunities is flattened into a single C(tasks) list on the
          matched result, ready to hand to an AI summarization step or serialize as task detail data.
    positional: _input
    options:
        _input:
            description: The C(accounts) list from M(zjleblanc.gsuite.parse_sf_tasks)'s output (C(sf_report.accounts)).
            type: list
            elements: dict
            required: true
        gsheet_values:
            description: >-
                Row-major account name values read from the Google Sheet's account column, as returned by
                M(zjleblanc.gsuite.gsheet_read) (its C(values) return value).
            type: list
            elements: list
            required: true
        gsheet_hyperlinks:
            description: >-
                Row-major hyperlink URLs read from the Google Sheet's account column, aligned with O(gsheet_values),
                as returned by M(zjleblanc.gsuite.gsheet_read) (its C(hyperlinks) return value).
            type: list
            elements: list
            required: true
'''

EXAMPLES = r'''
- name: Match report accounts to their gsheet rows
  ansible.builtin.set_fact:
    matched_accounts: >-
      {{ sf_report.accounts
         | zjleblanc.gsuite.match_sf_accounts(gsheet_accounts.values, gsheet_accounts.hyperlinks) }}

- name: Update each matched account's row
  zjleblanc.gsuite.gsheet_update:
    sheet: Data
    lookup_column: A
    lookup_value: "{{ item.lookup_value }}"
    updates:
      - column: D
        value: "{{ item.total_opps }}"
      - column: E
        value: "{{ item.total_tasks }}"
  loop: "{{ matched_accounts }}"
'''

RETURN = r'''
_value:
    description: List of matched accounts, one entry per report account found in the Google Sheet.
    type: list
    elements: dict
    contains:
        lookup_value:
            description: >-
                The account's exact text value as it appears in the Google Sheet's account column -- use this
                (not O(account)) as C(lookup_value) when calling M(zjleblanc.gsuite.gsheet_update), since it is
                guaranteed to match the cell text exactly.
            type: str
        account:
            description: Account name as it appears in the Salesforce report.
            type: str
        account_url:
            description: Salesforce URL for the account, from the report.
            type: str
        total_opps:
            description: Number of opportunities under this account, from the report.
            type: int
        total_tasks:
            description: Number of tasks under this account, from the report.
            type: int
        tasks:
            description: Every task across all of this account's opportunities, flattened into a single list.
            type: list
            elements: dict
'''

import re

from ansible.errors import AnsibleFilterError

# Matches the Salesforce record ID out of report/lightning URLs regardless of whether an object-type
# segment (e.g. "Account/") is present, e.g.:
#   https://.../lightning/r/0016e00003LcC7YAAV/view
#   https://.../lightning/r/Account/0016e00003LcM7tAAF/view
SF_RECORD_ID_RE = re.compile(r"/r/(?:[A-Za-z]+/)?([A-Za-z0-9]{15,18})(?:/|$)")


def _extract_sf_id(url):
    """Return the Salesforce record ID embedded in a lightning/report URL, or None if not found."""
    if not url:
        return None
    match = SF_RECORD_ID_RE.search(url)
    return match.group(1) if match else None


def _build_gsheet_index(gsheet_values, gsheet_hyperlinks):
    """Return a dict mapping Salesforce record ID -> exact account text, from parallel gsheet_read outputs."""
    index = {}
    for row_values, row_links in zip(gsheet_values or [], gsheet_hyperlinks or []):
        name = row_values[0] if row_values else None
        url = row_links[0] if row_links else None
        sf_id = _extract_sf_id(url)
        if name and sf_id:
            index[sf_id] = name
    return index


def _flatten_tasks(account):
    """Return every task across all of an account's opportunities as a single flat list."""
    return [
        task
        for opportunity in account.get("opportunities", [])
        for task in opportunity.get("tasks", [])
    ]


def match_sf_accounts(report_accounts, gsheet_values, gsheet_hyperlinks):
    """Match parsed Salesforce report accounts to Google Sheet rows by Salesforce record ID."""
    if report_accounts is None:
        raise AnsibleFilterError("match_sf_accounts requires a list of report accounts, got None.")

    gsheet_index = _build_gsheet_index(gsheet_values, gsheet_hyperlinks)

    matched = []
    for account in report_accounts:
        sf_id = _extract_sf_id(account.get("account_url"))
        gsheet_name = gsheet_index.get(sf_id) if sf_id else None
        if not gsheet_name:
            continue

        matched.append(
            {
                "lookup_value": gsheet_name,
                "account": account.get("account"),
                "account_url": account.get("account_url"),
                "total_opps": account.get("total_opps", 0),
                "total_tasks": account.get("total_tasks", 0),
                "tasks": _flatten_tasks(account),
            }
        )

    return matched


class FilterModule:
    """Ansible core jinja2 filters for matching Salesforce report accounts to Google Sheet rows."""

    def filters(self):
        return {
            "match_sf_accounts": match_sf_accounts,
        }
