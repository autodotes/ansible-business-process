# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
    name: modified_ago
    short_description: Format a last-modified timestamp as a relative English age
    version_added: "1.0.0"
    description:
        - Converts a last-modified timestamp into a short English relative age for display
          (for example in the support case tracker email).
        - Ages of 30 days or less use days; greater than 30 days up to 90 days use weeks
          (C(days // 7)); greater than 90 days use months (C(days // 30)).
        - Accepts ISO-8601 strings and Google Sheets date serial numbers. Missing or
          unparseable values return an em dash. Future timestamps are treated as 0 days.
    positional: _input
    options:
        _input:
            description: >-
                Last-modified value as an ISO-8601 string (with or without milliseconds,
                C(Z) or an offset) or a Google Sheets date serial number.
            type: raw
            required: true
"""

EXAMPLES = r"""
- name: Render relative last-modified ages for email rows
  ansible.builtin.debug:
    msg: "{{ case.last_modified | zjleblanc.rh_case_mgmt.modified_ago }}"
"""

RETURN = r"""
_value:
    description: Relative age string such as C(3 days ago), or an em dash when unknown.
    type: str
"""

from datetime import datetime, timedelta, timezone

# Google Sheets serial day 0 is 1899-12-30 (Lotus 1-2-3 compatibility epoch).
_SHEETS_EPOCH = datetime(1899, 12, 30, tzinfo=timezone.utc)
_EM_DASH = "\u2014"


def _parse_timestamp(value):
    """Return an aware UTC datetime, or None when the value is missing/unparseable."""
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return _SHEETS_EPOCH + timedelta(days=float(value))

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    try:
        return _SHEETS_EPOCH + timedelta(days=float(text))
    except ValueError:
        pass

    iso = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pluralize(count, singular):
    """Return ``N singular`` or ``N singulars`` for English unit labels."""
    unit = singular if count == 1 else singular + "s"
    return f"{count} {unit} ago"


def modified_ago(value, now=None):
    """Format a last-modified value as a relative English age string."""
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    stamp = _parse_timestamp(value)
    if stamp is None:
        return _EM_DASH

    days = (now - stamp).days
    if days < 0:
        days = 0

    if days <= 30:
        return _pluralize(days, "day")
    if days <= 90:
        return _pluralize(days // 7, "week")
    return _pluralize(days // 30, "month")


class FilterModule:
    """Ansible Jinja2 filters for relative last-modified wording."""

    def filters(self):
        return {
            "modified_ago": modified_ago,
        }
