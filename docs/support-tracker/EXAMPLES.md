# Usage Examples — Support Case Tracker

Practical examples for `playbooks/pb_track_support_cases.yml`. See
[../support-analyzer/EXAMPLES.md](../support-analyzer/EXAMPLES.md) for the analyzer workflow's
examples; see [../support-analyzer/QUICKSTART.md](../support-analyzer/QUICKSTART.md) for base
credential setup shared by both workflows.

`playbooks/pb_track_support_cases.yml` is a separate, lightweight playbook designed to run as its
**own job template** on a cadence (cron, AAP schedule, etc.). Each run:

1. Reads the tracker sheet **once, for every tracked account at the same time** (via
   `zjleblanc.rh_case_mgmt.gsheet_tracker state=read`) to retrieve each account's `last_seen_timestamp`
   from the previous run, plus the raw rows belonging to any account *not* in this run
   (`other_rows`).
2. Per account, queries only non-closed cases modified **since that account's previous run**
   through the GraphQL API (`status_filter`, default `{ne: "Closed"}`, excludes closed cases
   server-side) — avoids re-fetching the entire case history on every cadence tick.
3. Diffs the current cases against what was recorded on the previous run (new / closed / changed
   severity, status, or owner) via `zjleblanc.rh_case_mgmt.gsheet_tracker state=diff` — a pure local
   computation with **no Google API calls** — and accumulates that account's replacement rows.
4. After every account has been processed, writes the whole tab **exactly once**
   (`zjleblanc.rh_case_mgmt.gsheet_tracker state=write`: `other_rows` + every account's accumulated
   rows in a single clear+rewrite) — a dedicated worksheet tab that the `gsheet_tracker` module
   owns completely (header row and all data rows). It is *not* the `Accounts` tab used by
   `pb_analyze_support_cases.yml`, and does not rely on that playbook's lookup/update column
   configuration. Treat it as its own green-field tab (default name: `Support Case Tracker`).
   The same step also creates/resizes a Sheets API Table over the tab, named `gsheet_table_name`
   (defaults to the sheet name).
5. Emails one or more change summaries via `community.general.mail`, one message per
   `tracker_notifications` pairing. Each pairing scopes the body to `accounts: all` or a named
   subset of the pulled accounts. A pairing is sent only when its scoped accounts have changes,
   unless `tracker_notify_on_no_changes: true`.

The date cutoff is resolved in order: `tracker_last_run_date` (manual override via `-e`) → sheet
`last_seen_timestamp` → `activity_date` fallback.

No matter how many accounts are tracked, each run makes exactly **one** read and **one** write
against the Google Sheets API (plus one small `batchUpdate` for table maintenance) — not one
read/write pair per account.

No LLM is required for this playbook.

## Credentials

`pb_track_support_cases.yml` leverages the **same credential type definitions** as
`pb_analyze_support_cases.yml` (see
[aap_config/controller/credential_types.yml](../../aap_config/controller/credential_types.yml)),
but as a separate job template it attaches its own, separate credentials:

1. **"Ansible Support Analyzer"** — a *second Credential instance* of the same credential type
   used by `pb_analyze_support_cases.yml` (Red Hat offline token, Google service account JSON,
   `google_sheet_id`, etc.). Leave `gsheet_sheet` at its default (`Support Case Tracker`) on this
   instance — only the `pb_analyze_support_cases.yml` job template's Credential overrides it to
   `Accounts`.
2. **"SMTP Server"** — also defined in
   [aap_config/controller/credential_types.yml](../../aap_config/controller/credential_types.yml),
   mirrored from
   [ansible-cac's credential_types.yml](https://github.com/zjleblanc/ansible-cac/blob/main/config/common/credential_types.yml).
   Supplies `email_smtp_server`, `email_smtp_server_port`, `email_smtp_username`,
   `email_smtp_password`, and `email_smtp_from_address` as `extra_vars` for the
   change-notification email. Only the tracker job template needs this credential.

No `TRACKER_*` environment variables are used anywhere in this project.

## Setup

```bash
# community.general is already part of collections/requirements.yml in this repo
```

```yaml
# vault.yml
redhat_offline_token: "your-redhat-offline-token"
google_credentials_path: "/path/to/service-account.json"
gsheet_id: "your-spreadsheet-id"
# Optional: override the dedicated tracker tab name (default: "Support Case Tracker")
# gsheet_sheet: "Support Case Tracker"
```

SMTP settings and notification recipients are plain extra vars — pass them with `-e` or add them
to `vault.yml`. Prefer `tracker_notifications` when different recipient groups should see
different account scopes from a single run:

```yaml
# my_notifications.yml
tracker_notifications:
  - to:
      - team@example.com
      - oncall@example.com
    accounts: all
  - to:
      - region-team@example.com
    accounts:
      - Parasol
      - Acme Corp
```

```bash
ansible-navigator run playbooks/pb_track_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml -e @my_notifications.yml \
  -e email_smtp_server="smtp.example.com" \
  -e email_smtp_server_port="587" \
  -e email_smtp_username="notifier@example.com" \
  -e email_smtp_password="..." \
  -e email_smtp_from_address="support-tracker@example.com" \
  -e tracker_smtp_secure="starttls"
```

Each pairing requires a non-empty `to` list. `accounts` must be the string `all` (every account
pulled in this run) or a non-empty list of names that match `support_case_accounts[].name`.
Accounts still get fetched and written even when no pairing names them; they appear in email
only via an `all` pairing.

Legacy single-recipient mode still works: omit `tracker_notifications` and set
`tracker_email_to` to a non-empty list. The playbook builds one pairing with `accounts: all`.
If both are set, `tracker_notifications` is used.

`tracker_smtp_secure` (optional: `try`|`always`|`never`|`starttls`), `tracker_notifications`,
and `tracker_email_to` are plain playbook variables — they are **not** sourced from any
credential type, so set them with `-e` or as extra vars on the job template either way.

## Run once

```bash
ansible-navigator run playbooks/pb_track_support_cases.yml -e @vault.yml -e @my_accounts.yml
```

## Run on a cadence (cron)

```bash
# Every 4 hours
0 */4 * * * cd /path/to/ansible-business-process && ansible-navigator run playbooks/pb_track_support_cases.yml -e @vault.yml -e @my_accounts.yml --mode stdout >> /var/log/support-case-tracker.log 2>&1
```

## Always send a notification, even with no changes

```bash
ansible-navigator run playbooks/pb_track_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -e tracker_notify_on_no_changes=true
```

## Override the last-run date cutoff

Force the tracker to re-fetch all cases modified since a specific date, ignoring the sheet's
stored `last_seen` timestamp:

```bash
ansible-navigator run playbooks/pb_track_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -e tracker_last_run_date="2026-01-01T00:00:00Z"
```

## What gets written to the sheet

Each run rewrites the entire tracker tab exactly once, with columns:

`Account | Case ID | Summary | Product | Severity | Status | Owner | Created | Last Modified | Last Seen`

Rows for accounts not in this run's `support_case_accounts` list are carried through verbatim
(including any `HYPERLINK` formulas in the Case ID column); rows for every tracked account are
replaced with that account's freshly-diffed rows.

## What the module returns, by state

The `zjleblanc.rh_case_mgmt.gsheet_tracker` module (see
[collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/gsheet_tracker.py](../../collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/gsheet_tracker.py))
has three states, called in this order once per run:

- **`state: read`** (once, before the account loop) — returns `existing_rows` (the full raw
  matrix, passed into every `diff` call), `other_rows` (untouched accounts' rows, passed into
  the final `write` call), and `accounts` — a dict keyed by account name with
  `last_seen_timestamp` / `total_previous` for each — without writing anything. This powers the
  incremental GraphQL fetch described above.
- **`state: diff`** (once per account, no API calls) — returns `new_cases`, `closed_cases`,
  `updated_cases` (with before/after values for severity, status, and owner), `total_current` /
  `total_previous` counts, and `rows` (that account's freshly-built replacement rows to
  accumulate). These drive the per-account debug summary and are filtered into
  `notification_results` for each email pairing
  ([templates/support_case_tracking_email.html.j2](../../templates/support_case_tracking_email.html.j2)).
- **`state: write`** (once, after the account loop) — takes the fully assembled `rows` (every
  account's accumulated rows, concatenated with `other_rows`) and performs the single
  clear+rewrite, plus best-effort Table maintenance (`table_name`).

## Getting help

- Analyzer workflow examples: [../support-analyzer/EXAMPLES.md](../support-analyzer/EXAMPLES.md)
- Google Sheets: [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md)
- Running on Ansible Automation Platform: [../common/USAGE.md](../common/USAGE.md)
