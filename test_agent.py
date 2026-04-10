#!/usr/bin/env python
"""Quick test script for agent endpoints"""
import os
import sys
import requests
import json
from time import sleep

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8000"

def test_imports():
    """Test that all modules can be imported"""
    print("\n" + "="*70)
    print("STEP 1: Testing Module Imports")
    print("="*70)

    tests = [
        ("Config", lambda: __import__("backend.config", fromlist=["settings"])),
        ("Database", lambda: __import__("backend.database.session", fromlist=["get_db"])),
        ("Auth Service", lambda: __import__("backend.services.auth_service", fromlist=["create_user"])),
        ("Agent Brain", lambda: __import__("backend.agents.brain", fromlist=["get_agent"])),
        ("Agent Service", lambda: __import__("backend.services.agent_service", fromlist=["AgentService"])),
    ]

    for name, import_func in tests:
        try:
            import_func()
            print(f"✓ {name} loaded successfully")
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            return False

    return True


def test_api_endpoints():
    """Test API endpoints"""
    print("\n" + "="*70)
    print("STEP 2: Testing API Endpoints")
    print("="*70)

    try:
        # Check if server is running
        print("\nChecking if server is running...")
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running at " + BASE_URL)
        else:
            print(f"✗ Server returned status {response.status_code}")
            print("  Please start the server with: uvicorn backend.main:app --reload")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to {BASE_URL}")
        print("  Please start the server with: uvicorn backend.main:app --reload")
        return False
    except Exception as e:
        print(f"✗ Error checking server: {e}")
        return False

    # Test endpoints
    print("\nTesting endpoints...")

    # Register
    print("\n1. POST /register")
    register_data = {
        "username": "testuser_" + str(int(__import__("time").time())),
        "email": "test@example.com",
        "password": "testpass123",
        "role": "Employee"
    }

    try:
        response = requests.post(f"{BASE_URL}/register", json=register_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            user_id = result.get("user_id")
            print(f"✓ User registered: {user_id}")
        else:
            print(f"✗ Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Login
    print("\n2. POST /login")
    try:
        response = requests.post(f"{BASE_URL}/login", json={
            "username": register_data["username"],
            "password": register_data["password"]
        }, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Login successful")
            print(f"  - User ID: {result.get('user_id')}")
            print(f"  - Role: {result.get('role')}")
        else:
            print(f"✗ Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Get Documents
    print("\n3. GET /documents")
    try:
        response = requests.get(f"{BASE_URL}/documents", params={"user_id": user_id}, timeout=10)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Documents retrieved")
            print(f"  - Total documents: {result.get('total_documents', 0)}")
            print(f"  - User role: {result.get('user_role')}")
            if result.get('documents'):
                print(f"  - First document: {result['documents'][0]['filename']}")
        else:
            print(f"✗ Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Ask Agent
    print("\n4. POST /ask")
    try:
        response = requests.post(f"{BASE_URL}/ask", json={
            "user_id": user_id,
            "question": "What policies are available in the system?"
        }, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                print(f"✓ Agent responded successfully")
                print(f"  - Conversation ID: {result.get('conversation_id')}")
                print(f"  - Message ID: {result.get('message_id')}")
                answer = result.get("answer", "")
                if len(answer) > 100:
                    print(f"  - Answer: {answer[:100]}...")
                else:
                    print(f"  - Answer: {answer}")
                conversation_id = result.get("conversation_id")
            else:
                print(f"✗ Agent error: {result.get('error')}")
                return False
        else:
            print(f"✗ Status {response.status_code}: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print(f"✗ Request timeout (took too long)")
        print("  This might indicate the Groq API is slow or unreachable")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

    # Get Conversation
    if 'conversation_id' in locals():
        print(f"\n5. GET /conversation/{conversation_id}")
        try:
            response = requests.get(
                f"{BASE_URL}/conversation/{conversation_id}",
                params={"user_id": user_id},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✓ Conversation retrieved")
                print(f"  - Total messages: {result.get('total_messages', 0)}")
                if result.get('messages'):
                    msg = result['messages'][0]
                    print(f"  - First message Q: {msg['question']}")
            else:
                print(f"✗ Status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("AGENT TESTING SUITE")
    print("="*70)

    # Test imports
    if not test_imports():
        print("\n✗ Import tests failed")
        sys.exit(1)

    # Test API
    if not test_api_endpoints():
        print("\n✗ API tests failed")
        sys.exit(1)

    print("\n" + "="*70)
    print("✓ ALL TESTS PASSED!")
    print("="*70)
    print("\nNext steps:")
    print("1. Implement PDF embedding pipeline (backend/services/processor.py)")
    print("2. Generate embeddings for documents in /storage/policies/")
    print("3. Update retrieval tool to use semantic search with pgvector")
    print("\nFor more details, see TESTING.md")
