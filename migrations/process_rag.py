import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

# Ensure env vars are loaded
import config 

from services.rag_service import SemanticSearchEngine

def main():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        return

    print("Initializing Semantic Search Engine...")
    engine = SemanticSearchEngine(api_key=api_key)
    
    print("Starting RAG processing...")
    engine.process_and_embed_publications()
    
    print("Done.")
    engine.close()

if __name__ == "__main__":
    main()
