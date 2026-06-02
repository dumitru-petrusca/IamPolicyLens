#!/usr/bin/env python3
"""
Terraform IAM Least-Privilege Verification Gate - GitLab CI/CD Wrapper
======================================================================

Imports the platform-agnostic verification core engine and formats 
the output specifically for GitLab CI/CD pipeline runs (standard logs, Code Climate 
Code Quality JSON files, and MR artifact summary markdown).
"""

import os
import sys
import json
import argparse
import hashlib
from verify_iam import verify_least_privilege, resolve_relative_path, generate_api_scan_report


def main():
    parser = argparse.ArgumentParser(
        description="Verify if Terraform Custom Roles cover required permissions (GitLab CI/CD wrapper)."
    )
    parser.add_argument(
        "--tf-dir",
        required=True,
        help="Path to the directory containing your Terraform (.tf) files."
    )
    parser.add_argument(
        "--policy-json",
        required=True,
        help="Path to the Policy Lens JSON file (analyzer or policy generator output)."
    )
    parser.add_argument(
        "--gapic-calls",
        required=False,
        default=None,
        help="Path to the raw GAPIC calls JSON (enables inline code annotations)."
    )
    parser.add_argument(
        "--codequality-file",
        default="gl-code-quality-report.json",
        help="Path to save the GitLab Code Quality JSON report."
    )
    parser.add_argument(
        "--summary-file",
        default="iam-verification-summary.md",
        help="Path to save the Markdown summary report."
    )
    parser.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Fail the verification if extra (over-privileged) permissions are granted in Terraform."
    )

    args = parser.parse_args()
    workspace = os.getenv("CI_PROJECT_DIR", ".")

    print("--------------------------------------------------")
    print("🔒 Running Static IAM Least-Privilege Verification (GitLab)")
    print("--------------------------------------------------")
    print(f"Terraform Directory: {args.tf_dir}")
    print(f"Policy Lens Artifact: {args.policy_json}")
    if args.gapic_calls:
        print(f"GAPIC Calls Artifact: {args.gapic_calls}")
    print("--------------------------------------------------")

    try:
        results = verify_least_privilege(args.tf_dir, args.policy_json, args.gapic_calls)
    except Exception as e:
        print(f"Error performing verification: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"🔍 Codebase requires:  {sorted(list(results.required))}")
    print(f"🛡️ Terraform grants:  {sorted(list(results.granted))}")
    print("--------------------------------------------------")

    api_report = generate_api_scan_report(args.gapic_calls, workspace)
    summary = api_report + [
        "### 🔒 IAM Least-Privilege Verification Report",
        f"Verified Terraform configurations against **{len(results.required)} required permissions**.\n"
    ]
    
    issues = []

    if results.missing:
        print("❌ Under-privileged: Missing permissions detected!", file=sys.stderr)
        summary.append("#### ❌ Under-privileged Permissions (Missing)")
        summary.append("The following required permissions are NOT granted in Terraform HCL:")
        summary.append("| Permission | Required By (Code Location) | Method |")
        summary.append("| :--- | :--- | :--- |")

        for perm in sorted(list(results.missing)):
            locs = results.missing_locs.get(perm, [])
            if locs:
                for loc in locs:
                    rel_path = resolve_relative_path(loc["file_path"], workspace)
                    line = loc["line"]
                    method = loc["method"]
                    
                    print(f"Error: Code requires permission '{perm}' via '{method}' in {rel_path}:{line}, but it is not granted in Terraform.", file=sys.stderr)
                    summary.append(f"| `{perm}` | `{rel_path}:{line}` | `{method}` |")
                    
                    # Build CodeQuality structure
                    fingerprint = hashlib.md5(f"missing-{perm}-{rel_path}-{line}".encode('utf-8')).hexdigest()
                    issues.append({
                        "description": f"Code requires GCP permission '{perm}' via '{method}' but it is not granted in Terraform.",
                        "check_name": "missing-iam-permission",
                        "fingerprint": fingerprint,
                        "severity": "major",
                        "location": {
                            "path": rel_path,
                            "lines": {
                                "begin": line
                            }
                        }
                    })
            else:
                print(f"Error: Required permission '{perm}' is not granted in Terraform.", file=sys.stderr)
                summary.append(f"| `{perm}` | *Location Unknown* | *N/A* |")
                
                fingerprint = hashlib.md5(f"missing-{perm}-unknown".encode('utf-8')).hexdigest()
                issues.append({
                    "description": f"Required GCP permission '{perm}' is not granted in Terraform HCL.",
                    "check_name": "missing-iam-permission",
                    "fingerprint": fingerprint,
                    "severity": "major",
                    "location": {
                        "path": args.tf_dir,
                        "lines": {
                            "begin": 1
                        }
                    }
                })
        summary.append("\n")

    if results.extra:
        print("⚠️ Over-privileged: Extra permissions detected!", file=sys.stderr)
        if args.fail_on_extra:
            summary_header = "#### ❌ Over-privileged Permissions (Extra - FAILED)"
        else:
            summary_header = "#### ⚠️ Over-privileged Permissions (Extra - Warning)"

        summary.append(summary_header)
        summary.append("The following granted permissions are NOT used by any code:")
        summary.append("| Permission | Granted In (Terraform Location) |")
        summary.append("| :--- | :--- |")

        for perm in sorted(list(results.extra)):
            locs = results.tf_locs.get(perm, [])
            if locs:
                for loc in locs:
                    rel_path = resolve_relative_path(loc.file, workspace)
                    lvl_prefix = "Error" if args.fail_on_extra else "Warning"
                    print(f"{lvl_prefix}: GCP permission '{perm}' is granted in Terraform HCL but not required by any API calls in the codebase at {rel_path}:{loc.line}.", file=sys.stderr)
                    summary.append(f"| `{perm}` | `{rel_path}:{loc.line}` |")
                    
                    fingerprint = hashlib.md5(f"extra-{perm}-{rel_path}-{loc.line}".encode('utf-8')).hexdigest()
                    issues.append({
                        "description": f"GCP permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.",
                        "check_name": "over-privileged-iam-permission",
                        "fingerprint": fingerprint,
                        "severity": "major" if args.fail_on_extra else "minor",
                        "location": {
                            "path": rel_path,
                            "lines": {
                                "begin": loc.line
                            }
                        }
                    })
            else:
                lvl_prefix = "Error" if args.fail_on_extra else "Warning"
                print(f"{lvl_prefix}: Permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.", file=sys.stderr)
                summary.append(f"| `{perm}` | *Location Unknown* |")
                
                fingerprint = hashlib.md5(f"extra-{perm}-unknown".encode('utf-8')).hexdigest()
                issues.append({
                    "description": f"GCP permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.",
                    "check_name": "over-privileged-iam-permission",
                    "fingerprint": fingerprint,
                    "severity": "major" if args.fail_on_extra else "minor",
                    "location": {
                        "path": args.tf_dir,
                        "lines": {
                            "begin": 1
                        }
                    }
                })
        summary.append("\n")

    # If everything is clean
    if not results.missing and not results.extra:
        print("✅ Verification Succeeded! All permissions match exactly (least-privilege achieved).")
        summary.append("✅ **Verification Succeeded!** All permissions match exactly (least-privilege achieved).")
    elif not results.missing and results.extra and not args.fail_on_extra:
        print("✅ Verification Succeeded! Required permissions are covered. (Warnings generated for extra permissions)")
        summary.append("✅ **Verification Succeeded!** Required permissions are fully covered. (Some over-privileged warnings exist)")

    # Write GitLab Code Quality Report
    if args.codequality_file:
        try:
            with open(args.codequality_file, "w", encoding="utf-8") as f:
                json.dump(issues, f, indent=2)
            print(f"✅ Wrote GitLab Code Quality report to {args.codequality_file}")
        except Exception as e:
            print(f"Warning: Failed to write GitLab Code Quality report: {e}", file=sys.stderr)
    
    # Write GitLab Markdown Summary File
    if args.summary_file:
        try:
            with open(args.summary_file, "w", encoding="utf-8") as f:
                f.write("\n".join(summary) + "\n")
            print(f"✅ Wrote GitLab markdown summary to {args.summary_file}")
        except Exception as e:
            print(f"Warning: Failed to write GitLab markdown summary: {e}", file=sys.stderr)

    if results.missing or (results.extra and args.fail_on_extra):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
