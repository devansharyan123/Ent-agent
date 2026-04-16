import sys
import os
from unittest.mock import MagicMock, patch

# Set up environment for imports
sys.path.append(os.getcwd())

# Mock DB and tools
db = MagicMock()
question = "What is leave policy?"
role = "employee"
conversation_id = "123e4567-e89b-12d3-a456-426614174000"

with patch('backend.services.conversation_service.policy_retrieval_tool') as mock_rag:
    with patch('backend.agents.tools.recommendation_tool.recommendation_tool') as mock_rec:
        from backend.services.conversation_service import send_message
        
        mock_rag.return_value = {"answer": "You have 20 days of leave.", "sources": []}
        mock_rec.return_value = {"answer": "Would you like to know more about holiday policy?\nWould you like to know more about sick leave?", "sources": []}
        
        msg = send_message(db, conversation_id, question, role, tool="rag")
        print("Final Answer:")
        print(msg.answer)

