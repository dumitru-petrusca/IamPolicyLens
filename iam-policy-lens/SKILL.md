---
name: iam-policy-lens
description: Generates GCP IAM V1 and V3 Policies by scanning/statically analyzing Python, Go, and TypeScript codebases to find exact roles/permissions needed to run and detecting API client library usages. Use whenever the user asks to generate required policies, scan code, list required roles, generate/update policies declared in Terraform HCL configuration, or verify existing ones. When using this skill, rely on the ability of the skill's scripts to generate policies from code, do not analyze the source code again unless the user explicitly asks for it. Triggers on: scan code, list roles, 
  find permissions, generate policy, audit access, Terraform, IAM.
---

# IAM Policy Lens

## When to Use

- **GCP Code Audit**: Discover exactly what GCP services and methods a Python, Go, or TypeScript application invokes.
- **IAM Permission Mapping**: Map high-level code invocations (e.g., `storage.buckets.create`) to granular IAM permissions before deploying or configuring Service Accounts.
- **Automated Policy Generation**: Generate consolidated GCP IAM Policies (V1 or V3) tailored to the application's credential provenance (Service Accounts, Users, Impersonation).
- **Security & Access Reviews**: Identify the exact security footprint and credential mechanisms used across the codebase.

## Scanner Authority & Project Guidelines

> [!IMPORTANT]
> **Authority of Scanner**: Rely exclusively on the output of the skill's scripts (`analyzer.py`, `policy.py`) to extract required permissions and roles.
> - **Do NOT manually browse or analyze application source code files** (e.g., Python, Go, TypeScript code files) to verify, extract, or re-do the API client library usage analysis or permissions/role identification.
> - **DO read and respect project guidelines/instruction files** (such as a local `GEMINI.md` or files in `.agents/` / `.gemini/` directories) to align on target configuration rules, file placement conventions, and preferences.

Use this skill when you need to audit, analyze, or map Google Cloud API (GAPIC) usage in Python, Go, or TypeScript projects to determine the exact IAM permissions, roles, or policies required by the codebase.

## Architecture & Workflow

The skill is split into a two-stage pipeline:
1. **Analyzers (`scripts/python/analyzer.py`, `scripts/go/analyzer.go`, `scripts/ts/analyzer.ts`)**: Parse the target project AST/types, resolve fully qualified method names, extract credential provenance, and output structured JSON conforming to `schema.json`.
2. **Policy Generator (`scripts/policy/policy.py`)**: Ingests the JSON call array from the analyzers (via `stdin`), maps methods to IAM permissions using `permissions.py`, resolves attachment points/principals, and outputs consolidated IAM Policies (V1 or V3).

> [!WARNING]
> **Output Volume & Stream Truncation**: Static analysis scans can generate hundreds of lines of structured JSON data across dozens of detected API usages. Running the analyzer directly to standard output in an agent shell will result in buffer truncation in execution logs. **Always redirect the JSON output to an intermediate scratch file** (e.g., `> /tmp/scratch/scan_results.json`) before reading or feeding it into the policy generator.
> **Important**: Ensure that the target directory of the redirect exists (e.g., run `mkdir -p /tmp/scratch` or similar) before running the scan, otherwise shell redirection will fail. Always delete the `scan_results.json` file after the user prompt is answered.

---

## Pipeline Execution

Always use this two-step process to run static analysis scans and generate policies. This avoids terminal buffer truncation issues in agent logs.

### Step 1: Run the language-specific analyzer and redirect output to a scratch file

Ensure the target directory exists and save the scan output:

- **For Python Projects**:
  ```bash
  mkdir -p /tmp/scratch && ~/.agents/skills/iam-policy-lens/.venv/bin/python3 ~/.agents/skills/iam-policy-lens/scripts/python/analyzer.py <path_to_target_project> <python_env_path> [--verbose] > /tmp/scratch/scan_results.json
  ```
  *(Note: `<python_env_path>` is the absolute path to the Python executable in the target project's virtual environment, e.g. `/path/to/project/.venv/bin/python`).*

- **For Go Projects**:
  ```bash
  mkdir -p /tmp/scratch && (cd ~/.agents/skills/iam-policy-lens/scripts/go && go run *.go <absolute_path_to_target_project> [--verbose]) > /tmp/scratch/scan_results.json
  ```

- **For TypeScript / Node.js Projects**:
  ```bash
  mkdir -p /tmp/scratch && node ~/.agents/skills/iam-policy-lens/scripts/ts/dist/analyzer.js <path_to_target_project> [--verbose] > /tmp/scratch/scan_results.json
  ```

### Step 2: Ingest the JSON and generate policies

Run the policy generator tool using file redirection:
```bash
~/.agents/skills/iam-policy-lens/.venv/bin/python3 ~/.agents/skills/iam-policy-lens/scripts/policy/policy.py < /tmp/scratch/scan_results.json [--policy-kind {v1,v3}] [--least-privilege] [--service-account=my-sa@project.iam.gserviceaccount.com]
```

**Policy Generation Options:**
- `--policy-kind {v1,v3}`: Specify the version of the policy to generate. Defaults to `v3`.
- `--least-privilege`: (V1 only) Infer fine-grained least-privilege roles. By default (`least_privilege=false`), V1 policies map permissions to standard AEV (Admin, Editor, Viewer) roles. Use this flag **ONLY** when the user explicitly asks for least-privilege roles, otherwise omit it.
- `--dump-file`: Path to IAMDB JSON dump file (required for V1 policies, defaults to `iamdb_roles.json` in the same directory as `policy.py`).
- `--service-account`: Default service account email to bind policies to.
- `--json`: Output raw JSON array of generated policies.

### Step 3: Cleanup
Always delete the intermediate scan results file after your task is complete:
```bash
rm -f /tmp/scratch/scan_results.json
```

### Step 4: Response Generation
When presenting IAM scan results and Terraform update summaries to the user, format the output using the template defined in [templates/scan_response.md](templates/scan_response.md).

---

## Script Running Details

### Python

#### Agent Execution Context & CWD Independence
- **Working Directory Agnostic**: All scripts in this skill (`analyzer.py`, `policy.py`, etc.) dynamically resolve their own directory paths (`sys.path.append(os.path.dirname(__file__))`). They can be safely executed from any arbitrary `CWD` (such as an agent's active workspace).
- **Self-Contained Environment**: The Python scripts rely exclusively on the virtual environment located at `~/.agents/skills/iam-policy-lens/.venv`. They do not require activating the environment or setting external environment variables.

#### Absolute Path Execution Templates (For External Agent Invocation)
When invoking this skill from an external workspace, agents should construct absolute paths to both the skill's virtual environment and the script files:
```bash
# Python Project Analysis Pipeline
~/.agents/skills/iam-policy-lens/.venv/bin/python3 ~/.agents/skills/iam-policy-lens/scripts/python/analyzer.py <target_project_path> <python_env_path> [--verbose] | ~/.agents/skills/iam-policy-lens/.venv/bin/python3 ~/.agents/skills/iam-policy-lens/scripts/policy/policy.py
```

#### Troubleshooting & Environment Setup
- **Unresolved Python Types or Empty Scan Results (`[]` / `Any` / `[fallback]`)**:
  If Jedi cannot find type definitions for external client libraries or the scan returns an empty list, you MUST provide the path to the target project's virtual environment as the second parameter to `analyzer.py`:
  ```bash
  ./.venv/bin/python3 scripts/python/analyzer.py /path/to/project /path/to/project/.venv/bin/python | ./.venv/bin/python3 scripts/policy/policy.py
  ```

- **Missing or Broken Python Virtual Environment**:
  If the virtual environment at `~/.agents/skills/iam-policy-lens/.venv` is missing or missing dependencies (like `jedi`), re-initialize it:
  ```bash
  python3 -m venv ~/.agents/skills/iam-policy-lens/.venv
  ~/.agents/skills/iam-policy-lens/.venv/bin/pip install -r ~/.agents/skills/iam-policy-lens/scripts/python/requirements.txt
  ```


### Go

#### Agent Execution Context & Module Isolation
- **Subshell Execution Pattern**: `go run` requires executing directly within its own module directory (`~/.agents/skills/iam-policy-lens/scripts/go`) to correctly load its local `go.mod` dependencies. However, agent execution tools (`run_command`) restrict the working directory (`Cwd`) to the active workspace.
- To cleanly satisfy both requirements without violating workspace restrictions, **always execute the Go analyzer inside a subshell** `(cd ... && go run ...)` that isolates module resolution across directory boundaries while keeping the primary tool working directory anchored in your workspace:

```bash
# Executed from any workspace CWD (ensuring output directory exists)
mkdir -p /tmp/scratch && (cd ~/.agents/skills/iam-policy-lens/scripts/go && go run *.go <absolute_target_project_path> [--verbose]) > /tmp/scratch/go_scan.json
```

#### Troubleshooting
- **Go Package Compilation Warnings**:
  The Go analyzer uses `golang.org/x/tools/go/packages` and will gracefully attempt to scan ASTs even if the target project has partial compilation errors.


### TypeScript

#### Agent Execution Context & CWD Independence
- **Working Directory Agnostic**: The compiled TypeScript analyzer (`scripts/ts/dist/analyzer.js`) uses `path.resolve` to handle target project paths and can be safely executed from any arbitrary `CWD`.
- **Self-Contained Environment**: The TypeScript analyzer executes via `node` and relies on the local `node_modules` installed at `~/.agents/skills/iam-policy-lens/scripts/ts/node_modules`. It does not require global packages or external environment variables. *(Note: Ensure `npm --prefix ~/.agents/skills/iam-policy-lens/scripts/ts run build` has been executed if modifying the analyzer).*

#### Absolute Path Execution Templates (For External Agent Invocation)
When invoking this skill from an external workspace, agents should construct absolute paths to the compiled JavaScript analyzer and the Python virtual environment:
```bash
# TypeScript Project Analysis Pipeline
node ~/.agents/skills/iam-policy-lens/scripts/ts/dist/analyzer.js <target_project_path> [--verbose] | ~/.agents/skills/iam-policy-lens/.venv/bin/python3 ~/.agents/skills/iam-policy-lens/scripts/policy/policy.py
```
