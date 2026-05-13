"""
GCP IAM Policy Generator
========================

Problem Statement:
------------------
This script consumes the structured JSON output from the Python or Go GAPIC analyzers, maps the detected API calls to their required IAM permissions, and generates consolidated GCP IAM V3 Allow Policies.

How It Works:
-------------
1. Ingests a JSON array of `GapicCall` objects (via stdin).
2. Maps each fully qualified method name to its required IAM permissions using `permissions.py`.
3. Resolves the target principal (e.g., Service Account, User, or Impersonated SA) based on credential provenance.
4. Consolidates permissions by attachment point (e.g., project or regional location) and outputs IAM V3 Allow Policies.

How to Run:
-----------
1. Using Standard Streams (Unix Pipes):
    .venv/bin/python3 scripts/python/analyzer.py /path/to/project | .venv/bin/python3 scripts/policy/policy.py
    go run scripts/go/analyzer.go /path/to/project | .venv/bin/python3 scripts/policy/policy.py

2. Using Shell Stream Redirection (Intermediate File):
    .venv/bin/python3 scripts/policy/policy.py < result-python.txt
    .venv/bin/python3 scripts/policy/policy.py < result-go.txt [--json] [--service-account=my-sa@project.iam.gserviceaccount.com]

./.venv/bin/python3 scripts/policy/policy.py < result-python.txt
./.venv/bin/python3 scripts/policy/policy.py < result-go.txt
"""
import os
import sys
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set


sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../python')))

from gapic import GapicCall
from credentials import CredentialProvenance, IdentityContext, CredentialsInfo
from permissions import gapic2permission


def _resolve_principal(call: GapicCall, default_sa: str = "your-service-account@your-project.iam.gserviceaccount.com") -> str:
    """Resolves the target principal email to bind the policy to, using IAM V3 principal scheme."""
    sa_email = default_sa
    if call.credentials:
        prov = call.credentials.provenance
        source = call.credentials.source
        
        if prov == CredentialProvenance.IMPERSONATION:
            import re
            match = re.search(r"target_principal\s*=\s*['\"]([^'\"]+)['\"]", source)
            if match:
                sa_email = match.group(1)
            else:
                sa_email = "target-impersonated-sa@your-project.iam.gserviceaccount.com"
                
        elif prov in (CredentialProvenance.OAUTH_USER, CredentialProvenance.OAUTH_FLOW):
            return "principalSet://goog/subject/your-user-email@domain.com"
            
    return f"principal://iam.googleapis.com/projects/-/serviceAccounts/{sa_email}"

def _resolve_attachment_point(call: GapicCall) -> str:
    """Determines the target container resource path (attachment point) for the permission."""
    fullname = call.fullname
    
    # Vertex AI (Agent Engines) is regional
    if "aiplatform" in fullname or "vertexai.agent_engines" in fullname:
        return "projects/{project_id}/locations/{location}"
        
    return "projects/{project_id}"

def generate_iam_policies(calls: List[GapicCall], default_sa: str = None) -> List[Dict]:
    """Generates a set of consolidated GCP IAM V3 Allow Policies grouped by attachment point."""
    sa_email = default_sa or "your-service-account@your-project.iam.gserviceaccount.com"
    
    # Structure: attachment_point -> principal -> set of permissions
    policies_map: Dict[str, Dict[str, Set[str]]] = {}
    
    for call in calls:
        permissions = gapic2permission(call.fullname)
        if not permissions:
            continue
            
        principal = _resolve_principal(call, sa_email)
        attachment = _resolve_attachment_point(call)
        
        policies_map.setdefault(attachment, {}).setdefault(principal, set()).update(permissions)
        
    # Convert consolidated maps into GCP IAM V3 Policy JSON format
    generated_policies = []
    
    for attachment, principal_map in sorted(policies_map.items()):
        rules = []
        for principal, permissions in sorted(principal_map.items()):
            rules.append({
                "description": f"Allow workload permissions for {principal}",
                "allowRule": {
                    "allowPrincipals": [principal],
                    "allowPermissions": sorted(list(permissions))
                }
            })
            
        # Map target path to a valid policies resource name
        # E.g. projects/{project_id} -> policies/projects/{project_id}/allowpolicies/workload-policy
        policy_name = f"policies/{attachment}/allowpolicies/workload-policy"
        
        generated_policies.append({
            "attachment_point": attachment,
            "policy": {
                "name": policy_name,
                "displayName": "Consolidated Workload Allow Policy",
                "rules": rules
            }
        })
        
    return generated_policies

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate GCP IAM Allow Policies from analyzer JSON output.")
    parser.add_argument(
        "input_file",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Path to the analyzer JSON output file (defaults to stdin)."
    )
    parser.add_argument(
        "--service-account",
        type=str,
        default=os.getenv("GCP_SERVICE_ACCOUNT"),
        help="Default service account email to bind policies to."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON array of generated policies instead of human-readable blocks."
    )

    args = parser.parse_args()

    try:
        data = json.load(args.input_file)
    except Exception as e:
        print(f"Error reading JSON input: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Invalid input: Expected a JSON array of GAPIC calls.", file=sys.stderr)
        sys.exit(1)

    calls = []
    for item in data:
        try:
            cred_data = item.get("credentials")
            creds = None
            if cred_data:
                creds = CredentialsInfo(
                    source=cred_data.get("source", ""),
                    provenance=CredentialProvenance(cred_data.get("provenance", CredentialProvenance.UNKNOWN)),
                    identity=IdentityContext(cred_data.get("identity", IdentityContext.UNKNOWN)) if cred_data.get("identity") else None
                )
            calls.append(GapicCall(
                fullname=item.get("fullname", ""),
                file_path=item.get("file_path", ""),
                line=item.get("line", 0),
                source_line=item.get("source_line", ""),
                resolution=item.get("resolution", ""),
                client_fullname=item.get("client_fullname"),
                credentials=creds
            ))
        except Exception as e:
            print(f"Warning: Skipping invalid call entry: {e}", file=sys.stderr)

    policies = generate_iam_policies(calls, args.service_account)

    if args.json:
        print(json.dumps(policies, indent=2))
    else:
        print("\n====================================================")
        print("🔒 Generated GCP IAM V3 Allow Policies")
        print("====================================================")
        for p in policies:
            print(f"\n📍 Attachment Point: {p['attachment_point']}")
            print(json.dumps(p['policy'], indent=4))
        print("\n====================================================")

