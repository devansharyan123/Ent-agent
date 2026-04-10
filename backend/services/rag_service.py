"""
rag_service.py — Role-category access helper.

RBAC is now enforced at the SQL level inside policy_retrieval_tool.
This module is kept for backward compatibility and utility use.
"""

from typing import List

_ROLE_CATEGORY_MAP = {
    "admin":    ["admin", "hr", "general"],
    "hr":       ["hr", "general"],
    "employee": ["general"],
}


def get_allowed_categories(role: str) -> List[str]:
    """
    Return categories accessible to *role* (case-insensitive).

    Raises:
        ValueError: For unrecognised roles.
    """
    normalised = role.strip().lower() if role else ""
    if normalised not in _ROLE_CATEGORY_MAP:
        raise ValueError(f"Invalid role '{role}'.")
    return _ROLE_CATEGORY_MAP[normalised]


def filter_docs_by_role(user_role: str, docs: list) -> list:
    """
    Filter a list of dicts (each with a 'category' key) to only those
    categories accessible to *user_role*.

    kept for any code that still calls this helper directly.
    """
    try:
        allowed = get_allowed_categories(user_role)
    except ValueError:
        allowed = ["general"]
    return [d for d in docs if d.get("category") in allowed]