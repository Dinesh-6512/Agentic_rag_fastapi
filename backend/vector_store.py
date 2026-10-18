import os
import json
import math
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import faiss
from dotenv import load_dotenv

from backend.ingestion import load_processed_chunks, DEFAULT_DOCS_DIR

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

DEFAULT_INDEX_DIR = Path(__file__).parent / "faiss_index"
INDEX_FILE_NAME = "index.faiss"
METADATA_FILE_NAME = "metadata.json"
EMBEDDING_DIM = 768


# --- EMBEDDING PROVIDER (Gemini API with Deterministic Local Fallback) ---

STOP_WORDS = {
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", 
    "but", "by", "can", "did", "do", "does", "doing", "down", "during", "each", "few", 
    "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", 
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", 
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", 
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours", 
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such", 
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", 
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up", 
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", 
    "whom", "why", "will", "with", "you", "your", "yours", "yourself", "yourselves"
}

def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ations", "ation", "ments", "ment", "ingly", "ings", "ing", "ions", "ion", "ers", "er", "ies", "es", "ed", "ly", "s", "e"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w

def _get_local_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """
    Generates a deterministic semantic feature vector using stemmed character and word n-grams
    normalized to unit L2 norm. Filters stop words so unrelated queries don't artificially match.
    """
    vec = np.zeros(dim, dtype=np.float32)
    raw_words = [re.sub(r"[^\w]", "", w) for w in text.lower().split()]
    stemmed_words = [_stem(w) for w in raw_words if len(w) > 2 and w not in STOP_WORDS]
    if not stemmed_words:
        stemmed_words = [_stem(w) for w in raw_words if w]
        
    if not stemmed_words:
        vec[0] = 1.0
        return vec
    
    # Word-level features with TF weighting
    word_counts: Dict[str, int] = {}
    for w in stemmed_words:
        word_counts[w] = word_counts.get(w, 0) + 1
        
    for w, count in word_counts.items():
        weight = 1.0 + math.log(count + 1)
        h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += weight
        
    # Word bigram features
    for i in range(len(stemmed_words) - 1):
        bigram = f"{stemmed_words[i]}_{stemmed_words[i+1]}"
        bh = int(hashlib.sha256(bigram.encode("utf-8")).hexdigest(), 16)
        b_idx = bh % dim
        vec[b_idx] += 1.8

    # Normalize vector to unit length (L2 norm) for cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    else:
        vec[0] = 1.0
        
    return vec


def get_embedding(text: str, dim: int = EMBEDDING_DIM) -> np.ndarray:
    """
    Computes an embedding vector for text.
    Uses Google Gemini text-embedding-004 if GEMINI_API_KEY is present;
    otherwise uses the robust deterministic local embedding.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            if hasattr(result, "embedding") and hasattr(result.embedding, "values"):
                vec = np.array(result.embedding.values, dtype=np.float32)
                norm = np.linalg.norm(vec)
                return vec / norm if norm > 0 else vec
        except Exception as e:
            # Fall back to local embedding gracefully if API call fails
            pass

    return _get_local_embedding(text, dim=dim)


# --- FAISS VECTOR STORE MANAGER ---

class FaissVectorStore:
    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []
        
    def build_from_chunks(self, chunks: Optional[List[Dict[str, Any]]] = None) -> int:
        """
        Builds the FAISS index from document chunks and saves both index and metadata.
        """
        if chunks is None:
            chunks = load_processed_chunks()
            
        if not chunks:
            print("No chunks provided or found to index.")
            return 0
            
        print(f"Generating embeddings for {len(chunks)} chunks...")
        vectors: List[np.ndarray] = []
        metadata_list: List[Dict[str, Any]] = []
        
        for idx, chunk in enumerate(chunks):
            text = chunk["text"]
            prod = chunk.get("metadata", {}).get("product_name", "")
            sec = chunk.get("metadata", {}).get("section", "")
            embed_text = f"{prod} {sec} {sec}: {text}"
            vec = get_embedding(embed_text, dim=EMBEDDING_DIM)
            vectors.append(vec)
            
            meta_record = {
                "vector_id": idx,
                "chunk_id": chunk.get("chunk_id", f"chunk_{idx}"),
                "chunk_index": chunk.get("chunk_index", idx),
                "text": text,
                "document_name": chunk.get("metadata", {}).get("document_name", ""),
                "source_file": chunk.get("metadata", {}).get("source_file", ""),
                "product_name": chunk.get("metadata", {}).get("product_name", ""),
                "section": chunk.get("metadata", {}).get("section", ""),
                "char_count": chunk.get("metadata", {}).get("char_count", len(text)),
            }
            metadata_list.append(meta_record)
            
        vector_matrix = np.vstack(vectors).astype(np.float32)
        
        # We use IndexFlatIP (Inner Product) with unit-normalized vectors = Cosine Similarity
        index = faiss.IndexFlatIP(EMBEDDING_DIM)
        index.add(vector_matrix)
        
        # Save to disk in dedicated local folder
        self.index_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.index_dir / INDEX_FILE_NAME
        metadata_path = self.index_dir / METADATA_FILE_NAME
        
        faiss.write_index(index, str(index_path))
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, indent=2, ensure_ascii=False)
            
        self.index = index
        self.metadata = metadata_list
        print(f"FAISS index built successfully: {index.ntotal} vectors saved to {index_path}")
        return index.ntotal
        
    def load(self) -> bool:
        """
        Loads the FAISS index and metadata from disk.
        """
        index_path = self.index_dir / INDEX_FILE_NAME
        metadata_path = self.index_dir / METADATA_FILE_NAME
        
        if not index_path.exists() or not metadata_path.exists():
            return False
            
        self.index = faiss.read_index(str(index_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)
            
        return True
        
    def ensure_loaded(self) -> bool:
        """
        Loads the index if available; otherwise builds it from document chunks.
        """
        if self.index is not None and self.metadata:
            return True
            
        if self.load():
            return True
            
        count = self.build_from_chunks()
        return count > 0
        
    def search(
        self, 
        query: str, 
        top_k: int = 3, 
        product_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs vector similarity search against the FAISS index.
        Returns top_k matching chunks with similarity score and metadata.
        """
        if not self.ensure_loaded() or self.index is None:
            return []
            
        query_vec = get_embedding(query, dim=EMBEDDING_DIM).reshape(1, -1).astype(np.float32)
        
        # Retrieve more candidates if filtering by product
        fetch_k = top_k * 3 if product_filter else top_k
        fetch_k = min(fetch_k, self.index.ntotal)
        
        scores, indices = self.index.search(query_vec, fetch_k)
        
        results: List[Dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self.metadata):
                continue
                
            item = self.metadata[idx].copy()
            item["similarity_score"] = float(score)
            
            # Apply product filter if specified
            if product_filter:
                p_name = item.get("product_name", "").lower()
                doc_name = item.get("document_name", "").lower()
                filt = product_filter.lower()
                if filt not in p_name and filt not in doc_name:
                    continue
                    
            results.append(item)
            if len(results) >= top_k:
                break
                
        return results


# Global singleton store instance for easy import across backend
_vector_store = FaissVectorStore()

def get_vector_store() -> FaissVectorStore:
    return _vector_store


if __name__ == "__main__":
    store = FaissVectorStore()
    print("Building FAISS index for approved product manuals...")
    total = store.build_from_chunks()
    print(f"Indexing complete! Total indexed items: {total}")
    
    # Run a test query
    test_query = "How do I pair the wireless mouse to my laptop using bluetooth?"
    print(f"\n--- Testing Search for Query: '{test_query}' ---")
    matches = store.search(test_query, top_k=2)
    for i, m in enumerate(matches, 1):
        print(f"\nMatch {i} (Score: {m['similarity_score']:.4f}):")
        print(f"Product: {m['product_name']} | Section: {m['section']} ({m['source_file']})")
        print(f"Text snippet:\n{m['text'][:160]}...")
