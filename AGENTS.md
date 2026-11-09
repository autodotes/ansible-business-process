# AGENTS.md — Ansible Development Guide for AI Coding Agents

## Purpose

This document defines **strong conventions** for developing Ansible content.  
It is written primarily for **AI coding agents** to ensure consistency, maintainability, and alignment with best practices.

- Humans should rely on `README.md` for onboarding and usage.
- Agents should treat this document as **authoritative guidance**.
- Deviations are allowed, but **must be explicitly justified and confirmed with the user**.

---

## Source of Truth

Agents SHOULD reference the following template repository for structure and patterns:

- <https://github.com/Megalith-Development/Ansible-Template-Repo>

If a template is not present:

- The agent MUST infer structure from the current repository.
- The agent SHOULD suggest aligning to the template where appropriate.

---

## Core Standards

### Red Hat CoP Good Practices

All development MUST align with:

- <https://redhat-cop.github.io/automation-good-practices/>

This is the **baseline standard**. This guide builds on top of it.

---

## Collection Design Standards

### Structure

- Local collections MUST live under:
  - `collections/ansible_collections/<namespace>/<name>/`

- Collections MUST include:
  - `galaxy.yml`
  - `meta/runtime.yml`

- Collections SHOULD include a `README.md` documenting:
  - Included modules and plugins.
  - Required dependencies.
  - Authentication/configuration expectations.

Example structure:

```text
collections/ansible_collections/zjleblanc/example/
  galaxy.yml
  meta/
    runtime.yml
  plugins/
    modules/
      example_action.yml
    module_utils/
      auth.py
```

---

### Module Utils

- Collections SHOULD extract shared logic into:
  - `plugins/module_utils/`

- Candidates for extraction include:
  - Authentication and credential resolution.
  - Common API request/response handling.
  - Reusable data formatting or validation helpers.

This pattern:

- Prevents duplicated logic across modules in the same collection.
- Keeps individual modules focused on their specific action.
- Improves testability and maintainability.

Agents SHOULD suggest additional `module_utils` extractions when adding new modules to a collection reveals further duplicated logic, and confirm with the user before proceeding.

---

### Python Dependencies & the Execution Environment

Modules, `module_utils`, and filter/lookup plugins frequently depend on third-party Python packages (e.g. `google-api-python-client`, `beautifulsoup4`).

- Agents MUST add any new third-party Python package required by a module, `module_utils`, or plugin to:
  - `execution-environment/requirements/requirements.txt`
- Agents SHOULD group entries with a comment noting which collection/plugin requires them, e.g.:

  ```text
  # Required by collections/ansible_collections/zjleblanc/gsuite (gmail_search, gsheet_update)
  google-api-python-client
  google-auth

  # Required by collections/ansible_collections/zjleblanc/custom (parse_sf_tasks filter)
  beautifulsoup4
  ```

- Agents SHOULD keep the collection's own `README.md` "Requirements" section in sync with `requirements.txt`.
- This keeps the built Execution Environment (see `execution-environment/execution-environment.yml`) able to run all collection content without manual `pip install` steps in AAP.
- Dependencies used only by standalone developer tooling (e.g. a one-time OAuth setup script run locally, never executed by an AAP job) SHOULD NOT be added to `requirements.txt` -- document those separately instead (e.g. in the collection README or script docstring).

---

## Role Design Standards

### Variable Management

- Roles MUST initialize variables in:
  - `defaults/main.yml`

- Roles MUST validate externally provided variables:
  - inventory variables
  - extra vars
  - surveys
  - upstream role outputs

- Variables MUST be:
  - data only
  - predictable
  - documented where user-facing

---

### Validation Pattern

Each role MUST include:

```text
tasks/validate.yml
```

This file MUST:

- Validate required external variables.
- Validate formats and constraints.
- Validate relationships between variables.
- Fail fast with clear error messages.

Preferred implementation:

- Use `ansible.builtin.assert`.
- Provide meaningful success and failure output.

---

### Argument Specs

Roles MUST include `meta/argument_specs.yml` for schema validation.

This file MUST:

- Define all role entry points (main, and any task files callable via `tasks_from`)
- Declare all required and optional variables with types
- Include descriptions for user-facing variables
- Use appropriate validators (choices, min/max, regex, etc.)

Argument specs provide:

- Early validation before task execution
- IDE autocomplete and documentation
- Clear contract for role consumers
- Reduced need for defensive programming in tasks

`meta/argument_specs.yml` SHOULD NOT replace `tasks/validate.yml`.

Both serve different purposes:

- `argument_specs.yml`: Schema validation and documentation
- `tasks/validate.yml`: Complex business logic validation, relationship checks, and custom assertions

---

### Roles as Classes

Roles SHOULD be designed like **classes with public functions**.

This means:

- **Public functions**: Task files under `tasks/` that can be called via `tasks_from` represent the role's public API.
- **Encapsulation**: Internal implementation details remain within the role; external callers only need to know which task file to call and what variables to provide.
- **Reusability**: Like class methods, task files should be independently callable and composable.
- **Single Responsibility**: Each task file should have a clear, well-defined purpose (e.g., `create.yml`, `update.yml`, `delete.yml`).

Example structure:

```text
roles/example/
  tasks/
    main.yml       # Default entry point (like a constructor)
    validate.yml   # Internal validation (private method)
    create.yml     # Public function
    update.yml     # Public function
    delete.yml     # Public function
```

Playbooks then call these "public functions":

```yaml
- name: Create resource
  ansible.builtin.import_role:
    name: example
    tasks_from: create
```

This pattern:

- Makes roles more flexible and composable.
- Enables AAP Job Templates to call specific role functions.
- Improves testability and maintainability.

---

## Playbook Design Standards

### Naming

- Playbook filenames MUST be prefixed with `pb_`.
- Examples:
  - `pb_create_role_name.yml`
  - `pb_update_account_tasks.yml`
  - `pb_gmail_tasks_report.yml`

### Header comments

- Playbooks MAY include a comment block immediately before the document `---`.
- That comment MUST be limited to **run usage examples**.
- Run examples MUST use `ansible-navigator` (not `ansible-playbook`).
- Do NOT put narrative docs, credential explanations, or other prose in the playbook header.

Example:

```yaml
# ansible-navigator run playbooks/pb_example.yml
# ansible-navigator run playbooks/pb_example.yml -e 'example_var="value with spaces"'
---
- name: Example play
  hosts: localhost
  gather_facts: false
```

### Task comments

- Playbooks and task files MUST NOT include inline task comments (`#` on or above individual tasks).
- If an agent believes a comment is seriously necessary, it MUST ask for developer approval before adding it.

### Playbook task files (`tasks/`)

- Prefer keeping tasks inline in the playbook.
- Extract a task file only when necessary (for example, a multi-task body reused via `include_tasks` / `import_tasks` inside a loop).
- When a task file is required, place it under repo-root `tasks/` (not `playbooks/tasks/`) so YAML schema / ansible-lint treat it as a task list rather than a playbook.
- Name it `<subject>_<action>.yml` where:
  - `<subject>` matches the loop subject (typically the `loop_var` / loop label subject).
  - `<action>` MUST be a **single verb** when possible (e.g. `update`, `summarize`, `create`, `delete`).
- When creating a new task file, the agent MUST propose several one-word `<action>` options and ask the developer to select one before creating or renaming the file.
- If a single verb cannot clearly describe the work, the agent MUST ask the developer and present options (prefer still offering one-word candidates first; multi-word only if the developer chooses that).
  - Example: looping with `loop_var: account` → `tasks/account_update.yml` (after developer selects `update`).
- Include it from playbooks with a path relative to the playbook file, e.g. `../tasks/account_update.yml`.
- Task file header comments (before `---`) MUST be limited to **references** and MUST list all references.
- Each reference MUST be only the file path and line number (no extra context).

Example:

```yaml
# References:
#   - playbooks/pb_update_account_tasks.yml:107
---
- name: Example per-item task
  ansible.builtin.debug:
    msg: "{{ account }}"
```

---

## Task Design

### Structure

Roles SHOULD follow a modular task structure:

```text
tasks/
  main.yml
  validate.yml
  install.yml
  configure.yml
  service.yml
```

- `main.yml` SHOULD orchestrate imports.
- Tasks SHOULD be logically separated.
- Functional task files SHOULD be named by action or responsibility.

---

### Role Calling Pattern

Roles SHOULD have playbooks that call role functionality so that AAP Job Templates can target those playbooks directly.

Playbooks SHOULD use `ansible.builtin.import_role` or `ansible.builtin.include_role` instead of duplicating role logic.

Example:

```yaml
# ansible-navigator run playbooks/pb_create_role_name.yml
---
- name: Create ServiceNow incident
  hosts: localhost
  gather_facts: false

  tasks:
    - name: Create ServiceNow incident
      ansible.builtin.import_role:
        name: role_name
        tasks_from: create
```

Guidelines:

- Use `tasks_from` when the role has functional or modular task files.
- Prefer action-specific playbooks for AAP Job Templates.
- Keep playbooks thin; business logic should remain inside roles.
- Do not duplicate role tasks in playbooks.
- Playbook filenames MUST use the `pb_` prefix (see Playbook Design Standards), for example:
  - `pb_create_role_name.yml`
  - `pb_update_role_name.yml`
  - `pb_service_role_name.yml`

Agents SHOULD suggest this pattern when creating roles intended to be executed by AAP.

---

### Idempotency

All tasks MUST aim to be idempotent.

---

### Command-Based Tasks

Modules such as:

- `shell`
- `command`
- `raw`

Are:

- DISCOURAGED.
- MUST be justified.
- MUST include validation and idempotency safeguards.

Required protections include at least one applicable safeguard:

- `changed_when`
- `failed_when`
- `creates`
- `removes`
- pre-checks
- post-checks

Agents MUST explain why a module-based approach was not used.

---

## Data Transformation Rules

### Jinja Usage

Jinja is allowed under the following constraints:

- Maximum **4 chained filters**.
- `json_query` is allowed.
- Nested logic is allowed only if it remains human-readable.

---

### Python Filter Plugins

The agent MUST create a custom filter plugin when:

- Data restructuring is required.
- Jinja becomes difficult to read.
- Logic exceeds readability thresholds.

Location:

```text
filter_plugins/
```

Guidelines:

- Keep filters focused and reusable.
- Prefer clarity over cleverness.
- Keep transformation logic testable.

---

### Testing for Filters

Unit tests are RECOMMENDED.

They are not required, but SHOULD be suggested for complex filters.

---

## AAP Configuration as Code

The agent SHOULD suggest using configuration-as-code patterns when working with AAP resources, especially:

- Projects
- Job Templates
- Inventories
- Credentials
- Organizations
- Teams
- Roles
- Workflow Job Templates

Reference:

- `.cursor/skills/aap-config-as-code` skill/pattern

---

### API Usage

The agent SHOULD use supported collections when available.

If no collection exists:

- Raw API calls MAY be used.

If the agent is not confident that an appropriate collection exists:

- The agent MUST ask the user how to proceed.

---

## Decision Making Behavior

When multiple valid approaches exist, the agent MUST:

- Present options clearly.
- Explain trade-offs.
- Ask the user for direction.

The agent MUST NOT silently choose complex or impactful approaches.

---

## Repository Documentation

The agent SHOULD suggest README updates when:

- Adding roles.
- Adding playbooks.
- Introducing new patterns.
- Adding AAP-facing entry points.

The agent SHOULD NOT automatically rewrite documentation unless asked.

---

## CI / Validation Guidance

CI is project-specific.

The agent SHOULD suggest validation steps such as:

```bash
ansible-navigator run playbooks/pb_example.yml --mode stdout -- --syntax-check
```

```bash
ansible-navigator run playbooks/pb_example.yml --mode stdout -- --check
```

When appropriate, the agent SHOULD also suggest:

- `ansible-lint`
- `yamllint`

---

## Testing Expectations

Default expectation:

- Basic validation.
- Syntax checks.
- Check mode where supported.

Future direction, not enforced here:

- Functional testing.
- Molecule.
- AAP job-based integration testing.

---

## Enforcement Model

This document uses:

- **MUST**: required behavior
- **SHOULD**: strong recommendation
- **MAY**: optional behavior

---

## Deviation Rules

If an agent deviates from this guide, it MUST:

- Clearly explain the deviation.
- Justify the reasoning.
- Ask for user confirmation.

---

## Summary

Agents operating under this guide must:

- Follow Red Hat CoP best practices.
- Use structured, validated, and idempotent roles.
- Keep logic readable and maintainable.
- Move complex transformations into Python filters.
- Avoid command-based tasks unless justified.
- Prefix playbooks with `pb_`, keep playbook headers limited to `ansible-navigator` run examples, avoid task comments, and extract playbook task files only when necessary.
- Expose role functionality through thin playbooks when AAP Job Templates need executable entry points.
- Engage the user when decisions are ambiguous.

This ensures:

- Consistency
- Maintainability
- Production-quality automation