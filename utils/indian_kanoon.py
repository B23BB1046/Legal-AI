"""Small client for the Indian Kanoon API."""

from __future__ import annotations

import html
import re
from typing import Any

import requests

from utils.config import INDIAN_KANOON_API_TOKEN

BASE_URL = "https://api.indiankanoon.org"


def clean_judgment_text(value: str) -> str:
    """Convert Indian Kanoon HTML fragments into readable plain text."""
    if not value:
        return ""
    value = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<\s*br\s*/?\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value).replace("\u200b", " ").replace("\ufeff", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n+", "\n\n", value)
    return value.strip()


class IndianKanoonConfigurationError(RuntimeError):
    """Raised when the API is used without a configured token."""


class IndianKanoonClient:
    """Client for Indian Kanoon search and document endpoints."""

    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self.token = token or INDIAN_KANOON_API_TOKEN
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise IndianKanoonConfigurationError(
                "Set INDIAN_KANOON_API_TOKEN in .env before using Indian Kanoon."
            )
        return {
            "Authorization": f"Token {self.token}",
            "Accept": "application/json",
        }

    def search(
        self,
        query: str,
        page: int = 0,
        court: str = "supremecourt",
    ) -> dict[str, Any]:
        """Search judgments, restricted to the requested court type."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if page < 0:
            raise ValueError("page must be zero or greater")

        response = requests.post(
            f"{BASE_URL}/search/",
            headers=self._headers(),
            data={"formInput": query, "pagenum": page, "doctypes": court},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_document(self, doc_id: str) -> dict[str, Any]:
        """Retrieve the full judgment identified by ``doc_id``."""
        response = requests.post(
            f"{BASE_URL}/doc/{doc_id}/",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        document = response.json()
        if isinstance(document, dict) and isinstance(document.get("doc"), str):
            document["doc"] = clean_judgment_text(document["doc"])
        return document

    def get_metadata(self, doc_id: str) -> dict[str, Any]:
        """Retrieve metadata for a judgment."""
        response = requests.get(
            f"{BASE_URL}/docmeta/{doc_id}/",
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_fragment(self, doc_id: str, query: str) -> dict[str, Any]:
        """Retrieve the relevant fragment of a judgment for a query."""
        if not query.strip():
            raise ValueError("query must not be empty")
        response = requests.get(
            f"{BASE_URL}/docfragment/{doc_id}/",
            headers=self._headers(),
            params={"formInput": query},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
