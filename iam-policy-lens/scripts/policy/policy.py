"""
GCP IAM Policy Generator
========================

Problem Statement:
------------------
This script consumes the structured JSON output from the Python or Go GAPIC analyzers, maps the detected API calls to their required IAM permissions, and generates consolidated GCP IAM Policies (V1 or V3).

How It Works:
-------------
1. Ingests a JSON array of `GapicCall` objects (via stdin).
2. Maps each fully qualified method name to its required IAM permissions using `permissions.py`.
3. Resolves the target principal (e.g., Service Account, User, or Impersonated SA) based on credential provenance.
4. Consolidates permissions by attachment point (e.g., project or regional location) and outputs IAM Policies.

How to Run:
-----------
1. Using Standard Streams (Unix Pipes):
    .venv/bin/python3 scripts/python/analyzer.py /path/to/project | .venv/bin/python3 scripts/policy/policy.py
    go run scripts/go/analyzer.go /path/to/project | .venv/bin/python3 scripts/policy/policy.py

2. Using Shell Stream Redirection (Intermediate File):
    .venv/bin/python3 scripts/policy/policy.py < result-python.txt
    .venv/bin/python3 scripts/policy/policy.py < result-go.txt [--json] [--service-account=my-sa@project.iam.gserviceaccount.com] [--policy-kind {v1,v3}]

./.venv/bin/python3 scripts/policy/policy.py < result-python.txt
./.venv/bin/python3 scripts/policy/policy.py < result-go.txt
"""
import os
import sys
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set


sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../python')))

from gapic import GapicCall
from credentials import CredentialProvenance, IdentityContext, CredentialsInfo
from permissions import gapic2permission

from perm2role import Perm2RoleService

def _resolve_principal(call: GapicCall, default_sa: str = "your-service-account@your-project.iam.gserviceaccount.com", version: str = "v3") -> str:
    """Resolves the target principal email to bind the policy to."""
    sa_email = default_sa
    is_user = False
    
    if call.credentials:
        prov = call.credentials.provenance
        source = call.credentials.source
        
        if prov == CredentialProvenance.IMPERSONATION:
            match = re.search(r"target_principal\s*=\s*['\"]([^'\"]+)['\"]", source)
            if match:
                sa_email = match.group(1)
            else:
                sa_email = "target-impersonated-sa@your-project.iam.gserviceaccount.com"
                
        elif prov in (CredentialProvenance.OAUTH_USER, CredentialProvenance.OAUTH_FLOW):
            is_user = True
            
    if is_user:
        if version == "v1":
            return "user:your-user-email@domain.com"
        return "principalSet://goog/subject/your-user-email@domain.com"
        
    if version == "v1":
        return f"serviceAccount:{sa_email}"
    return f"principal://iam.googleapis.com/projects/-/serviceAccounts/{sa_email}"

def _resolve_attachment_point(call: GapicCall) -> str:
    """Determines the target container resource path (attachment point) for the permission."""
    fullname = call.fullname
    
    # Vertex AI (Agent Engines) is regional
    if "aiplatform" in fullname or "vertexai.agent_engines" in fullname:
        return "projects/{project_id}/locations/{location}"
        
    return "projects/{project_id}"

def _detect_agent_engine(calls: List[GapicCall], sa_email: str, version: str) -> tuple[Optional[str], Set[str]]:
    """Detects the agent engine deployment platform (GEAPR or Cloud Run) and associated agent principals."""
    engine = None
    agent_principals = set()

    for call in calls:
        # Check if call is an ADK Agent definition/instantiation
        if any(adk_pkg in call.fullname for adk_pkg in ("google.adk.agents", "@google/adk", "google.golang.org/adk/agent")):
            agent_principals.add(_resolve_principal(call, sa_email, version))
    
    if agent_principals:
        has_reasoning = any(
            "reasoningEngines" in call.fullname or "agent_engines" in call.fullname or "aiplatform" in call.fullname
            for call in calls
        )
        has_run = any(
            "run_v2" in call.fullname or "run/apiv2" in call.fullname or "run.ServicesClient" in call.fullname
            for call in calls
        )
        if has_reasoning:
            engine = "reasoning_engine"
        elif has_run:
            engine = "cloud_run"
        else:
            engine = "reasoning_engine"  # Default fallback for ADK agents
                
    return engine, agent_principals

def generate_iam_policies(calls: List[GapicCall], default_sa: str = None, version: str = "v3", perm2role_service: Optional['Perm2RoleService'] = None) -> List[Dict]:
    """Generates a set of consolidated GCP IAM Policies grouped by attachment point."""
    sa_email = default_sa or "your-service-account@your-project.iam.gserviceaccount.com"
    
    # Structure: attachment_point -> principal -> set of permissions
    policies_map: Dict[str, Dict[str, Set[str]]] = {}
    
    for call in calls:
        permissions = gapic2permission(call.fullname)
        if not permissions:
            continue
            
        principal = _resolve_principal(call, sa_email, version)
        attachment = _resolve_attachment_point(call)
        
        policies_map.setdefault(attachment, {}).setdefault(principal, set()).update(permissions)
        
    # Determine agent engine deployment for birthright roles (GEAPR / Cloud Run)
    engine, agent_principals = _detect_agent_engine(calls, sa_email, version)
                    
    if version == "v1":
        # Convert permissions to roles
        v1_policies_map: Dict[str, Dict[str, Set[str]]] = {}
        for attachment, principal_map in policies_map.items():
            for principal, permissions in principal_map.items():
                if not perm2role_service:
                    print("Error: Perm2RoleService required for V1 policies", file=sys.stderr)
                    continue
                chosen_roles, uncovered = perm2role_service.infer(list(permissions))
                if uncovered:
                    print(f"Warning: could not cover all permissions for {principal} at {attachment}: {uncovered}", file=sys.stderr)
                for role in chosen_roles:
                    v1_policies_map.setdefault(attachment, {}).setdefault(role.name, set()).add(principal)
        
        # Augment with birthright roles at the project-level policy
        if engine == "reasoning_engine":
            for r in ["roles/aiplatform.agentDefaultAccess", "roles/aiplatform.agentContextEditor"]:
                for principal in agent_principals:
                    v1_policies_map.setdefault("projects/{project_id}", {}).setdefault(r, set()).add(principal)
        elif engine == "cloud_run":
            for r in ["roles/run.agent"]:
                for principal in agent_principals:
                    v1_policies_map.setdefault("projects/{project_id}", {}).setdefault(r, set()).add(principal)
                    
        generated_policies = []
        for attachment, role_map in sorted(v1_policies_map.items()):
            bindings = []
            for role, members in sorted(role_map.items()):
                bindings.append({
                    "role": role,
                    "members": sorted(list(members))
                })
            generated_policies.append({
                "attachment_point": attachment,
                "policy": {
                    "bindings": bindings
                }
            })
        return generated_policies

    # V3 Logic
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
    parser.add_argument(
        "--policy-kind",
        choices=["v1", "v3"],
        default="v3",
        help="Type of policy to generate (v1 or v3). Defaults to v3."
    )
    parser.add_argument(
        "--dump-file",
        default=os.path.join(os.path.dirname(__file__), "iamdb_roles.json"),
        help="Path to IAMDB JSON dump file (required for V1 policies)."
    )
    parser.add_argument(
        "--least-privilege",
        action="store_true",
        help="Use fine-grained least privilege roles instead of the default AEV roles (for V1 policies)."
    )


    args = parser.parse_args()

    perm2role_service = None
    if args.policy_kind == "v1":
        if not os.path.exists(args.dump_file):
            print(f"Error: Dump file not found: {args.dump_file}", file=sys.stderr)
            print("Dump file is required for V1 policies.", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.dump_file, "r") as f:
                roles_dump = json.load(f)
            perm2role_service = Perm2RoleService(roles_dump, least_privilege=args.least_privilege)
        except Exception as e:
            print(f"Error loading dump file: {e}", file=sys.stderr)
            sys.exit(1)

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

    policies = generate_iam_policies(
        calls, 
        args.service_account, 
        version=args.policy_kind, 
        perm2role_service=perm2role_service
    )

    if args.json:
        print(json.dumps(policies, indent=2))
    else:
        print("\n====================================================")
        print(f"🔒 Generated GCP IAM {args.policy_kind.upper()} Policies")
        print("====================================================")
        for p in policies:
            print(f"\n📍 Attachment Point: {p['attachment_point']}")
            print(json.dumps(p['policy'], indent=4))
        print("\n====================================================")

