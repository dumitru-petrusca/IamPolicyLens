# Google Agentic Coding - Skills Repository

This repository serves as a centralized collection of advanced, agentic AI skills designed for Google Cloud automation, governance, security, and cost optimization. These skills empower AI agents and developers to perform complex static analysis, IAM policy generation, and infrastructure optimization across multi-language codebases.

---

### 1. IAM Policy Lens (`/iam-policy-lens`)
**IAM Policy Lens** is a multi-language static analysis tool and automated least-privilege IAM policy generator. It scans application source code to identify Google Cloud, Vertex AI, GenAI, and Google API client library invocations, resolves their fully qualified names, traces credential provenance, and generates tailored, least-privilege IAM policies.

- **Supported Languages**: Go, TypeScript / Node.js, Python
- **Documentation**: See the [IAM Policy Lens README](./iam-policy-lens/README.md) for full installation instructions, agent usage prompts, and architectural details.

---

### GCP Cost Optimizer Agent (`/gcp_cost_optimizer_agent`)
**GCP Cost Optimizer Agent** is a multi-language sample agent codebase (available in Go, TypeScript, and Python) provided as a realistic test environment. It is designed to validate and demonstrate the capabilities of the IAM Policy Lens skill by simulating real-world Google Cloud infrastructure analysis and API invocations.
