# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
    name: recent_tasks
    short_description: Filter a list of Salesforce task dicts to only those within the last N months
    version_added: "1.3.0"
    description:
        - Given a list of task dictionaries (as produced by M(zjleblanc.gsuite.parse_sf_tasks) or the flattened
          C(tasks) list from M(zjleblanc.gsuite.match_sf_accounts)), returns only those whose C(date) field falls
          within the last N months from today.
        - Tasks with missing or unparseable dates are excluded from the result.
    positional: _input, months
    options:
        _input:
            description: List of task dictionaries, each expected to have a C(date) key in C(m/d/Y) format.
            type: list
            elements: dict
            required: true
        months:
            description: Number of months to look back from today. Defaults to C(3).
            type: int
            default: 3
'''

EXAMPLES = r'''
- name: Keep only tasks from the last 3 months
  ansible.builtin.set_fact:
    recent: "{{ account.tasks | zjleblanc.gsuite.recent_tasks(3) }}"

- name: Keep only tasks from the last 6 months
  ansible.builtin.set_fact:
    recent: "{{ account.tasks | zjleblanc.gsuite.recent_tasks(6) }}"
'''

RETURN = r'''
_value:
    description: Subset of input tasks whose date is within the specified window.
    type: list
    elements: dict
'''

from datetime import datetime, date

from ansible.errors import AnsibleFilterError


def _parse_task_date(date_str):
    """Parse report date strings like '3/11/2026' into a date object, or None on failure."""
    if not date_str:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _months_ago(months):
    """Return a date object representing N months before today."""
    today = date.today()
    month = today.month - months
    year = today.year
    while month < 1:
        month += 12
        year -= 1
    day = min(today.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                          31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def recent_tasks(tasks, months=3):
    """Filter a list of task dicts to only those within the last N months."""
    if tasks is None:
        return []
    if not isinstance(months, int) or months < 1:
        raise AnsibleFilterError("recent_tasks 'months' parameter must be a positive integer, got: %r" % months)

    cutoff = _months_ago(months)
    result = []
    for task in tasks:
        task_date = _parse_task_date(task.get("date", ""))
        if task_date is not None and task_date >= cutoff:
            result.append(task)
    return result


class FilterModule:
    """Ansible jinja2 filters for filtering Salesforce tasks by recency."""

    def filters(self):
        return {
            "recent_tasks": recent_tasks,
        }
