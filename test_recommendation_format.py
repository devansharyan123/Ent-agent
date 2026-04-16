import sys
import os
from unittest.mock import MagicMock

# Set up environment for imports
sys.path.append(os.getcwd())

# Mock ChatGroq to test prompt construction or basic execution if API key works
from backend.agents.tools.recommendation_tool import _generate_recommendation

chunks = [
    {"file_name": "leave_policy.pdf", "chunk_text": "Sick leave is 10 days per year."},
    {"file_name": "hr_handbook.pdf", "chunk_text": "Resignation requires 2 weeks notice."}
]
query = "Tell me about leave"

print("Testing _generate_recommendation output format...")
try:
    # This will attempt an actual LLM call if API key is in env
    res = _generate_recommendation(query, chunks)
    print("Result:")
    print(res)
except Exception as e:
    print(f"Error (likely due to missing API key in this shell): {e}")

