# IAM Policy Lens

**IAM Policy Lens** is a multi-language static IAM analysis tool, automated IAM policy generator and policy verifier. It scans application source code to identify Google API client library invocations, resolves their fully qualified names, and generates tailored, least-privilege IAM policies.

---

### 1. IAM Policy Lens Skill (`/iam-policy-lens`)
**IAM Policy Lens** is a multi-language static analysis tool and automated least-privilege IAM policy generator. It scans application source code to identify Google API client library invocations, resolves their fully qualified names, traces credential provenance, and generates tailored, least-privilege IAM policies.

- **Supported Languages**: Go, TypeScript / Node.js, Python
- **Documentation**: See the [IAM Policy Lens README](./iam-policy-lens/README.md) for full installation instructions, agent usage prompts, and architectural details.

---

### 2. IAM Policy Lens GitHub Actions ([/actions](./actions))
This repository provides pre-built GitHub Actions and reference workflows to automate static code scanning, least-privilege IAM policy generation, and automatic Terraform verification on every Pull Request.

For complete setup instructions, details on all custom actions, input/output specifications, and a reference workflow configuration, please see the [GitHub Actions README](./actions/README.md).

---

### 3. GCP Cost Optimizer Agent (`/gcp_cost_optimizer_agent`)
**GCP Cost Optimizer Agent** is a multi-language sample agent codebase (available in Go, TypeScript, and Python) provided as a realistic test environment. It is designed to validate and demonstrate the capabilities of the IAM Policy Lens skill by simulating real-world Google Cloud infrastructure analysis and API invocations.
