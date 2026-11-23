"""Department-aware RBAC helpers.

Global roles come from ``Member.role`` (admin/executive/manager/rep/readonly).
Department roles come from ``DepartmentMember.role`` (manager/member/readonly).
Admins bypass checks; executives get read access to every department.
"""
from __future__ import annotations

from typing import Iterable, Optional

DEPARTMENTS = {
    "sales": {"name": "Sales", "description": "Pipeline, leads, deals and revenue"},
    "marketing": {"name": "Marketing", "description": "Campaigns, segments and attribution"},
    "support": {"name": "Support", "description": "Tickets, SLAs and customer replies"},
    "hr": {"name": "HR", "description": "People, attendance, leave and payroll simulation"},
    "finance": {"name": "Finance", "description": "Invoices, expenses and revenue"},
    "operations": {"name": "Operations", "description": "Internal tasks, assets and requests"},
    "executive": {"name": "Executive", "description": "Cross-department performance"},
}

ALL_DEPARTMENTS = tuple(DEPARTMENTS.keys())

ROLE_PERMISSIONS = {
    "admin": {"*"},
    "executive": {
        "dashboard.read",
        "dashboard.*.read",
        "analytics.read",
        "crm.read",
        "campaign.read",
        "email.read",
    },
    "manager": {
        "dashboard.read",
        "analytics.read",
        "crm.read",
        "crm.write",
        "campaign.read",
        "campaign.write",
        "campaign.send",
        "email.read",
        "email.write",
        "email.send",
    },
    "member": {
        "dashboard.read",
        "analytics.read",
        "crm.read",
        "crm.write",
        "campaign.read",
        "campaign.write",
        "email.read",
        "email.write",
    },
    "readonly": {"dashboard.read", "analytics.read", "crm.read", "campaign.read", "email.read"},
    "rep": {
        "dashboard.read",
        "analytics.read",
        "crm.read",
        "crm.write",
        "campaign.read",
        "email.read",
        "email.write",
    },
}


def department_meta(key: str) -> dict:
    return DEPARTMENTS.get(key, {"name": key.title(), "description": ""})


def _matches(granted: Iterable[str], permission: str) -> bool:
    if "*" in granted or permission in granted:
        return True
    if permission.startswith("dashboard.") and "dashboard.*.read" in granted:
        return True
    return False


def role_permissions(role: str) -> set[str]:
    return set(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["readonly"]))


def has_permission(user, permission: str, department: Optional[str] = None) -> bool:
    global_role = getattr(user, "role", "readonly")
    if global_role == "admin":
        return True
    if global_role == "executive":
        return _matches(role_permissions("executive"), permission)
    departments = getattr(user, "departments", []) or []
    if department:
        match = next((d for d in departments if d.get("key") == department), None)
        if not match:
            return False
        role = match.get("role") or "readonly"
        return _matches(role_permissions(role), permission)
    for d in departments:
        if _matches(role_permissions(d.get("role") or "readonly"), permission):
            return True
    return _matches(role_permissions(global_role), permission)


def accessible_departments(user) -> list[dict]:
    global_role = getattr(user, "role", "readonly")
    if global_role in {"admin", "executive"}:
        return [
            {"key": key, "name": meta["name"], "description": meta["description"], "role": global_role}
            for key, meta in DEPARTMENTS.items()
        ]
    return list(getattr(user, "departments", []) or [])
