"""Manual test for LM Studio embedding API.

This test requires LM Studio to be running locally on port 1234 with an embedding model loaded.

To run this test:
1. Start LM Studio
2. Load an embedding model (e.g., nomic-embed-text-v1.5)
3. Enable the local server (default: http://localhost:1234)
4. Run: python tests/manual_lmstudio_embedding_test.py

This test is NOT run automatically by pytest - it's for manual verification only.
"""

import sys
import json
import requests
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_lmstudio_connection():
    """Test if LM Studio server is accessible."""
    print("=" * 60)
    print("TEST 1: LM Studio Server Connection")
    print("=" * 60)

    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=5)
        print(f"✅ Connection successful (Status: {response.status_code})")

        if response.status_code == 200:
            models = response.json()
            print(f"Available models: {json.dumps(models, indent=2)}")
            return True, models
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False, None

    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection failed: LM Studio not running on localhost:1234")
        print(f"   Error: {e}")
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False, None


def test_lmstudio_embeddings_api():
    """Test LM Studio embeddings API with a simple request."""
    print("\n" + "=" * 60)
    print("TEST 2: LM Studio Embeddings API")
    print("=" * 60)

    test_text = "This is a test sentence for embedding generation."

    payload = {
        "input": test_text,
        "model": "nomic-embed-text",  # Common embedding model in LM Studio
        "encoding_format": "float"
    }

    try:
        response = requests.post(
            "http://localhost:1234/v1/embeddings",
            json=payload,
            timeout=30
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check response structure
            if "data" in data and len(data["data"]) > 0:
                embedding = data["data"][0]["embedding"]
                print(f"✅ Embedding generated successfully")
                print(f"   Model: {data.get('model', 'unknown')}")
                print(f"   Embedding dimension: {len(embedding)}")
                print(f"   First 5 values: {embedding[:5]}")
                print(f"   Usage: {data.get('usage', {})}")
                return True, data
            else:
                print(f"❌ Invalid response structure: {data}")
                return False, None
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None

    except requests.exceptions.Timeout:
        print(f"❌ Request timeout (30s) - model may be loading or too slow")
        return False, None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False, None


def test_openai_client_with_lmstudio():
    """Test using OpenAI Python client with LM Studio base_url."""
    print("\n" + "=" * 60)
    print("TEST 3: OpenAI Client with LM Studio")
    print("=" * 60)

    try:
        import openai

        # Create OpenAI client pointing to LM Studio
        client = openai.OpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio"  # LM Studio doesn't validate API key
        )

        test_text = "This is a test sentence for embedding generation."

        print(f"Creating embedding for: '{test_text}'")

        response = client.embeddings.create(
            model="nomic-embed-text",
            input=test_text,
            encoding_format="float"
        )

        embedding = response.data[0].embedding
        print(f"✅ Embedding generated via OpenAI client")
        print(f"   Model: {response.model}")
        print(f"   Embedding dimension: {len(embedding)}")
        print(f"   First 5 values: {embedding[:5]}")
        print(f"   Usage: {response.usage}")

        return True, response

    except ImportError:
        print(f"❌ OpenAI library not installed")
        return False, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def test_batch_embeddings():
    """Test batch embedding generation."""
    print("\n" + "=" * 60)
    print("TEST 4: Batch Embeddings")
    print("=" * 60)

    try:
        import openai

        client = openai.OpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio"
        )

        test_texts = [
            "First test sentence",
            "Second test sentence",
            "Third test sentence"
        ]

        print(f"Generating embeddings for {len(test_texts)} texts...")

        response = client.embeddings.create(
            model="nomic-embed-text",
            input=test_texts,
            encoding_format="float"
        )

        print(f"✅ Batch embeddings generated")
        print(f"   Number of embeddings: {len(response.data)}")
        print(f"   Embedding dimension: {len(response.data[0].embedding)}")
        print(f"   Usage: {response.usage}")

        return True, response

    except ImportError:
        print(f"❌ OpenAI library not installed")
        return False, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None


def main():
    """Run all manual tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "LM STUDIO EMBEDDING API TEST" + " " * 20 + "║")
    print("╚" + "=" * 58 + "╝")
    print()

    results = []

    # Test 1: Connection
    success, models = test_lmstudio_connection()
    results.append(("Connection", success))

    if not success:
        print("\n❌ Cannot continue tests - LM Studio is not running")
        print("\nTo run this test:")
        print("1. Start LM Studio")
        print("2. Load an embedding model (e.g., nomic-embed-text-v1.5)")
        print("3. Enable the local server")
        print("4. Run this script again")
        sys.exit(1)

    # Test 2: Basic embeddings API
    success, data = test_lmstudio_embeddings_api()
    results.append(("Embeddings API", success))

    # Test 3: OpenAI client compatibility
    success, response = test_openai_client_with_lmstudio()
    results.append(("OpenAI Client", success))

    # Test 4: Batch embeddings
    success, response = test_batch_embeddings()
    results.append(("Batch Embeddings", success))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! LM Studio embeddings are working correctly.")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
