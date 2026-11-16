# Data Flow — Support Case Tracker

How `playbooks/pb_track_support_cases.yml` interacts with external services (one read + one
write for the whole run, regardless of account count).

```mermaid
sequenceDiagram
  participant Playbook
  participant SSO as RedHatSSO
  participant GQL as GraphQLAPI
  participant Sheet as GoogleSheet
  participant Mail

  Playbook->>SSO: Exchange offline token
  SSO-->>Playbook: Bearer token

  Playbook->>Sheet: "gsheet_tracker state=read (once)"
  Sheet-->>Playbook: existing_rows, other_rows, accounts map
  loop per account
    Playbook->>GQL: "query RedHatSupportCase where: account in [...], status != Closed"
    GQL-->>Playbook: Every currently open case for the account
    Playbook->>Playbook: "gsheet_tracker state=diff (no API call)"
  end
  Playbook->>Sheet: "gsheet_tracker state=write (once)"
  loop per tracker_notifications pairing
    Playbook->>Mail: email scoped to all or named accounts
  end
```

## Flow

1. **SSO token exchange** — same as the analyzer, via the token-exchange task in
   `playbooks/pb_track_support_cases.yml`.
2. **Read previous state once for every account** — `zjleblanc.rh_case_mgmt.gsheet_tracker` with
   `state: read` is called a single time (before the per-account loop, not inside it) and returns
   each account's previous rows (`total_previous`, `last_seen_timestamp` as a stamp only) plus
   `other_rows` (raw rows for accounts outside this run, preserved verbatim) and `existing_rows`
   (the full matrix, for the per-account diff step).
3. **GraphQL fetch (per account)** — `zjleblanc.rh_case_mgmt.graphql_cases` with
   `include_description: false` and `status_filter: tracker_status_filter` (default
   `{ne: "Closed"}`) fetches every currently non-closed case for the account
   (see [tasks/account_track.yml](../../tasks/account_track.yml)). That full open-case snapshot is
   what the sheet stores and what the next run diffs against, so unchanged open cases stay on the
   tab and are not reclassified as new.
4. **Diff (per account, no API calls)** — `zjleblanc.rh_case_mgmt.gsheet_tracker` with `state: diff`
   compares the full current open set against the relevant slice of `existing_rows`, returns
   new/closed/updated case lists, and builds that account's replacement rows (accumulated into a
   playbook-level fact).
5. **Write once** — after every account has been processed, `state: write` writes `other_rows` +
   every account's accumulated rows in a single clear+rewrite, and maintains a Sheets API Table
   (`gsheet_table_name`, defaults to `gsheet_sheet`) over the result.
6. **Email notifications** — after the single sheet write, the playbook loops
   `tracker_notifications` (or a legacy one-pairing fallback from `tracker_email_to`). Each
   pairing sends one `community.general.mail` message (rendered from
   [templates/support_case_tracking_email.html.j2](../../templates/support_case_tracking_email.html.j2))
   scoped to `accounts: all` or a named subset. A pairing is sent when its scoped accounts have
   diffs (or always, when `tracker_notify_on_no_changes: true`).

See [../support-analyzer/DATA_FLOW.md](../support-analyzer/DATA_FLOW.md) for the analyzer
workflow's data flow (which shares the SSO step but writes to a different Google Sheet tab and
uses an LLM).
