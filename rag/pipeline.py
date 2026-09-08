"""Core document parsing, retrieval, storage, and grounded generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from utils.config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL, GROQ_API_KEY, MODEL_NAME, TOP_K


def clean_text(text: str) -> str:
    """Clean and normalize whitespace and formatting characters in text."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[-_=]{3,}", " ", text)).strip()


def create_chunks(text: str, chunk_size: int = 1200, chunk_overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks with sentence or paragraph boundary awareness."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be between zero and chunk_size")
    if not text.strip():
        return []
        
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


@dataclass
class LegalDocument:
    """Representation of an individual legal judgment or document."""
    doc_id: str
    title: str
    text: str
    source: str = "Indian Kanoon"
    court: str | None = None
    date: str | None = None
    citation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def load_judgment(path: str | Path) -> LegalDocument:
    """Load and parse a judgment JSON payload from disk."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
        
    metadata = payload.get("metadata") or {}
    return LegalDocument(
        doc_id=str(payload.get("tid") or payload.get("docid") or file_path.stem),
        title=str(payload.get("title") or payload.get("case_name") or "Unknown Case"),
        text=str(payload.get("doc") or payload.get("text") or ""),
        source=str(payload.get("source") or "Indian Kanoon"),
        court=payload.get("court"),
        date=payload.get("date"),
        citation=payload.get("citation"),
        metadata=metadata if isinstance(metadata, dict) else {},
    )


class EmbeddingModel:
    """Wrapper for generating text embeddings using SentenceTransformers."""

    def __init__(self, model_name: str = EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the SentenceTransformer embedding model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: Iterable[str]):
        """Encode a collection of texts into normalized embeddings."""
        values = list(texts)
        if not values:
            return []
        return self.model.encode(values, normalize_embeddings=True, show_progress_bar=len(values) > 10)


class VectorStore:
    """Persistent vector database interface using ChromaDB."""

    def __init__(self, path: str | Path = CHROMA_PATH, collection_name: str = COLLECTION_NAME) -> None:
        self.path = str(path)
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        """Lazy-load the persistent Chroma collection."""
        if self._collection is None:
            import chromadb
            Path(self.path).mkdir(parents=True, exist_ok=True)
            self._collection = chromadb.PersistentClient(path=self.path).get_or_create_collection(
                name=self.collection_name
            )
        return self._collection

    def add_documents(
        self,
        documents: Iterable[str],
        embeddings: Any,
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        """Upsert documents, vectors, and metadata into the vector store."""
        values = list(documents)
        if values:
            vectors = embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)
            self.collection.upsert(documents=values, embeddings=vectors, metadatas=metadatas, ids=ids)

    def search(self, embedding: Any, top_k: int = 5, where: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a vector similarity query."""
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
            
        query = {
            "query_embeddings": [embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)],
            "n_results": top_k,
        }
        if where:
            query["where"] = where
        return self.collection.query(**query)


class LegalRetriever:
    """Retrieves relevant legal passages based on semantic similarity search."""

    def __init__(self, embedding_model: EmbeddingModel | None = None, vector_store: VectorStore | None = None) -> None:
        self.embedding_model = embedding_model or EmbeddingModel()
        self.vector_store = vector_store or VectorStore()

    def retrieve(self, query: str, top_k: int = TOP_K, document_id: str | None = None) -> list[dict]:
        """Retrieve top matching passages for a given query string."""
        if not query.strip():
            raise ValueError("query must not be empty")
            
        query_embedding = self.embedding_model.encode([query])[0]
        where_clause = {"doc_id": document_id} if document_id else None
        
        result = self.vector_store.search(query_embedding, top_k, where=where_clause)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        
        return [
            {
                "text": text,
                "metadata": metadata or {},
                "distance": distances[index] if index < len(distances) else None,
            }
            for index, (text, metadata) in enumerate(zip(documents, metadatas))
        ]


class LegalGenerator:
    """Generates grounded responses via the Groq client API."""

    def __init__(self, api_key: str | None = GROQ_API_KEY, model: str = MODEL_NAME) -> None:
        self.api_key = api_key
        self.model_name = model
        self._client = None

    @property
    def client(self):
        """Lazy-load the Groq client instance."""
        if not self.api_key:
            raise RuntimeError("Set GROQ_API_KEY in .env before asking the Legal RAG assistant.")
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, question: str, context: str) -> str:
        """Send prompt and legal context to Groq to generate a grounded legal response."""
        prompt = f"""You are an Indian Supreme Court legal research assistant.
Answer only from the provided legal sources. Do not invent cases, citations, provisions, facts, or holdings.
If the sources are insufficient, say so clearly. This is legal research, not legal advice.

USER QUESTION:
{question}

LEGAL SOURCES:
{context}

Give a concise answer with legal reasoning. Cite the source case and document ID after each important proposition."""

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content or "The model returned no answer."
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


class LegalRAG:
    """High-level orchestrator connecting retrieval and generation pipelines."""

    def __init__(self, retriever: LegalRetriever | None = None, generator: LegalGenerator | None = None) -> None:
        self.retriever = retriever or LegalRetriever()
        self.generator = generator or LegalGenerator()

    def ask(self, question: str, top_k: int = 5, document_id: str | None = None, language: str = "English") -> dict:
        """Answer a question using retrieved passages and structured formatting constraints."""
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")
            
        passages = (
            self.retriever.retrieve(question, top_k=top_k, document_id=document_id)
            if document_id
            else self.retriever.retrieve(question, top_k=top_k)
        )
        
        if not passages:
            scope = f" for document '{document_id}'" if document_id else ""
            return {"question": question, "answer": f"No indexed passages were found{scope}.", "sources": []}
            
        context_parts = []
        sources = []
        for passage in passages:
            metadata = passage["metadata"]
            context_parts.append(
                "CASE: {title}\nDOCUMENT ID: {doc_id}\nSOURCE: {source}\nPASSAGE:\n{text}".format(
                    title=metadata.get("title", "Unknown Case"),
                    doc_id=metadata.get("doc_id", "Unknown"),
                    source=metadata.get("source", "Indian Kanoon"),
                    text=passage["text"],
                )
            )
            sources.append(metadata)
            
        instruction = (
            "Answer in simple Hindi and keep important legal terms in English in parentheses."
            if language == "Hindi"
            else "Answer in clear, simple English."
        )
        
        structured_question = f"""{instruction}
Answer using exactly these headings:
### Answer
### Legal basis in the document
### Evidence from the document
### Uncertainty or missing information
### Practical next steps
Use only the supplied passages. Do not invent facts, provisions, citations, or legal conclusions.

User question: {question}"""

        answer_text = self.generator.generate(structured_question, "\n\n".join(context_parts))
        return {
            "question": question,
            "answer": answer_text,
            "sources": sources,
            "language": language,
        }

    def answer(self, question: str) -> dict:
        """Convenience method to query the RAG system in English with default parameters."""
        return self.ask(question)