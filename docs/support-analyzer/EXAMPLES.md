# Usage Examples — Support Case Analyzer

Practical examples for `playbooks/pb_analyze_support_cases.yml`. All examples assume
`vault.yml` at the repo root supplies the required credentials (see
[QUICKSTART.md](QUICKSTART.md)) and that account lists are supplied via your own (gitignored)
extra-vars file, e.g. `my_accounts.yml`:

```yaml
support_case_accounts:
  - name: Parasol
    ids: ['123456']
  - name: Acme Corp
    ids: ['789012', '345678']
```

See [../support-tracker/EXAMPLES.md](../support-tracker/EXAMPLES.md) for the tracker workflow's
examples.

## Basic examples

### 1. Single account (legacy variables)

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml \
  -e "support_case_account_name=Parasol" \
  -e "support_case_account_ids=['123456']"
```

### 2. Multiple accounts (recommended)

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml
```

### 3. Per-account output path

Override the report path for one account in `my_accounts.yml`:

```yaml
support_case_accounts:
  - name: Parasol
    ids: ['123456']
    analysis_file_dest: reports/parasol_q4_2024
```

### 4. Google Sheets (JSON output)

Set Google credentials (see [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md)),
then run:

```yaml
# vault.yml
gsheet_id: "your-spreadsheet-id"
google_credentials_path: "/path/to/service-account.json"
```

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml
```

The `json` tag path (default) updates the spreadsheet; the lookup value defaults to each
account's `name` unless `gsheet_lookup_value` is set.

### 5. Markdown and PDF reports

Tasks tagged `pdf` are skipped by default. Request them explicitly:

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf
```

Reports are written under `reports/` (or `analysis_file_dest` per account).

## Using Ansible Vault

### With vault password prompt

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --ask-vault-pass
```

### With vault password file

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --vault-password-file ~/.ansible/vault_pass.txt
```

## Advanced examples

### 6. Verbose output for debugging

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- -vvv
```

### 7. Skip AI analysis

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --skip-tags ai
```

### 8. Only fetch data

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags fetch,filter
```

### 9. Sheets only (no PDF)

The default run updates Google Sheets and skips markdown/PDF (`never` tag). To avoid Sheets:

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --skip-tags json
```

### 10. Split accounts across runs

```yaml
# accounts-priority.yml
support_case_accounts:
  - name: Tier1 Customer
    ids: ['111111']
```

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @accounts-priority.yml
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @accounts-standard.yml
```

## Automation examples

### 11. Weekly automated report (crontab)

```bash
# Edit crontab
crontab -e

# Add this line (runs every Monday at 9 AM)
0 9 * * 1 cd /path/to/ansible-business-process && ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml --mode stdout >> /var/log/support-case-analyzer.log 2>&1
```

### 12. Monthly report on the first of the month

```bash
0 6 1 * * cd /path/to/ansible-business-process && ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @my_accounts.yml --mode stdout -- --tags pdf
```

### 13. Shell script wrapper

```bash
#!/bin/bash
# Run support case analysis with error handling
set -e

echo "Running support case analysis..."

ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml --mode stdout

if [ $? -eq 0 ]; then
    echo "Analysis complete!"
else
    echo "Analysis failed!"
    exit 1
fi
```

## Integration examples

### 14. Email report after generation

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf

mail -s "Red Hat Support Case Analysis" \
  -a reports/latest.md \
  team@company.com < /dev/null
```

### 15. Convert to PDF and share

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf

pandoc reports/analysis.md -o reports/analysis.pdf
aws s3 cp reports/analysis.pdf s3://company-reports/
```

### 16. Commit to a Git repository

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf

cd reports
git add $(date +%Y%m%d)_analysis.md
git commit -m "Support case analysis for $(date +%Y-%m-%d)"
git push
```

### 17. Post summary to Slack

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags pdf

SUMMARY=$(head -n 50 reports/latest.md)
curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"Support Case Analysis:\n\`\`\`$SUMMARY\`\`\`\"}" \
  YOUR_SLACK_WEBHOOK_URL
```

## Troubleshooting examples

### 18. Dry run with maximum verbosity

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --check -vvvv
```

### 19. Test API connectivity only

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --tags fetch --step
```

### 20. Skip failing tasks

```bash
ansible-navigator run playbooks/pb_analyze_support_cases.yml \
  -e @vault.yml -e @my_accounts.yml \
  -- --skip-tags ai -v
```

## Performance examples

### 21. Parallel account processing

The playbook processes accounts in sequence by default. For large numbers of accounts, consider
splitting into multiple runs:

```bash
# Terminal 1
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @accounts-batch1.yml &

# Terminal 2
ansible-navigator run playbooks/pb_analyze_support_cases.yml -e @vault.yml -e @accounts-batch2.yml &
```

## Tips

- **Account IDs**: provide as YAML lists under each account's `ids`
- **Output**: the default run updates Google Sheets (`json` tag); use `--tags pdf` for
  markdown/PDF under `reports/`
- **Rate limiting**: be mindful of Red Hat API limits when processing many accounts
- **LLM quotas**: monitor your LLM provider when analyzing large case volumes
- **Google Sheets**: see [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md) for
  service account setup
- **GraphQL API**: `pb_analyze_support_cases.yml` queries `https://graphql.redhat.com` via the
  `zjleblanc.rh_case_mgmt.graphql_cases` module, which filters and paginates server-side. Override the
  endpoint or Apollo headers via `redhat_graphql_url`, `redhat_graphql_client_name`, and
  `redhat_graphql_client_version` in the playbook's `vars:` section (or `-e`)
- **Product filtering**: use `product_filter` with the GraphQL `like` operator for starts-with
  matching (e.g. `{like: "Red Hat Ansible%"}`). See
  [collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/graphql_cases.py](../../collections/ansible_collections/zjleblanc/rh_case_mgmt/plugins/modules/graphql_cases.py)
  for all options

## Getting help

- Quick start: [QUICKSTART.md](QUICKSTART.md)
- Google Sheets: [../common/GSUITE_QUICKSTART.md](../common/GSUITE_QUICKSTART.md)
- Running on Ansible Automation Platform: [../common/USAGE.md](../common/USAGE.md)
- Tracker workflow examples: [../support-tracker/EXAMPLES.md](../support-tracker/EXAMPLES.md)
