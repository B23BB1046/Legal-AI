"""Extract and analyze uploaded legal documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rag.pipeline import create_chunks, clean_text, EmbeddingModel, VectorStore


class DocumentProcessor:
    """Read PDF/TXT files and optionally add their chunks to the RAG index."""

    allowed_suffixes = {".pdf", ".txt", ".md"}

    def extract_text(self, file_path: str | Path) -> str:
        """Extract raw text from PDF, TXT, or Markdown files."""
        path = Path(file_path)
        if path.suffix.lower() not in self.allowed_suffixes:
            raise ValueError("Only PDF, TXT, and Markdown files are supported.")
        if path.suffix.lower() == ".pdf":
            try:
                import fitz
            except ImportError as exc:
                raise RuntimeError("Install pymupdf to process PDF documents.") from exc
            with fitz.open(path) as document:
                return "\n".join(page.get_text() for page in document)
        return path.read_text(encoding="utf-8", errors="ignore")

    def analyze(self, text: str) -> dict[str, Any]:
        """Perform lightweight metadata extraction and keyword auditing."""
        normalized = clean_text(text)
        sections = sorted(
            set(re.findall(r"\b(?:Section|Sec\.?|Article)\s+[\dA-Za-z()/-]+", normalized, re.IGNORECASE)),
            key=str.lower,
        )
        issue_terms = {
            "bail": "bail",
            "anticipatory bail": "anticipatory bail",
            "fundamental rights": "fundamental rights",
            "Article 21": "right to life and personal liberty",
            "privacy": "privacy",
            "murder": "murder",
            "custody": "custody",
        }
        lowered = normalized.lower()
        issues = [label for term, label in issue_terms.items() if term.lower() in lowered]
        return {
            "characters": len(normalized),
            "words": len(normalized.split()),
            "sections": sections,
            "issues": issues,
            "preview": normalized[:500],
        }

    def process(self, file_path: str | Path) -> list[str]:
        """Extract, clean, and chunk text from a file path."""
        return create_chunks(clean_text(self.extract_text(file_path)))

    def index(self, file_path: str | Path) -> dict[str, Any]:
        """Process document chunks, generate embeddings, and add them to the VectorStore."""
        path = Path(file_path)
        chunks = self.process(path)
        if not chunks:
            return {"chunks": 0, "analysis": self.analyze("")}
            
        document_id = path.stem
        metadata = self.analyze(self.extract_text(path))
        metadatas = [
            {
                "doc_id": document_id,
                "title": path.name,
                "source": "Uploaded document",
                "chunk_id": index,
                "document_issue": ", ".join(metadata["issues"]),
            }
            for index in range(len(chunks))
        ]
        
        embeddings = EmbeddingModel().encode(chunks)
        VectorStore().add_documents(
            chunks,
            embeddings,
            metadatas,
            [f"{document_id}_{index}" for index in range(len(chunks))],
        )
        return {"chunks": len(chunks), "analysis": metadata}