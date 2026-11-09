# Changelog

## 2026-11-09 — Scope tracker emails with notification pairings

### Added
- `tracker_notifications` on `playbooks/pb_track_support_cases.yml`: a list of `{to, accounts}`
  pairings so one run can email different recipient lists scoped to `all` pulled accounts or a
  named subset, after a single Google Sheet read/write.

### Changed
- Tracker email sending now loops pairings after the sheet write; each message uses a scoped
  `notification_results` slice in `templates/support_case_tracking_email.html.j2`.
- Legacy `tracker_email_to` still works when `tracker_notifications` is omitted (one pairing with
  `accounts: all`). Both `to` and `support_case_accounts` must be non-empty lists.
- Docs updated in `docs/support-tracker/EXAMPLES.md`, `docs/support-tracker/DATA_FLOW.md`, and
  `docs/common/USAGE.md`.

## 2026-10-12 — Add Sheets-friendly date format defaults for support tracker vars

### Changed
- Added `gsheet_date_format` and `gsheet_datetime_format` defaults to
  `playbooks/vars/track_support_cases.yml` so tracker date/time formatting is
  explicit and spreadsheet-friendly.
- Updated `activity_date` in `playbooks/vars/track_support_cases.yml` to use
  `strftime(gsheet_date_format)` instead of an inline hard-coded format.

## 2026-10-12 — Default support tracker runtime inputs from environment variables

### Changed
- Updated `playbooks/vars/track_support_cases.yml` to default tracker runtime
  inputs from environment variables: `REDHAT_OFFLINE_TOKEN`, `GSHEET_SHEET`,
  `GOOGLE_SHEET_ID`, and `GOOGLE_SA_CRED_PATH` (with `tower.filename` fallback
  for credentials path), while keeping `gsheet_id` aligned to the env-backed
  sheet id.
- Updated `playbooks/pb_track_support_cases.yml` validation to also require a
  non-empty `gsheet_id` before execution.

## 2026-10-12 — Filter stale closed support cases server-side for analyzer runs

### Changed
- Added `analyze_closed_case_days: 90` to
  `playbooks/vars/analyze_support_cases.yml` to make closed-case retention
  explicit and configurable for analyzer payload control.
- Updated `tasks/account_analyze.yml` to apply a server-side GraphQL
  `extra_where` filter when fetching cases, keeping all non-closed cases plus
  only closed cases updated within the configured retention window.
- Updated the analyzer "no cases" debug message to clarify that closed cases are
  included only when updated within the retention window.

## 2026-10-12 — Reduce Google Sheets support report payload size

### Changed
- Slimmed `templates/support_case_analysis.json.j2` to remove duplicated per-case
  arrays from `accounts[].cases_by_severity[]` and `products[]`, keeping count
  summaries while preserving the detailed top-level `cases[]` list.
- Updated `case_detail` in `templates/support_case_analysis.json.j2` to include
  `description` only for priority products matched by keyword substring
  (`gsheet_truncate_priority_products`), instead of including descriptions for
  every case.
- Updated support analyzer defaults in `playbooks/vars/analyze_support_cases.yml`
  to use `gsheet_truncate_priority_products: ["Ansible"]` so all Ansible product
  variants are treated as priority.
- Updated `business.support.gsheet_update` priority matching in
  `collections/ansible_collections/business/support/plugins/modules/gsheet_update.py`
  from exact product-name matching to case-insensitive substring keyword matching,
  and aligned module docs/defaults to `["Ansible"]`.

## 2026-10-12 — Externalize support-case playbook defaults into vars files

### Added
- New playbook vars files under `playbooks/vars/`: `analyze_support_cases.yml` and
  `track_support_cases.yml`, each organized by concern and annotated with brief
  section-purpose headers.
- Scoped Cursor rule at `.cursor/rules/playbooks-vars-convention.mdc` to enforce
  the `playbooks/vars/` + `vars_files` pattern and section header usage for grouped vars.

### Changed
- `playbooks/pb_analyze_support_cases.yml` now loads defaults via
  `vars_files: [vars/analyze_support_cases.yml]` instead of a large inline `vars` block.
- `playbooks/pb_track_support_cases.yml` now loads defaults via
  `vars_files: [vars/track_support_cases.yml]` instead of a large inline `vars` block.
- Support analyzer defaults now map required runtime inputs from environment variables
  in `playbooks/vars/analyze_support_cases.yml` (LLM model/key/base URL, Google Sheet
  identifiers/columns/credential path, and Red Hat offline token).

## 2026-10-04 — Merge ansible-support-analyzer (analyzer + tracker workflows)

### Added
- New `business.support` collection
  (`collections/ansible_collections/business/support/`) with four modules migrated from
  `ansible-support-analyzer`'s `library/`: `graphql_cases` (Red Hat GraphQL case fetch with
  server-side filtering/pagination), `llm_summarize` (OpenAI-compatible case summarization),
  `gsheet_update` (service-account-only cell update with smart JSON truncation), and
  `gsheet_tracker` (read/diff/write case-tracking states against a dedicated worksheet tab).
  This `gsheet_update` is intentionally kept separate from the existing
  `business.google.gsheet_update` (different auth model and write semantics — see the new
  collection's README for the comparison).
- Two new playbooks: `playbooks/pb_analyze_support_cases.yml` (AI-powered support case
  analysis into a Google Sheet / markdown / PDF report) and
  `playbooks/pb_track_support_cases.yml` (incremental case change tracking with e-mail
  notifications), each using FQCNs for all `business.support` module calls.
- Two new task files: `tasks/account_analyze.yml` and `tasks/account_track.yml` (per-account
  logic included by the two new playbooks).
- Three new templates under `templates/`: `support_case_analysis.md.j2`,
  `support_case_analysis.json.j2`, and `support_case_tracking_email.html.j2`.
- New `docs/` tree with `docs/support-analyzer/` (QUICKSTART, LLM_CONFIGURATION,
  IMPLEMENTATION_SUMMARY, DATA_FLOW, EXAMPLES, and the archived original changelog —
  `CHANGELOG.archive.md`), `docs/support-tracker/` (DATA_FLOW, EXAMPLES), and `docs/common/`
  (GSUITE_QUICKSTART, USAGE) for documentation spanning both workflows.
- Two new AAP job templates in `aap_config/controller/templates.yml` ("BPA // Support Case
  Analyzer", "BPA // Support Case Tracker"), two new credential types in
  `aap_config/controller/credential_types.yml` ("Ansible Support Analyzer", "SMTP Server"), and
  three new credential instances in `aap_config/controller/credentials.yml`.
- `openai`, `requests`, and `python-dateutil` added to
  `execution-environment/requirements/requirements.txt`; `community.general` and the new
  `business.support` collection added to `collections/requirements.yml`.
- `scripts/generate_pdf.js` (optional Puppeteer-based PDF helper for the analyzer's `pdf` tag).
- `reports/` and `refs/` added to `.gitignore`.

### Notes
- This is a merge, not a rewrite: the original `ansible-support-analyzer` repository's own
  changelog is preserved verbatim at
  [docs/support-analyzer/CHANGELOG.archive.md](docs/support-analyzer/CHANGELOG.archive.md)
  rather than interleaved with this file.
- The incoming repo's `group_vars/all/vars.yml` defaults were inlined into each new playbook's
  `vars:` section instead of introducing a `group_vars/` directory, matching this repo's
  existing pattern of playbook-local defaults plus `vault.yml` for secrets.

## 2026-08-12 — Limit account activity summaries to the last 3 months

### Added
- `business.google.recent_tasks` filter plugin to keep only Salesforce tasks whose date falls within the last N months (default 3).

### Changed
- Account dashboard updates now summarize and write only tasks from the last 3 months; when none remain, columns F and G are set to `{}` and the AI call is skipped.
- Annotated parser loop state in `parse_sf_tasks` so Pylint no longer flags `current_account` as unsubscriptable.

---

## 2026-08-12 — Require gsheet and gmail vars for account dashboard playbook

### Changed
- `pb_update_account_tasks.yml` now asserts required AI, Gmail, and Google Sheets variables up front (with inline example values) instead of defaulting sheet/range settings in the playbook `vars` section.
- Updated `vault.yml` to supply the required playbook variables for local runs.
- Ignored `*.log` files in `.gitignore`.

---

## 2026-08-12 — Migrate parse_sf_tasks filter from business.custom to business.google

### Changed
- Moved `parse_sf_tasks` filter plugin from `business.custom` to `business.google` — the FQCN is now `business.google.parse_sf_tasks`.
- `parse_sf_tasks` now returns a dict (with an `accounts` key) instead of a plain list, adding `total_tasks`, `total_opps`, and `total_accounts` summary counts at the root, account, and opportunity levels.
- Updated `gmail_tasks_report.yml` playbook to use the new FQCN.
- Moved `beautifulsoup4` dependency under the `business.google` group in `requirements.txt`.

### Removed
- Removed the `business.custom` collection (its only content was `parse_sf_tasks`).

---

## 2026-08-12 — Support OAuth2 credentials in gsheet_update alongside service accounts

### Added
- `SHEETS_COMBINED_ARGSPEC` and `SHEETS_COMBINED_MUTUALLY_EXCLUSIVE` in `business.google`'s `module_utils/auth.py`, merging the service-account and OAuth2 argument specs and enforcing that only one credential type is provided at a time.

### Changed
- `gsheet_update` now authenticates with either a Google service account (`credentials_path`/`credentials`) or an OAuth2 installed-app client (`client_id`/`client_secret`/`refresh_token`), so the same OAuth2 client already used by `gmail_search` can also update Sheets.
- `scripts/google_oauth_setup.py` now requests both the `gmail.readonly` and `spreadsheets` scopes by default, so a single refresh token works for both `gmail_search` and `gsheet_update`.
- Updated the `business.google` collection README to document the dual authentication options for `gsheet_update` and note that existing Gmail-only refresh tokens must be regenerated to also cover Sheets.
