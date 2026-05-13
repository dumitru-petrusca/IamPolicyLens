---
name: iam-policy-lens
description: Polyglot Cloud Access Scanner (Python & Go) to statically identify Google Cloud (GAPIC) client library invocations, map them to required IAM permissions, and generate consolidated GCP IAM V3 Allow Policies.
---

# IAM Policy Lens Instructions

Use this skill when you need to audit, analyze, or map Google Cloud API (GAPIC) usage in Python or Go projects to determine the exact IAM permissions, roles, or policies required by the codebase.

---

## When to Use

- **GCP Code Audit**: Discover exactly what GCP services and methods a Python or Go application invokes.
- **IAM Permission Mapping**: Map high-level code invocations (e.g., `storage.buckets.create`) to granular IAM permissions before deploying or configuring Service Accounts.
- **Automated Policy Generation**: Generate least-privilege, consolidated GCP IAM V3 Allow Policies tailored to the application's credential provenance (Service Accounts, Users, Impersonation).
- **Security & Access Reviews**: Identify the exact security footprint and credential mechanisms used across the codebase.

---

## Architecture & Workflow

The skill is split into a two-stage pipeline:
1. **Analyzers (`scripts/python/analyzer.py`, `scripts/go/analyzer.go`)**: Parse the target project AST/types, resolve fully qualified method names, extract credential provenance, and output structured JSON conforming to `schema.json`.
2. **Policy Generator (`scripts/policy/policy.py`)**: Ingests the JSON call array from the analyzers (via `stdin`), maps methods to IAM permissions using `permissions.py`, resolves attachment points/principals, and outputs consolidated IAM V3 Allow Policies.

---

## Execution

### 1. End-to-End Pipeline (Recommended)
Chain the analyzer and policy generator together using standard Unix streams (`stdin`/`stdout`).

#### For Python Projects:
```bash
./.venv/bin/python3 scripts/python/analyzer.py <path_to_target_project> [python_env_path] | ./.venv/bin/python3 scripts/policy/policy.py [--service-account=my-sa@project.iam.gserviceaccount.com] [--json]
```

#### For Go Projects:
```bash
go run scripts/go/analyzer.go <path_to_target_project> | ./.venv/bin/python3 scripts/policy/policy.py [--service-account=my-sa@project.iam.gserviceaccount.com] [--json]
```

### 2. Two-Step Execution (For Auditing & CI/CD)
You can save the analyzer's structured JSON output to an intermediate file for compliance auditing or debugging against `schema.json`, then generate policies via shell stream redirection:

```bash
# Step 1: Generate scan artifact
./.venv/bin/python3 scripts/python/analyzer.py /path/to/project > scan_results.json

# Step 2: Generate IAM policies from artifact
./.venv/bin/python3 scripts/policy/policy.py < scan_results.json
```

---

## Analyzing Results

### 1. Analyzer JSON Output (`schema.json`)
The analyzer emits a clean JSON array of detected calls to `stdout` (while logging progress to `stderr`):

```json
[
  {
    "fullname": "google.cloud.asset_v1.AssetServiceClient.list_assets",
    "file_path": "/path/to/tools/assets.py",
    "line": 32,
    "source_line": "for asset in client.list_assets(request=request):",
    "resolution": "jedi",
    "credentials": {
      "source": "default/implicit",
      "provenance": "IMPLICIT",
      "identity": "APP"
    }
  }
]
```

### 2. Generated IAM V3 Policy Output
The policy generator consolidates permissions by attachment point and principal:

```json
====================================================
🔒 Generated GCP IAM V3 Allow Policies
====================================================

📍 Attachment Point: projects/{project_id}
{
    "name": "policies/projects/{project_id}/allowpolicies/workload-policy",
    "displayName": "Consolidated Workload Allow Policy",
    "rules": [
        {
            "description": "Allow workload permissions for principal://iam.googleapis.com/projects/-/serviceAccounts/your-service-account@your-project.iam.gserviceaccount.com",
            "allowRule": {
                "allowPrincipals": [
                    "principal://iam.googleapis.com/projects/-/serviceAccounts/your-service-account@your-project.iam.gserviceaccount.com"
                ],
                "allowPermissions": [
                    "bigquery.jobs.create",
                    "bigquery.tables.list",
                    "cloudasset.assets.searchAllResources",
                    "compute.instances.list",
                    "container.clusters.list"
                ]
            }
        }
    ]
}
====================================================
```

---

## Troubleshooting & Fallbacks

- **Unresolved Python Types (`Any` or `[fallback]`)**:
  If Jedi cannot find type definitions for external client libraries, provide the path to the target project's virtual environment as the second parameter to `analyzer.py`:
  ```bash
  ./.venv/bin/python3 scripts/python/analyzer.py /path/to/project /path/to/project/.venv/bin/python | ./.venv/bin/python3 scripts/policy/policy.py
  ```
- **Go Package Compilation Warnings**:
  The Go analyzer uses `golang.org/x/tools/go/packages` and will gracefully attempt to scan ASTs even if the target project has partial compilation errors.
