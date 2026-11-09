#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, Zachary LeBlanc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: gmail_search
short_description: Search Gmail messages and retrieve their contents
version_added: "1.1.0"
description:
    - Searches a Gmail mailbox using basic filters (O(from_addr), O(to), O(subject), O(labels)) and/or a raw Gmail search O(query).
    - Retrieves up to O(max_results) matching messages, most recent first.
    - Authenticates using OAuth2 installed-app credentials (O(client_id), O(client_secret), O(refresh_token)) rather than a
      service account, since Gmail access requires a specific user's consent.
author:
    - Zachary LeBlanc
options:
    client_id:
        description:
            - OAuth2 client ID from the Google Cloud project's installed-app credentials.
            - When omitted, the module uses the C(GOOGLE_CLIENT_ID) environment variable.
        type: str
    client_secret:
        description:
            - OAuth2 client secret paired with O(client_id).
            - When omitted, the module uses the C(GOOGLE_CLIENT_SECRET) environment variable.
        type: str
        no_log: true
    refresh_token:
        description:
            - OAuth2 refresh token obtained via a one-time consent flow (see C(scripts/google_oauth_setup.py)).
            - When omitted, the module uses the C(GOOGLE_REFRESH_TOKEN) environment variable.
        type: str
        no_log: true
    from_addr:
        description:
            - Filter messages sent from this address. Maps to the Gmail C(from:) search operator.
        type: str
    to:
        description:
            - Filter messages sent to this address. Maps to the Gmail C(to:) search operator.
        type: str
    subject:
        description:
            - Filter messages whose subject contains this text. Maps to the Gmail C(subject:) search operator.
        type: str
    labels:
        description:
            - Filter messages having all of these Gmail labels (e.g. C(INBOX), C(UNREAD), or custom label names).
            - Maps to the Gmail C(label:) search operator, one clause per label.
            - Spaces in label names are converted to dashes to match Gmail search syntax
              (e.g. C(RHSC/Tasks Report) becomes C(label:RHSC/Tasks-Report)).
        type: list
        elements: str
    after:
        description:
            - Only include messages after this date. Maps to the Gmail C(after:) search operator.
        type: str
    before:
        description:
            - Only include messages before this date. Maps to the Gmail C(before:) search operator.
        type: str
    query:
        description:
            - A raw Gmail search query string, using any supported Gmail search operators.
            - Appended alongside O(from_addr), O(to), O(subject), O(labels), O(after), and O(before) so both can be combined.
        type: str
    max_results:
        description:
            - Maximum number of messages to return, most recent first.
            - Set to C(1) to retrieve a single (most recent) matching message.
        type: int
        default: 5
    message_format:
        description:
            - Level of detail to retrieve for each matching message.
            - C(minimal) returns only IDs and labels.
            - C(metadata) additionally returns headers (from/to/subject/date) and a snippet.
            - C(full) additionally returns the decoded message body.
        type: str
        choices: [minimal, metadata, full]
        default: metadata
requirements:
    - google-api-python-client
    - google-auth
'''

EXAMPLES = r'''
- name: Get the single most recent unread message in the inbox
  zjleblanc.gsuite.gmail_search:
    labels:
      - INBOX
      - UNREAD
    max_results: 1
    message_format: full
  register: latest_unread

- name: Get the top 3 messages from a specific sender with a subject match
  zjleblanc.gsuite.gmail_search:
    from_addr: alerts@example.com
    subject: "Deployment failed"
    max_results: 3
  register: deployment_alerts

- name: Search using explicit OAuth2 credentials and a raw query
  zjleblanc.gsuite.gmail_search:
    client_id: "{{ vault_google_client_id }}"
    client_secret: "{{ vault_google_client_secret }}"
    refresh_token: "{{ vault_google_refresh_token }}"
    query: "has:attachment newer_than:7d"
    max_results: 10

- name: Fail the play if no invoice email arrived this month
  zjleblanc.gsuite.gmail_search:
    from_addr: billing@example.com
    subject: Invoice
    after: "2026/08/01"
  register: invoice_search
  failed_when: invoice_search.messages | length == 0
'''

RETURN = r'''
messages:
    description: List of matching messages, most recent first.
    type: list
    elements: dict
    returned: success
    contains:
        id:
            description: Gmail message ID.
            type: str
        thread_id:
            description: Gmail thread ID the message belongs to.
            type: str
        from:
            description: Value of the C(From) header.
            type: str
        to:
            description: Value of the C(To) header.
            type: str
        subject:
            description: Value of the C(Subject) header.
            type: str
        date:
            description: Value of the C(Date) header.
            type: str
        snippet:
            description: Short plaintext preview of the message.
            type: str
        label_ids:
            description: Gmail label IDs applied to the message.
            type: list
            elements: str
        body:
            description: Decoded message body. Only present when O(message_format=full).
            type: str
total_estimate:
    description: Gmail's estimated total number of messages matching the query (may exceed the number returned).
    type: int
    returned: success
query:
    description: The final Gmail search query string used, after combining filters and O(query).
    type: str
    returned: success
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.zjleblanc.gsuite.plugins.module_utils.auth import (
    GMAIL_READONLY_SCOPES,
    OAUTH_ARGSPEC,
    HttpError,
    build,
    check_google_deps,
    load_oauth_credentials,
    resolve_oauth_param,
)
from ansible_collections.zjleblanc.gsuite.plugins.module_utils.gmail import (
    build_query,
    parse_message,
)

GOOGLE_CLIENT_ID_ENV = "GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET_ENV = "GOOGLE_CLIENT_SECRET"
GOOGLE_REFRESH_TOKEN_ENV = "GOOGLE_REFRESH_TOKEN"


def list_message_ids(service, query, max_results):
    """Return message stubs (id/threadId) matching the query."""
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    return result.get("messages", []), result.get("resultSizeEstimate", 0)


def get_message(service, message_id, message_format):
    """Retrieve a single message at the requested detail level."""
    return (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format=message_format)
        .execute()
    )


def main():
    module = AnsibleModule(
        argument_spec=dict(
            OAUTH_ARGSPEC,
            from_addr=dict(type="str"),
            to=dict(type="str"),
            subject=dict(type="str"),
            labels=dict(type="list", elements="str"),
            after=dict(type="str"),
            before=dict(type="str"),
            query=dict(type="str"),
            max_results=dict(type="int", default=5),
            message_format=dict(
                type="str",
                choices=["minimal", "metadata", "full"],
                default="metadata",
            ),
        ),
        supports_check_mode=True,
    )

    check_google_deps(module)

    client_id = resolve_oauth_param(module.params["client_id"], GOOGLE_CLIENT_ID_ENV)
    client_secret = resolve_oauth_param(module.params["client_secret"], GOOGLE_CLIENT_SECRET_ENV)
    refresh_token = resolve_oauth_param(module.params["refresh_token"], GOOGLE_REFRESH_TOKEN_ENV)

    if not (client_id and client_secret and refresh_token):
        module.fail_json(
            msg=(
                "OAuth2 credentials required: set client_id, client_secret, and refresh_token, "
                "or the GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN "
                "environment variables"
            )
        )

    max_results = module.params["max_results"]
    if not 1 <= max_results <= 500:
        module.fail_json(msg="max_results must be between 1 and 500")

    message_format = module.params["message_format"]

    query = build_query(
        from_addr=module.params["from_addr"],
        to=module.params["to"],
        subject=module.params["subject"],
        labels=module.params["labels"],
        after=module.params["after"],
        before=module.params["before"],
        query=module.params["query"],
    )

    if module.check_mode:
        module.exit_json(
            changed=False,
            messages=[],
            total_estimate=0,
            query=query,
            check_mode=True,
        )

    try:
        creds = load_oauth_credentials(
            client_id, client_secret, refresh_token, scopes=GMAIL_READONLY_SCOPES
        )
    except Exception as exc:
        module.fail_json(msg=f"Failed to obtain OAuth2 access token: {exc}")

    try:
        service = build("gmail", "v1", credentials=creds)
        message_stubs, total_estimate = list_message_ids(service, query, max_results)
    except HttpError as exc:
        module.fail_json(msg=f"Gmail API error: {exc}")
    except Exception as exc:
        module.fail_json(msg=f"Failed to search Gmail: {exc}")

    messages = []
    try:
        for stub in message_stubs:
            raw_msg = get_message(service, stub["id"], message_format)
            messages.append(parse_message(raw_msg, message_format))
    except HttpError as exc:
        module.fail_json(msg=f"Gmail API error: {exc}")
    except Exception as exc:
        module.fail_json(msg=f"Failed to retrieve message: {exc}")

    module.exit_json(
        changed=False,
        messages=messages,
        total_estimate=total_estimate,
        query=query,
    )


if __name__ == "__main__":
    main()
