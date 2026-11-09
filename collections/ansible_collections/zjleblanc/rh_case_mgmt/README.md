# zjleblanc.rh_case_mgmt

Ansible collection for fetching, summarizing, and tracking Red Hat support cases. Backs the
support-analyzer and support-tracker workflows (see
[playbooks/pb_analyze_support_cases.yml](../../../../../playbooks/pb_analyze_support_cases.yml) and
[playbooks/pb_track_support_cases.yml](../../../../../playbooks/pb_track_support_cases.yml)).

## Modules

- `graphql_cases` -- Fetch Red Hat support cases via the GraphQL API (`https://graphql.redhat.com`)
  with server-side filtering (account numbers, last-modified date, status, product) and automatic
  cursor-based pagination. Normalizes GraphQL field names back to legacy REST v3 field names
  (`caseNumber`, `summary`, `product`, etc.).
- `llm_summarize` -- Summarize support case data using any OpenAI-compatible LLM API (vLLM, Ollama,
  LocalAI, OpenAI, Azure OpenAI, etc.). Builds an analyst-style prompt from case data and returns a
  formatted summary.
- `gsheet_update` -- Update a single Google Spreadsheet cell by row lookup (service account auth
  only). Includes smart JSON truncation so report payloads that exceed the Google Sheets
  50,000-character single-cell limit are shortened without breaking the JSON schema (non-priority
  product text is shortened first; see `truncate_priority_products`).
- `gsheet_tracker` -- Owns a dedicated worksheet tab as a case tracker. Split into three composable
  states (`read`, `diff`, `write`) so a multi-account run makes exactly one read and one write
  against the Sheets API regardless of account count. `read` returns per-account previous state
  plus other accounts' raw rows (preserving `HYPERLINK` formulas); `diff` is a pure local
  computation that returns new/closed/updated cases; `write` performs the single clear+rewrite and
  optionally maintains a Sheets API "Table" object over the tab.

### Note on the separate `zjleblanc.gsuite.gsheet_update`

This collection's `gsheet_update` is intentionally distinct from
[`zjleblanc.gsuite.gsheet_update`](../gsuite/README.md). They diverged from different lineages:

| | `zjleblanc.rh_case_mgmt.gsheet_update` | `zjleblanc.gsuite.gsheet_update` |
|---|---|---|
| Auth | Service account only | Service account or OAuth2 installed-app |
| Writes | Single cell per call | Single cell, or batch `updates` (multiple columns/cells per call) |
| Truncation | Smart JSON truncation for the 50k cell limit | None |
| Used by | Support analyzer workflow | Salesforce account-tasks workflow |

## Requirements

- `openai` (for `llm_summarize`)
- `requests` (used indirectly via `ansible.module_utils.urls`)
- `python-dateutil`
- `google-api-python-client`
- `google-auth`

Install with:

```bash
pip install openai requests python-dateutil google-api-python-client google-auth
```

## Authentication

### `graphql_cases` / `llm_summarize`

No Google auth involved:

- `graphql_cases` takes an `access_token` (SSO bearer token exchanged from a Red Hat offline token
  -- see the token-exchange task in `pb_analyze_support_cases.yml` / `pb_track_support_cases.yml`).
- `llm_summarize` takes `api_key` / `api_base_url` for any OpenAI-compatible endpoint.

### `gsheet_update` / `gsheet_tracker` -- Google service account only

Provide exactly one of:

- `credentials_path` module argument (path to a service account JSON key file)
- `credentials` module argument (service account JSON key as a dict, e.g. from Ansible Vault)
- `GOOGLE_SA_CRED_PATH` environment variable (path to a service account JSON key file)

The target spreadsheet is identified via the `gsheet_id` module argument or the `GOOGLE_SHEET_ID`
environment variable. See [docs/common/GSUITE_QUICKSTART.md](../../../../../docs/common/GSUITE_QUICKSTART.md)
for setting up a Google Cloud service account.
