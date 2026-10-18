from typing import List, Dict, Any, Optional
from backend.vector_store import get_vector_store

# Default configuration
DEFAULT_TOP_K = 3
DEFAULT_SCORE_THRESHOLD = 0.10  # Minimum similarity score required to be considered relevant


class RetrievalService:
    def __init__(self, score_threshold: float = DEFAULT_SCORE_THRESHOLD):
        self.vector_store = get_vector_store()
        self.default_score_threshold = score_threshold

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: Optional[float] = None,
        product_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves relevant document chunks from the FAISS vector index for a user question.
        
        Args:
            query: The user's question or search phrase.
            top_k: Maximum number of chunks to return (configurable limit).
            score_threshold: Minimum similarity score (filters out irrelevant matches).
            product_filter: Optional product name or document filter.
            
        Returns:
            Dict containing:
                - query: str
                - chunks: List[Dict] with chunk text, score, and metadata
                - has_relevant_context: bool (True if at least one chunk passed threshold)
                - top_score: float
                - citation_sources: List[str] formatted source tags
        """
        cleaned_query = query.strip()
        threshold = score_threshold if score_threshold is not None else self.default_score_threshold
        
        if not cleaned_query:
            return {
                "query": query,
                "chunks": [],
                "results_count": 0,
                "has_relevant_context": False,
                "top_score": 0.0,
                "citation_sources": []
            }
            
        # Perform FAISS similarity search
        raw_matches = self.vector_store.search(
            query=cleaned_query,
            top_k=top_k,
            product_filter=product_filter
        )
        
        # Filter matches by relevance threshold
        relevant_chunks: List[Dict[str, Any]] = []
        sources: List[str] = []
        seen_sources = set()
        
        for item in raw_matches:
            score = item.get("similarity_score", 0.0)
            if score >= threshold:
                chunk_data = {
                    "chunk_id": item.get("chunk_id", ""),
                    "product_name": item.get("product_name", ""),
                    "section": item.get("section", ""),
                    "source_file": item.get("source_file", ""),
                    "similarity_score": round(score, 4),
                    "text": item.get("text", "")
                }
                relevant_chunks.append(chunk_data)
                
                # Format a clean citation string
                source_tag = f"{item.get('product_name', 'Product')} > {item.get('section', 'General')} ({item.get('source_file', '')})"
                if source_tag not in seen_sources:
                    seen_sources.add(source_tag)
                    sources.append(source_tag)
                    
        top_score = relevant_chunks[0]["similarity_score"] if relevant_chunks else 0.0
        
        # Consolidate sibling chunks from top matching section so multi-step procedures are never fragmented
        if relevant_chunks:
            top_sections = {(c["source_file"], c["section"]) for c in relevant_chunks[:2]}
            included_ids = {c["chunk_id"] for c in relevant_chunks}
            for meta in self.vector_store.metadata:
                sec_key = (meta.get("source_file", ""), meta.get("section", ""))
                cid = meta.get("chunk_id", "")
                if sec_key in top_sections and cid not in included_ids:
                    relevant_chunks.append({
                        "chunk_id": cid,
                        "product_name": meta.get("product_name", ""),
                        "section": meta.get("section", ""),
                        "source_file": meta.get("source_file", ""),
                        "similarity_score": round(top_score * 0.9, 4),
                        "text": meta.get("text", "")
                    })
                    included_ids.add(cid)
        
        return {
            "query": cleaned_query,
            "chunks": relevant_chunks,
            "results_count": len(relevant_chunks),
            "has_relevant_context": len(relevant_chunks) > 0,
            "top_score": top_score,
            "citation_sources": sources
        }


# Singleton instance for simple reuse
_retrieval_service = RetrievalService()

def get_retrieval_service() -> RetrievalService:
    return _retrieval_service
