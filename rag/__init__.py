"""Legal RAG package."""

from rag.pipeline import LegalGenerator, LegalRAG, LegalRetriever

# Kept for compatibility with the original API module.
RAGPipeline = LegalRAG

__all__ = ["LegalGenerator", "LegalRAG", "LegalRetriever", "RAGPipeline"]
