# Usage Guide: Running on Ansible Automation Platform

End-to-end setup guide for running `playbooks/pb_analyze_support_cases.yml` and
`playbooks/pb_track_support_cases.yml` as job templates on Ansible Automation Platform (AAP) /
Controller. It covers the Google service account, the SMTP credential used for
change-notification emails, the two custom Credential Types, the Credentials built from them,
the Execution Environment, and the Job Templates themselves — all expressed as configuration as
code under [aap_config/](../../aap_config/) per this repo's
[aap-config-as-code skill](../../.cursor/skills/aap-config-as-code/SKILL.md).

If you only want to run the playbooks locally from the CLI, see
[../support-analyzer/QUICKSTART.md](../support-analyzer/QUICKSTART.md) and
[GSUITE_QUICKSTART.md](GSUITE_QUICKSTART.md) instead — this guide is specifically about the
AAP/Controller path.

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Set up the Google service account (Sheets API)](#2-set-up-the-google-service-account-sheets-api)
3. [Obtain an SMTP credential (for change-notification emails)](#3-obtain-an-smtp-credential-for-change-notification-emails)
4. [Gather the remaining credential values](#4-gather-the-remaining-credential-values)
5. [Credential Types in aap_config](#5-credential-types-in-aap_config)
6. [Credentials in aap_config](#6-credentials-in-aap_config)
7. [Execution Environment and Project](#7-execution-environment-and-project)
8. [Job Templates in aap_config](#8-job-templates-in-aap_config)
9. [Prepare the Google Sheet tabs](#9-prepare-the-google-sheet-tabs)
10. [Verify everything end-to-end](#10-verify-everything-end-to-end)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

- An AAP/Controller instance and an **Organization** you have admin rights on. This repo's
  [aap_config/](../../aap_config/) hardcodes `organization: Autodotes` throughout — either create
  an org with that exact name, or edit the files to use your own org name before deploying with
  `playbooks/pb_deploy_aap_config.yml`.
- A Google account (Workspace or personal Gmail) for both the service account (step 2) and the
  SMTP sender (step 3). They don't have to be the same account.
- A Red Hat offline token and an OpenAI-compatible LLM endpoint/key. These are consumed as
  Credential fields in step 6 but setting them up isn't AAP-specific — see
  [../support-analyzer/QUICKSTART.md](../support-analyzer/QUICKSTART.md) and
  [../support-analyzer/LLM_CONFIGURATION.md](../support-analyzer/LLM_CONFIGURATION.md) for how to
  obtain them.
- The project's existing custom Execution Environment (see
  [execution-environment/](../../execution-environment/)) must be rebuilt with the Python/Galaxy
  dependencies these two workflows need (step 7) — most minimal/official EE images have a
  read-only container filesystem, so installing `requirements.txt` at project-sync time usually
  isn't reliable.

## 2. Set up the Google service account (Sheets API)

This mirrors [GSUITE_QUICKSTART.md](GSUITE_QUICKSTART.md) §1; repeated here because the JSON key
it produces is pasted directly into an AAP Credential in step 6.

1. Open the [Google Cloud Console](https://console.cloud.google.com/), create or select a
   project, go to **APIs & Services → Library**, and enable the **Google Sheets API**.
2. **IAM & Admin → Service Accounts → Create service account** (e.g. `support-analyzer-sheets`).
   No project-level roles are required — access is granted by sharing the spreadsheet directly.
3. **Keys → Add key → Create new key → JSON**, and download the key file. Open it in a text
   editor; you'll paste its full contents into the `google_service_account_json` Credential
   field in step 6.
4. Note the service account's email address (`...@....iam.gserviceaccount.com`) from the key
   file or the Service Accounts list.
5. Open the target Google Sheet, click **Share**, and add the service account email as
   **Editor**.
6. Copy the spreadsheet ID out of the URL:
   `https://docs.google.com/spreadsheets/d/`**`SPREADSHEET_ID`**`/edit` — you'll need it for
   `google_sheet_id` in step 6.

## 3. Obtain an SMTP credential (for change-notification emails)

`pb_track_support_cases.yml` sends its change-notification email via `community.general.mail`
using plain SMTP credentials (not OAuth or an API). Any SMTP provider works; for Google/Gmail
SMTP specifically there are two supported routes:

### Option A — Gmail / Workspace account with an App Password (recommended)

Google no longer accepts a plain account password over SMTP; you need a 16-character **App
Password**, which requires 2-Step Verification to be enabled first.

1. Go to [Google Account → Security](https://myaccount.google.com/security) for the sending
   account and enable **2-Step Verification** if it isn't already.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), create
   a new app password (name it e.g. `ansible-support-analyzer`), and copy the 16-character
   password shown — it's only displayed once.
3. Record these values for step 6's "SMTP Server" Credential:
   - **Server**: `smtp.gmail.com`
   - **Port**: `587` (STARTTLS) — or `465` for implicit SSL
   - **Username**: the full Gmail/Workspace address (e.g. `notifier@example.com`)
   - **Password**: the app password from step 2 (not the account login password)
   - **From Address**: typically the same address as the username

Gmail enforces sending limits (~500/day for personal accounts, ~2,000/day for Workspace), which
is normally plenty for case-change notifications.

### Option B — Google Workspace SMTP relay service

For Workspace domains that want to avoid per-mailbox app passwords (e.g. sending as a shared
`no-reply@` address at higher volume):

1. In the [Admin console](https://admin.google.com/), go to **Apps → Google Workspace → Gmail →
   Routing → SMTP relay service** and add the configuration.
2. Allow-list the AAP/Controller's outbound IP address(es) under **Allowed senders**, since the
   relay authenticates by source IP rather than username/password in its simplest mode.
3. Use:
   - **Server**: your domain's relay hostname (often still `smtp-relay.gmail.com`)
   - **Port**: `587`
   - **Username**/**Password**: leave blank if relying on IP allow-listing, or set them if you
     configured the relay to require SMTP AUTH

Only use Option B if your AAP execution nodes have stable, allow-listable egress IPs — Option A
works from anywhere and is simpler to set up for most users.

## 4. Gather the remaining credential values

The "Ansible Support Analyzer" Credential Type (step 5) also needs non-Google values you'll set
on the Credential in step 6:

| Value | Where to get it |
|---|---|
| Red Hat offline token | [access.redhat.com/management/api](https://access.redhat.com/management/api) → **Generate Token** |
| LLM API key, base URL, model | Depends on provider (OpenAI, local vLLM/Ollama, etc.) — see [../support-analyzer/LLM_CONFIGURATION.md](../support-analyzer/LLM_CONFIGURATION.md) |

## 5. Credential Types in aap_config

[aap_config/controller/credential_types.yml](../../aap_config/controller/credential_types.yml)
defines both types as part of this repo's `controller_credential_types` list, in the format
consumed by `infra.aap_configuration.dispatch` (deployed via
`playbooks/pb_deploy_aap_config.yml`). This file already contains the "Google OAuth Client" and
"OpenAI Config" types used by the Salesforce account-tasks workflow; "Ansible Support Analyzer"
and "SMTP Server" are appended alongside them.

### Option A — Configuration as code (this repo's default)

```bash
ansible-navigator run playbooks/pb_deploy_aap_config.yml -e @vault.yml
```

This deploys every object under [aap_config/](../../aap_config/), including both new credential
types, in dependency-aware order.

### Option B — Manual UI setup

Go to **Automation Execution → Infrastructure → Credential Types → Add**, and create each type
below using **Input configuration** / **Injector configuration** in YAML mode (the field IDs
must match exactly — they're referenced by name in
[gsheet_update.py](../../collections/ansible_collections/business/support/plugins/modules/gsheet_update.py),
[gsheet_tracker.py](../../collections/ansible_collections/business/support/plugins/modules/gsheet_tracker.py),
and
[support_case_tracking_email.html.j2](../../templates/support_case_tracking_email.html.j2) via
the environment variables and extra vars they inject).

#### Type 1: "Ansible Support Analyzer"

Shared by both playbooks — each job template attaches its **own separate Credential instance**
of this type (see step 6).

| Field ID | Label | Type | Secret | Required | Notes |
|---|---|---|---|---|---|
| `redhat_offline_token` | Red Hat offline token | string | Yes | Yes | |
| `llm_api_key` | LLM API key | string | Yes | Yes | `EMPTY` for unauthenticated local servers |
| `llm_api_base_url` | LLM API base URL | string | | Yes | e.g. `https://api.openai.com/v1` |
| `llm_model` | LLM model name | string | | Yes | |
| `google_service_account_json` | Google service account JSON | string (multiline) | Yes | Yes | Full key file contents from step 2 |
| `google_sheet_id` | Google spreadsheet ID | string | | Yes | From step 2 |
| `gsheet_sheet` | Default worksheet name | string | | | Default: `Support Case Tracker`; override to `Accounts` on the analyzer job template's instance |
| `gsheet_lookup_column` | Default lookup column | string | | | Used by `pb_analyze_support_cases.yml` only |
| `gsheet_update_column` | Default update column | string | | | Used by `pb_analyze_support_cases.yml` only |

Not currently a Credential field (set via each playbook's `vars:` section or `-e` instead):

| Variable | Purpose |
|---|---|
| `gsheet_table_name` | Name of a Sheets API Table maintained over the tracker tab's data range (`pb_track_support_cases.yml` only). Defaults to `gsheet_sheet`; set to `""` to skip. Best-effort — a failure only emits a warning, since the row data itself already wrote successfully. |
| `tracker_status_filter` | GraphQL `status_filter` applied to the tracker's fetch. Default `{ne: "Closed"}` — excludes closed cases so they surface via the diff's `closed_cases` instead of lingering as "active". |

Injects `REDHAT_OFFLINE_TOKEN`, `LLM_API_KEY`, `LLM_API_BASE_URL`, `LLM_MODEL`,
`GOOGLE_SA_CRED_PATH` (the materialized key file path), `GOOGLE_SHEET_ID`, `GSHEET_SHEET`,
`GSHEET_LOOKUP_COLUMN`, and `GSHEET_UPDATE_COLUMN` as environment variables, and writes
`google_service_account_json` to a temp file via the `file` injector.

#### Type 2: "SMTP Server"

Only attached to the `pb_track_support_cases.yml` job template.

| Field ID | Label | Type | Secret | Required |
|---|---|---|---|---|
| `email_smtp_server` | Server | string | | Yes |
| `email_smtp_server_port` | Port | string | | Yes |
| `email_smtp_username` | Username | string | | Yes |
| `email_smtp_password` | Password | string | Yes | Yes |
| `email_smtp_from_address` | From Address | string | | Yes |

Injects its values as `extra_vars` (not environment variables) — `email_smtp_server`,
`email_smtp_server_port`, `email_smtp_username`, `email_smtp_password`,
`email_smtp_from_address`, plus legacy aliases (`MAILHOST*`, `smtp_*`) kept for parity with
[ansible-cac](https://github.com/zjleblanc/ansible-cac/blob/main/config/common/credential_types.yml).

For either option, copy the exact `inputs`/`injectors` YAML straight out of
[aap_config/controller/credential_types.yml](../../aap_config/controller/credential_types.yml)
into the UI's YAML editors if you'd rather not type the tables above by hand — it's valid
Controller credential-type syntax (note the `!unsafe` tags on injector values, which are
expected and required).

## 6. Credentials in aap_config

[aap_config/controller/credentials.yml](../../aap_config/controller/credentials.yml) defines
Credential instances. Add **three** new ones alongside the existing "Google OAuth Client" and
"OpenAI Config" credentials:

| Credential name | Type | Attached to | Key field differences |
|---|---|---|---|
| `Support Analyzer - Accounts` | Ansible Support Analyzer | `pb_analyze_support_cases.yml` job template | `gsheet_sheet` = `Accounts`; set `gsheet_lookup_column` / `gsheet_update_column` (e.g. `K` / `O`) |
| `Support Analyzer - Tracker` | Ansible Support Analyzer | `pb_track_support_cases.yml` job template | `gsheet_sheet` left at its default, `Support Case Tracker`; lookup/update columns can stay blank (unused by the tracker) |
| `SMTP Notifier` | SMTP Server | `pb_track_support_cases.yml` job template only | From step 3 |

The Red Hat token, LLM fields, service account JSON, and spreadsheet ID can be identical across
the two "Ansible Support Analyzer" Credentials — only `gsheet_sheet` (and optionally the lookup
columns) need to differ, since the two playbooks write to different worksheet tabs in the same
spreadsheet. As with the existing credentials in this file, reference vault-encrypted values
(`vault.yml`) via Jinja rather than hardcoding secrets.

## 7. Execution Environment and Project

### Execution environment

Everything in this project runs with `hosts: localhost` / `ansible_connection: local`, which
means the custom modules in `collections/ansible_collections/business/support/plugins/modules/`
execute **inside the Execution Environment's Python**, not on a managed node. This repo already
builds a custom EE (see [execution-environment/](../../execution-environment/)) — add the new
dependencies there rather than creating a second EE:

- Python packages: already added to
  [execution-environment/requirements/requirements.txt](../../execution-environment/requirements/requirements.txt)
  (`openai`, `requests`, `python-dateutil`; `google-api-python-client` / `google-auth*` were
  already present for `business.google`)
- Collections: already added to
  [collections/requirements.yml](../../collections/requirements.yml) (`business.support`,
  `community.general`)

Rebuild the EE image after these changes:

```bash
ansible-builder build -f execution-environment/execution-environment.yml -t business-process-ee:latest
```

Push the resulting image to a registry AAP can pull from, then reference it from both new job
templates in step 8 (or confirm it's already the Project's default EE).

> **`pdf` tag caveat**: `tasks/account_analyze.yml` runs `pandoc --standalone -c
> ~/.pandoc/github-md.css ...` when the `pdf` tag is requested. That CSS file is **not** part of
> this repository, so a job template that adds `--tags pdf` will fail inside the EE unless you
> either bake `~/.pandoc/github-md.css` into the custom EE image yourself or drop the `-c`
> option. The default job template configuration in step 8 doesn't use the `pdf` tag, so this
> only matters if you opt into markdown/PDF generation on AAP.

### Project and inventory

Both new job templates reuse the existing "Business Process" Project (see
[aap_config/controller/projects.yml](../../aap_config/controller/projects.yml)) and an inventory
with a `localhost` host / `ansible_connection: local` (see
[inventories/](../../inventories/)) — no new Project is needed.

## 8. Job Templates in aap_config

Add two new entries to
[aap_config/controller/templates.yml](../../aap_config/controller/templates.yml), alongside the
existing "BPA // Account Task Updater" template — don't share a single job template between the
two support-analyzer playbooks, since they need different Credential instances and extra vars.

### Job Template: "BPA // Support Case Analyzer"

| Field | Value |
|---|---|
| Job Type | Run |
| Inventory | existing |
| Project | Business Process |
| Playbook | `playbooks/pb_analyze_support_cases.yml` |
| Execution Environment | the rebuilt EE from step 7 |
| Credentials | `Support Analyzer - Accounts` |
| Variables | see below |

```yaml
support_case_accounts:
  - name: Parasol
    ids: ['12345678']
  - name: Acme Corp
    ids: ['789012', '345678']
```

The default run (no tags passed) fetches cases, runs the LLM analysis, and writes JSON into the
`Accounts` worksheet tab — nothing else to configure. Add a **Schedule** (e.g. weekly) under the
job template's **Schedules** tab for recurring runs. Consider enabling **Prompt on Launch** for
`extra_vars` if different operators need to run it against different account lists ad hoc.

### Job Template: "BPA // Support Case Tracker"

| Field | Value |
|---|---|
| Job Type | Run |
| Inventory | existing |
| Project | Business Process |
| Playbook | `playbooks/pb_track_support_cases.yml` |
| Execution Environment | the rebuilt EE from step 7 |
| Credentials | `Support Analyzer - Tracker` **and** `SMTP Notifier` |
| Variables | see below |

```yaml
support_case_accounts:
  - name: Parasol
    ids: ['12345678']
  - name: Acme Corp
    ids: ['789012', '345678']

# Not sourced from any credential type — set directly here:
tracker_notifications:
  - to:
      - team@example.com
      - oncall@example.com
    accounts: all
  - to:
      - terr5@example.com
    accounts:
      - Parasol
tracker_smtp_secure: starttls          # try | always | never | starttls
# tracker_notify_on_no_changes: true   # optional: always send, even without changes
# Legacy alternative (omit tracker_notifications): one email to tracker_email_to for all accounts
# tracker_email_to:
#   - team@example.com
```

Add a **Schedule** for a cadence (e.g. every 4 hours) — this is the playbook's primary run mode.
Use one schedule with the full `support_case_accounts` pull list and multiple
`tracker_notifications` pairings when different recipient groups need different account scopes;
avoid overlapping schedules that rewrite the same tracker tab. Each pairing is emailed only when
its scoped accounts have a new, closed, or updated case, unless
`tracker_notify_on_no_changes: true`.

Deploy both templates (and their credential instances from step 6) with:

```bash
ansible-navigator run playbooks/pb_deploy_aap_config.yml -e @vault.yml
```

## 9. Prepare the Google Sheet tabs

Both job templates write to the **same spreadsheet** (`google_sheet_id`) but different tabs:

- **`Accounts`** tab (used by `pb_analyze_support_cases.yml`): a hand-maintained tab where each
  row has a lookup value in the lookup column (e.g. column `K`, matching each account's `name`
  or `gsheet_lookup_value`) — the playbook writes the JSON report into the update column (e.g.
  column `O`) on the matching row. Create the header/lookup rows yourself before the first run.
- **`Support Case Tracker`** tab (used by `pb_track_support_cases.yml`): fully self-managed by
  the `business.support.gsheet_tracker` module — it creates the header row and all data rows
  itself on first run. You don't need to pre-create anything in this tab, just make sure the
  spreadsheet itself is shared with the service account (step 2).

## 10. Verify everything end-to-end

1. Launch **BPA // Support Case Analyzer** manually from the AAP UI. Confirm the job succeeds
   and the `Accounts` tab's update column is populated for each configured account.
2. Launch **BPA // Support Case Tracker** manually. Confirm the `Support Case Tracker` tab is
   populated, and — since every case is "new" on the very first run — that a
   change-notification email arrives for each `tracker_notifications` pairing (or the legacy
   `tracker_email_to` addresses).
3. Run **BPA // Support Case Tracker** a second time with no case changes upstream; confirm no
   email is sent (unless `tracker_notify_on_no_changes: true`).
4. Confirm the schedules on both job templates are enabled for ongoing, unattended runs.

## 11. Troubleshooting

| Symptom | Likely cause |
|---|---|
| Credential Type creation fails / `!unsafe` tag rejected | You're validating with a YAML linter that doesn't allow custom tags — the Controller UI itself accepts `!unsafe` fine (see [AGENTS.md](../../AGENTS.md)) |
| Job fails with `ModuleNotFoundError: google...` or `openai` | The Execution Environment doesn't have the Python deps — rebuild the custom EE (step 7) rather than relying on project-level `requirements.txt` auto-install |
| `community.general.mail` module not found | `community.general` isn't installed in the EE — confirm it's in [collections/requirements.yml](../../collections/requirements.yml) and rebuild the EE |
| `403` / permission errors from Google Sheets | The spreadsheet isn't shared with the service account email (Editor) — see step 2 |
| `lookup_value not found in column K` | A row's lookup column value doesn't match the account `name` / `gsheet_lookup_value` in the `Accounts` tab — see step 9 |
| Tracker email never arrives | Check both Credentials are attached to the `pb_track_support_cases.yml` job template, and that `tracker_notifications` (or legacy `tracker_email_to`) is set in Variables — the playbook's precondition `assert` task fails fast with a descriptive message if anything required is missing |
| SMTP auth error (`535`, `Username and Password not accepted`) | Using the Google account password instead of an App Password — see step 3, Option A |
| `pandoc: ~/.pandoc/github-md.css: No such file or directory` | Only occurs if a job template adds the `pdf` tag — see the caveat at the end of step 7 |

For non-AAP-specific issues (LLM connectivity, Red Hat API errors, general playbook usage), see
[../support-analyzer/QUICKSTART.md](../support-analyzer/QUICKSTART.md),
[../support-analyzer/EXAMPLES.md](../support-analyzer/EXAMPLES.md),
[../support-tracker/EXAMPLES.md](../support-tracker/EXAMPLES.md),
[../support-analyzer/LLM_CONFIGURATION.md](../support-analyzer/LLM_CONFIGURATION.md), and
[GSUITE_QUICKSTART.md](GSUITE_QUICKSTART.md).
