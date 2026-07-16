# IAM Policy Lens

**IAM Policy Lens** is a multi-language static analysis tool and automated least-privilege IAM policy generator. It scans application source code to identify Google Cloud, Vertex AI, GenAI, and Google API client library invocations, resolves their fully qualified names, traces credential provenance, and generates tailored, least-privilege IAM policies.

---

## 🌟 Capabilities
- **Supported Languages**: Go, TypeScript / Node.js, Python
- **AST-based Static Analysis**: Performs deep semantic type checking and symbol resolution across complex project structures.
- **Credential Provenance Tracking**: Identifies Service Account explicit keys, Impersonation, OAuth flows, and Default/Implicit credentials.
- **Automated IAM Mapping**: Maps discovered API calls directly to required IAM permissions.
- **Automated Policy Generation**: Consolidates discovered permissions by attachment point (e.g., project-level or regional locations) and generates GCP IAM V3 Allow Policies.

---

## 🚀 Installation & Setup

### Skill Installation
To install the IAM Policy Lens skill into your agent, run:
```bash
npx skills add dumitru-petrusca/IamPolicyLens
```

Once installed, the agent will automatically manage and install all required language-specific dependencies (Python virtual environments, TypeScript builds, and Go modules) as needed during execution. 

> [!NOTE]
> If the Python virtual environment is missing or broken, the agent can self-recover by re-initializing it and installing dependencies from `scripts/python/requirements.txt` (instructions are provided in `SKILL.md`).


---

## 💡 Usage Instructions

Once the IAM Policy Lens skill is installed, you do not need to execute the underlying scanner scripts directly (agent execution mechanics are detailed in `SKILL.md`). Instead, simply interact with your AI agent using natural language prompts.

Here are example prompts you can ask your agent:

### 🔍 Codebase Scanning & Auditing
> *"Scan my Python agent at `/path/to/backend` and list all Google Cloud API client library invocations it makes."*

> *"Audit the Go agent in `./services/payment` and tell me what GCP services and methods are being used."*

### 🔐 Permission Determination
> *"Analyze my TypeScript agent in `/frontend-node` and determine the exact IAM permissions required for the discovered storage and bigquery calls."*

### 📜 Automated Policy Generation
> *"Generate a consolidated, least-privilege GCP IAM Allow Policy for my Go project at `/path/to/api` bound to `my-sa@my-project.iam.gserviceaccount.com`."*

---

## ALTERNATIVES

### Python Scanner Library Alternatives
The `iam-policy-lens` Python scanner currently uses `jedi` for static analysis and type inference. While `jedi` is excellent for IDE autocompletion, it can be limited for deep static analysis across complex project structures. 

For more robust AST traversal, scope tracking, and reliable type inference (`node.infer()`), the Python scanner could benefit from switching to:
- **[astroid](https://github.com/pylint-dev/astroid)**: The robust AST and type-inference engine behind Pylint, providing built-in type inference and scope resolution.

### TypeScript Scanner Library Alternatives
The `iam-policy-lens` TypeScript scanner currently uses the official `typescript` compiler API. While extremely powerful, the native Compiler API is notoriously low-level and verbose.

For improved ergonomics with full semantic type checking support, the TypeScript scanner could consider:
- **[ts-morph](https://github.com/dsherret/ts-morph)**: A comprehensive, high-level wrapper around the TypeScript Compiler API that dramatically simplifies AST navigation, type checking, and symbol resolution while maintaining full access to the underlying TypeChecker.

### Go Scanner Library Alternatives
The `iam-policy-lens` Go scanner currently uses `golang.org/x/tools/go/packages` alongside the standard `go/ast` and `go/types` packages.

For a more modular architecture with automated pass management and built-in type checking support, the Go scanner could explore:
- **[golang.org/x/tools/go/analysis](https://pkg.go.dev/golang.org/x/tools/go/analysis)**: The official Go static analysis framework (used by `go vet` and `gopls`). It provides a robust, modular architecture (`analysis.Analyzer`) where each pass automatically receives fully resolved type information (`pass.TypesInfo`), along with built-in caching and fact sharing across packages.
