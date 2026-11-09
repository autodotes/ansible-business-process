# Support Case Analyzer — Quick Start

Get up and running with the support case analyzer workflow in 5 minutes.

## Step 1: Install dependencies

Python dependencies are tracked in
[execution-environment/requirements/requirements.txt](../../execution-environment/requirements/requirements.txt):

```bash
pip install -r execution-environment/requirements/requirements.txt
```

## Step 2: Set up credentials

Add the required values to [vault.yml](../../vault.yml) (encrypt with `ansible-vault edit vault.yml`):

```yaml
---
redhat_offline_token: "your-redhat-offline-token"

# For local vLLM (no auth needed)
llm_api_key: "EMPTY"
llm_api_base_url: "http://localhost:8000/v1"
llm_model: "meta-llama/Llama-2-70b-chat-hf"

# For OpenAI
# llm_api_key: "sk-..."
# llm_api_base_url: "https://api.openai.com/v1"
# llm_model: "gpt-4"

# Google Sheets (service account)
gsheet_id: "your-spreadsheet-id"
google_credentials_path: "/path/to/service-account.json"
```

To get your Red Hat offline token:

1. Visit <https://access.redhat.com/management/api>
2. Log in with your Red Hat account
3. Click "Generate Token"
4. Copy the offline token into `vault.yml` as shown above
5. The playbook automatically exchanges this for an access token via Red Hat SSO

## Step 3: Configure accounts

Provide `support_case_accounts` as extra vars, either inline or from your own (gitignored) vars
file:

```yaml
# e.g. my_accounts.yml (keep this out of git)
support_case_accounts:
  - name: My Customer
    ids: ['YOUR_ACCOUNT_ID']
```

## Step 4: Run your first analysis

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml
```

By default this runs the **Google Sheets / JSON** path (see
[../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md)). Set `gsheet_id` and
`google_credentials_path` (or `GOOGLE_SA_CRED_PATH`) before running if you use Sheets.

For a local markdown report instead:

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf
```

## Step 5: View output

**Google Sheets:** open your spreadsheet and check the update column for the account row.

**Markdown (with `--tags pdf`):**

```bash
cat reports/*_support_case_summary_*.md
```

## Common use cases

### Multiple accounts

```yaml
support_case_accounts:
  - name: Parasol
    ids: ['123456']
  - name: Acme Corp
    ids: ['789012', '345678']
```

### Google Sheets dashboard

See [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md) for service account setup.

### PDF / markdown reports

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf
```

## Troubleshooting

### "Required extra vars missing"

Make sure `vault.yml` (or your extra vars) supplies `redhat_offline_token`, `llm_api_key`,
`llm_api_base_url`, and `llm_model`.

### "Failed to generate summary"

**For local LLM:** Check the server is running: `curl http://localhost:8000/v1/models`

**For OpenAI:** Check your API key is valid and you have quota available.

### "No cases found"

- Verify your account ID is correct
- Try a date further in the past (override `activity_date`)
- Check your Red Hat API credentials have access to the account

## Next steps

- Customize the report template at
  [templates/support_case_analysis.md.j2](../../templates/support_case_analysis.md.j2)
- Adjust AI prompts in
  [collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/llm_summarize.py](../../collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/llm_summarize.py)
- Set up automated reports with an AAP schedule (see [../common/USAGE.md](../common/USAGE.md))

## Getting API keys

### Red Hat Customer Portal offline token

1. Visit <https://access.redhat.com/management/api>
2. Log in with your Red Hat account
3. Click "Generate Token" to get an offline token
4. Copy the offline token (it will only be shown once!)
5. Store it securely in `vault.yml`

**How it works**: the offline token is a long-lived token that the playbook exchanges for a
temporary access token via Red Hat SSO before making API calls. This provides better security
since access tokens are short-lived.

Note: if you don't see the API management page, you may need API access. Contact your Red Hat
account team.

### LLM setup (choose one)

**Option 1: Local vLLM (best for privacy)**

1. Install vLLM: `pip install vllm`
2. Start the server:

   ```bash
   python -m vllm.entrypoints.openai.api_server \
     --model meta-llama/Llama-2-70b-chat-hf \
     --port 8000
   ```

3. Use `llm_api_key: "EMPTY"` and `llm_api_base_url: "http://localhost:8000/v1"`

**Option 2: Ollama (easiest local setup)**

1. Install from <https://ollama.ai/download>
2. Start: `ollama serve`
3. Pull model: `ollama pull llama2`
4. Use `llm_api_key: "EMPTY"` and `llm_api_base_url: "http://localhost:11434/v1"`

**Option 3: OpenAI (cloud-based)**

1. Visit <https://platform.openai.com/api-keys>
2. Create an API key
3. Use your API key and `llm_api_base_url: "https://api.openai.com/v1"`

**See [LLM_CONFIGURATION.md](LLM_CONFIGURATION.md) for detailed setup**

### Google Sheets (optional)

See [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md) for service account and
spreadsheet sharing steps.
