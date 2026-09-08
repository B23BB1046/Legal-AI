"""Shared agent state, LLM access, and parsing helpers."""

from __future__ import annotations

import json
import re
from typing import Any, TypedDict

from utils.config import GROQ_API_KEY, MODEL_NAME


class LegalState(TypedDict, total=False):
    user_query: str
    legal_topic: str
    legal_issues: list[str]
    search_queries: list[str]
    search_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    precedents: list[dict[str, Any]]
    verification_results: list[dict[str, Any]]
    final_answer: str
    errors: list[str]


class LegalLLM:
    def __init__(self, api_key: str | None = GROQ_API_KEY, model: str = MODEL_NAME) -> None:
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        if not self.api_key:
            raise RuntimeError("Set GROQ_API_KEY in .env before running the agentic workflow.")
        if self._client is None:
            from groq import Groq

            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content or ""
        return re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()


def parse_json(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removeprefix("json").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        return fallback
    return value if isinstance(value, dict) else fallback


def add_error(state: dict, message: str) -> None:
    state.setdefault("errors", []).append(message)
