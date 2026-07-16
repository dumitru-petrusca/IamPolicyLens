"""Utility to convert permissions to roles based on an IAMDB JSON dump."""

import argparse
import json
import os
import sys
from typing import List, Dict, Set, Any, Tuple

# Hardcoded roles to filter out in standard mode
BASIC_ROLES = {
    "roles/browser",
    "roles/owner",
    "roles/editor",
    "roles/viewer",
}

# Service Agent roles to filter out
SERVICE_AGENT_ROLES = {
    "roles/dataproc.hubAgent",
}

# Specialized roles to filter out
SPECIALIZED_ROLES = {
    "roles/notebooks.legacyAdmin",
    "roles/notebooks.legacyViewer",
    "roles/storage.legacyBucketOwner",
    "roles/storage.legacyBucketReader",
    "roles/storage.legacyBucketWriter",
    "roles/storage.legacyObjectOwner",
    "roles/storage.legacyObjectReader",
    "roles/compute.futureReservationViewer",
    "roles/compute.futureReservationUser",
    "roles/compute.futureReservationAdmin",
    "roles/storage.insightsCollectorService",
}


class Role:
    """Represents a simplified role for inference."""

    def __init__(self, name: str, title: str, description: str, service_name: str, permissions: List[str]):
        """Initializes a Role instance."""
        self.name = name
        self.title = title
        self.description = description
        self.service_name = service_name
        self.permissions = set(permissions)
        self.total_cost = 0.0
        self.max_permission_cost = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts the role to a dictionary representation."""
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "permissions": sorted(list(self.permissions)),
        }


class Perm2RoleService:
    """Service to infer roles from permissions."""

    def __init__(self, roles_dump: List[Dict[str, Any]], aev_only: bool = False):
        """Initializes the Perm2RoleService with dumped roles."""
        self.viewer_permissions: Set[str] = set()
        self.editor_permissions: Set[str] = set()
        self.owner_permissions: Set[str] = set()
        self.roles: List[Role] = []

        # Find basic permissions for cost modeling
        for r in roles_dump:
            if r["name"] == "roles/viewer":
                self.viewer_permissions = set(r.get("permissions", []))
            elif r["name"] == "roles/editor":
                self.editor_permissions = set(r.get("permissions", []))
            elif r["name"] == "roles/owner":
                self.owner_permissions = set(r.get("permissions", []))

        # Filter and load roles
        for r in roles_dump:
            name = r["name"]
            service_name = r.get("service_name", "")

            # Apply filters
            if r.get("service_name") == "service_roles" or name in SERVICE_AGENT_ROLES or name in SPECIALIZED_ROLES:
                continue

            if aev_only:
                is_basic_aev = name in {"roles/admin", "roles/editor", "roles/viewer"}
                is_service_aev = name.endswith(".admin") or name.endswith(".editor") or name.endswith(".viewer")
                if not is_basic_aev and not is_service_aev:
                    continue
            else:
                if name in BASIC_ROLES:
                    continue

            role = Role(
                name=name,
                title=r.get("title", ""),
                description=r.get("description", ""),
                service_name=service_name,
                permissions=r.get("permissions", [])
            )
            self.roles.append(role)

        # Sort roles by name for determinism
        self.roles.sort(key=lambda x: x.name)

        # Calculate costs
        for role in self.roles:
            costs = [self.permission_cost(p) for p in role.permissions]
            if costs:
                role.max_permission_cost = max(costs)
                role.total_cost = sum(costs)
            else:
                role.max_permission_cost = 0.0
                role.total_cost = 0.0

    def permission_cost(self, p: str) -> float:
        """Calculates the cost of a permission."""
        if p == "iam.serviceaccounts.actAs" or p.endswith(".setIamPolicy"):
            return 4.0
        if p in self.viewer_permissions:
            return 1.0
        if p in self.editor_permissions:
            return 2.0
        if p in self.owner_permissions:
            return 3.0
        return 0.0

    def role_cost(self, r: Role, uncovered_permissions: Set[str]) -> float:
        """Calculates the cost score of a role for covering uncovered permissions."""
        covered_permissions = r.permissions.intersection(uncovered_permissions)
        if not covered_permissions:
            return 0.0

        for permission in covered_permissions:
            # Is the permission too expensive for this role?
            if self.permission_cost(permission) > r.max_permission_cost:
                return 0.0
            # Is the permission in the same service as the role?
            if not permission.startswith(r.service_name + "."):
                return 0.0

        if r.total_cost == 0:
            return 0.0

        return len(covered_permissions) / r.total_cost

    def infer(self, permissions: List[str]) -> Tuple[List[Role], Set[str]]:
        """Infers the best roles to cover the given permissions."""
        # Filter candidate roles to only those covering requested services
        service_names = {p.split(".")[0] for p in permissions}
        candidates = [r for r in self.roles if r.service_name in service_names]

        chosen_roles: List[Role] = []
        uncovered = set(permissions)

        while uncovered:
            best_role = None
            best_score = 0.0

            for role in candidates:
                score = self.role_cost(role, uncovered)
                if score > best_score:
                    best_role = role
                    best_score = score

            if not best_role:
                break  # No role covers any remaining permission

            # Remove newly covered permissions
            covered_in_this_step = best_role.permissions.intersection(uncovered)
            uncovered.difference_update(covered_in_this_step)

            # Create a simplified role instance for output, covering only requested permissions
            chosen_roles.append(Role(
                name=best_role.name,
                title=best_role.title,
                description=best_role.description,
                service_name=best_role.service_name,
                permissions=list(covered_in_this_step)
            ))

        return chosen_roles, uncovered


def main():
    """Main function to parse arguments and run inference."""
    parser = argparse.ArgumentParser(description="Convert permissions to roles using IAMDB JSON dump.")
    parser.add_argument("--permissions", required=True, help="Comma-separated list of permissions")
    parser.add_argument("--dump_file", default="iamdb_roles.json", help="Path to IAMDB JSON dump file")
    parser.add_argument("--aev_only", action="store_true", help="Filter to only AEV roles")

    args = parser.parse_args()

    permissions = [p.strip() for p in args.permissions.split(",")]

    if not os.path.exists(args.dump_file):
        print(f"Error: Dump file not found: {args.dump_file}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.dump_file, "r") as f:
            roles_dump = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    service = Perm2RoleService(roles_dump, aev_only=args.aev_only)

    print(f"Inferring roles for permissions: {permissions}")
    chosen_roles, uncovered = service.infer(permissions)

    if uncovered:
        print(f"Error: not all permissions were covered: {uncovered}", file=sys.stderr)
        sys.exit(1)

    print("Recommended Roles:")
    for role in chosen_roles:
        print(f"- {role.name} (covers: {sorted(list(role.permissions))})")


if __name__ == "__main__":
    main()
