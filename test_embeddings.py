#!/usr/bin/env python3
"""Test script to verify embedding service is working"""

import sys
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_embedder():
    """Test if embedding service can be loaded and used"""
    print("\n" + "="*80)
    print("EMBEDDING SERVICE TEST")
    print("="*80)

    # Test 1: Import
    print("\n[1/4] Testing imports...")
    try:
        from backend.services.vector_store import get_embedder
        print("✅ Import successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

    # Test 2: Load model
    print("\n[2/4] Loading embedding model...")
    try:
        embedder = get_embedder()
        print(f"✅ Model loaded: {embedder.get_sentence_embedding_dimension()} dimensions")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Encode query
    print("\n[3/4] Testing query encoding...")
    try:
        test_query = "What is the leave policy?"
        embedding = embedder.encode(test_query, convert_to_numpy=True)
        print(f"✅ Query encoded successfully")
        print(f"   - Query: '{test_query}'")
        print(f"   - Embedding shape: {embedding.shape}")
        print(f"   - First 5 values: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Encoding failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 4: Batch encoding
    print("\n[4/4] Testing batch encoding...")
    try:
        test_texts = [
            "Leave policy for employees",
            "HR guidelines and procedures",
            "Company benefits and allowances"
        ]
        embeddings = embedder.encode(test_texts, show_progress_bar=False, convert_to_numpy=True)
        print(f"✅ Batch encoding successful")
        print(f"   - Texts encoded: {len(embeddings)}")
        print(f"   - Embedding shape per text: {embeddings[0].shape}")
    except Exception as e:
        print(f"❌ Batch encoding failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED - Embedding service is working!")
    print("="*80 + "\n")
    return True

if __name__ == "__main__":
    success = test_embedder()
    sys.exit(0 if success else 1)
