import sys
import os
from unittest.mock import MagicMock

api_key = os.getenv("GROQ_API_KEY")
from backend.agents.tools.recommendation_tool import recommendation_tool

query = "I'm looking for information about leave"
role = "employee"

print(f"Testing Recommendation Tool for query: '{query}' as role: '{role}'")
try:
    result = recommendation_tool(query=query, user_role=role)
    print("\n--- Answer ---")
    print(result.get("answer"))
    print("\n--- Sources ---")
    for s in result.get("sources", []):
        print(f"- {s['file_name']} ({s['category']})")
except Exception as e:
    print(f"Error: {e}")
