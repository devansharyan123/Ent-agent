# backend/services/rag_service.py

def filter_docs_by_role(user_role, docs):

    allowed = {
        "Admin": ["admin", "hr", "general"],
        "HR": ["hr", "general"],
        "Employee": ["general"]
    }

    return [
        d for d in docs
        if d.metadata.get("category") in allowed[user_role]
    ]