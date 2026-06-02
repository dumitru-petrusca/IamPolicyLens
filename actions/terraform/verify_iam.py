import os
import sys
import json
import re
import subprocess
from typing import Set, Dict, List, Optional, Any
from dataclasses import dataclass
from terraform import scan_granted_permissions


def generate_api_scan_report(gapic_calls_path: Optional[str], workspace: str) -> List[str]:
    """Generates a Markdown report table of all discovered API invocations prioritised by git diff changes."""
    if not gapic_calls_path or not os.path.exists(gapic_calls_path):
        return []

    try:
        with open(gapic_calls_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Warning: Error reading JSON results {gapic_calls_path}: {e}", file=sys.stderr)
        return []

    if not isinstance(data, list):
        print("Warning: Invalid JSON format for API scan results. Expected a list.", file=sys.stderr)
        return []

    changed_files = set()
    try:
        res = subprocess.run(["git", "diff", "--name-only", "HEAD^1"], capture_output=True, text=True, cwd=workspace)
        if res.returncode == 0:
            changed_files = {f.strip() for f in res.stdout.splitlines() if f.strip()}
        else:
            print(f"Debug git diff failed: {res.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not determine changed files: {e}", file=sys.stderr)

    def get_priority(call_obj):
        abs_path = call_obj.get("file_path", "")
        rel_p = os.path.relpath(abs_path, workspace) if abs_path else ""
        return 0 if rel_p in changed_files else 1

    data.sort(key=get_priority)

    report_lines = [
        "### 🔍 IAM Policy Lens - Discovered API Invocations",
        f"**Discovered {len(data)} Google Cloud API invocation(s)** across the codebase.\n",
        "| File | Line | Resolved Method | Client |",
        "| :--- | :---: | :--- | :--- |"
    ]

    for call in data:
        try:
            abs_path = call.get("file_path", "")
            rel_path = os.path.relpath(abs_path, workspace) if abs_path else ""
            line = call.get("line", 0)
            fullname = call.get("fullname", "")
            client = call.get("client_fullname", "N/A") or "N/A"
            
            report_lines.append(f"| `{rel_path}` | `{line}` | `{fullname}` | `{client}` |")
        except Exception as e:
            print(f"Warning: Skipping malformed entry: {e}", file=sys.stderr)

    report_lines.append("\n")
    return report_lines


@dataclass
class IAMVerificationResult:
    required: Set[str]
    granted: Set[str]
    missing_locs: Dict[str, List[Dict[str, Any]]]
    tf_locs: Dict[str, List[Any]]

    @property
    def missing(self) -> Set[str]:
        return self.required - self.granted

    @property
    def extra(self) -> Set[str]:
        return self.granted - self.required


def resolve_relative_path(file_path: str, workspace: str) -> str:
    """Resolves a file path robustly to a relative path from workspace, handling potential ../ prefixes."""
    if not file_path:
        return "N/A"
    resolved_path = file_path
    if not os.path.isabs(resolved_path):
        cwd_path = os.path.abspath(resolved_path)
        if os.path.exists(cwd_path):
            resolved_path = cwd_path
        else:
            ws_path = os.path.abspath(os.path.join(workspace, resolved_path))
            if os.path.exists(ws_path):
                resolved_path = ws_path
            else:
                stripped_path = resolved_path
                while stripped_path.startswith('../'):
                    stripped_path = stripped_path[3:]
                ws_stripped = os.path.abspath(os.path.join(workspace, stripped_path))
                if os.path.exists(ws_stripped):
                    resolved_path = ws_stripped
    return os.path.relpath(resolved_path, workspace)


def get_required_permissions(policy_json_path: str) -> Set[str]:
    """Reads required permissions from the Policy Lens JSON artifact (Consolidated IAM V3 Allow Policies)."""
    with open(policy_json_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON block by finding lines that start/end with JSON markers
        lines = content.splitlines()
        start_idx = -1
        end_idx = -1
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if start_idx == -1 and (stripped.startswith('{') or stripped.startswith('[')):
                start_idx = idx
            if start_idx != -1 and (stripped.startswith('}') or stripped.startswith(']')):
                end_idx = idx

        if start_idx != -1 and end_idx != -1:
            try:
                json_str = "\n".join(lines[start_idx:end_idx+1])
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error: Failed to parse extracted JSON block: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Policy Lens JSON is not valid JSON and no JSON block found.", file=sys.stderr)
            sys.exit(1)

    required = set()

    # Normalize input data to a list of policy items
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        print("Error: Policy Lens JSON must be a list or dict.", file=sys.stderr)
        sys.exit(1)

    for item in items:
        if not isinstance(item, dict):
            continue
        # Can be nested under "policy" key (generator output) or a direct policy object
        policy = item.get("policy") if "policy" in item else item
        if isinstance(policy, dict):
            for rule in policy.get("rules", []):
                if isinstance(rule, dict):
                    allow_rule = rule.get("allowRule", {})
                    if isinstance(allow_rule, dict):
                        permissions = allow_rule.get("allowPermissions", [])
                        if isinstance(permissions, list):
                            required.update(permissions)

    return required


def get_missing_permission_locations(gapic_calls_path: Optional[str], missing_permissions: Set[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Maps each missing permission back to the code locations (file_path, line, gapic_method) that required it."""
    locations = {}  # permission -> list of dict
    if not gapic_calls_path or not os.path.exists(gapic_calls_path):
        return locations

    try:
        # Append target policy dir to sys.path so we can load permissions mapping
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../iam-policy-lens/scripts/policy")))
        from permissions import gapic2permission
    except ImportError:
        print("Warning: Could not import permissions mapper. Inline code annotations for missing permissions will be unavailable.", file=sys.stderr)
        return locations

    try:
        with open(gapic_calls_path, "r", encoding="utf-8") as f:
            calls = json.load(f)

        for call in calls:
            if not isinstance(call, dict):
                continue
            fullname = call.get("fullname")
            if not fullname:
                continue

            perms = gapic2permission(fullname)
            if perms:
                for perm in perms:
                    if perm in missing_permissions:
                        loc = {
                            "file_path": call.get("file_path", ""),
                            "line": call.get("line", 0),
                            "method": fullname,
                            "source_line": call.get("source_line", "").strip()
                        }
                        locations.setdefault(perm, []).append(loc)
    except Exception as e:
        print(f"Warning: Error reading gapic calls for annotations: {e}", file=sys.stderr)

    return locations


def verify_least_privilege(tf_dir: str, policy_json_path: str, gapic_calls_path: Optional[str] = None) -> IAMVerificationResult:
    """Core verification logic returning raw verification statistics and location mapping."""
    required = get_required_permissions(policy_json_path)
    scan_result = scan_granted_permissions(tf_dir)
    granted = {perm.name for perm in scan_result.permissions}

    missing = required - granted
    missing_locs = get_missing_permission_locations(gapic_calls_path, missing)
    tf_locs = {perm.name: perm.locations for perm in scan_result.permissions}

    return IAMVerificationResult(
        required=required,
        granted=granted,
        missing_locs=missing_locs,
        tf_locs=tf_locs
    )



