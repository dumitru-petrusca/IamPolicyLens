#!/usr/bin/env python3
"""
Terraform IAM Least-Privilege Verification Gate - GitHub Actions Wrapper
========================================================================

Imports the platform-agnostic verification core engine and formats 
the output specifically for GitHub Actions workflow runs (inline warnings/errors
and dynamic GHA Step Summary reports).
"""

import os
import sys
import argparse
from verify_iam import verify_least_privilege, resolve_relative_path, generate_api_scan_report


def main():
    parser = argparse.ArgumentParser(
        description="Verify if Terraform Custom Roles cover required permissions (GitHub Actions wrapper)."
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
        "--fail-on-extra",
        action="store_true",
        help="Fail the verification if extra (over-privileged) permissions are granted in Terraform."
    )

    args = parser.parse_args()
    workspace = os.getenv("GITHUB_WORKSPACE", ".")

    print("--------------------------------------------------")
    print("🔒 Running Static IAM Least-Privilege Verification (GHA)")
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
                    
                    # Output GHA inline annotation
                    print(f"::error file={rel_path},line={line},title=Missing IAM Permission::Code requires permission '{perm}' via '{method}', but it is not granted in Terraform.")
                    summary.append(f"| `{perm}` | `{rel_path}:{line}` | `{method}` |")
            else:
                # Generic fallback GHA annotation
                print(f"::error title=Missing IAM Permission::Required permission '{perm}' is not granted in Terraform.")
                summary.append(f"| `{perm}` | *Location Unknown* | *N/A* |")
        summary.append("\n")

    if results.extra:
        print("⚠️ Over-privileged: Extra permissions detected!", file=sys.stderr)
        log_level = "error" if args.fail_on_extra else "warning"
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
                    # Output GHA inline annotation
                    print(f"::{log_level} file={rel_path},line={loc.line},title=Over-privileged IAM Permission::GCP permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.")
                    summary.append(f"| `{perm}` | `{rel_path}:{loc.line}` |")
            else:
                # Generic fallback GHA annotation
                print(f"::{log_level} title=Over-privileged IAM Permission::Permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.")
                summary.append(f"| `{perm}` | *Location Unknown* |")
        summary.append("\n")

    # If everything is clean
    if not results.missing and not results.extra:
        print("✅ Verification Succeeded! All permissions match exactly (least-privilege achieved).")
        summary.append("✅ **Verification Succeeded!** All permissions match exactly (least-privilege achieved).")
    elif not results.missing and results.extra and not args.fail_on_extra:
        print("✅ Verification Succeeded! Required permissions are covered. (Warnings generated for extra permissions)")
        summary.append("✅ **Verification Succeeded!** Required permissions are fully covered. (Some over-privileged warnings exist)")

    # Write GITHUB_STEP_SUMMARY
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write("\n".join(summary) + "\n")
        except Exception as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    if results.missing or (results.extra and args.fail_on_extra):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
