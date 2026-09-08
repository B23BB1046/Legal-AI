"""Application-level legal search service."""

from __future__ import annotations

from typing import Any

from utils.indian_kanoon import IndianKanoonClient, clean_judgment_text
from rag.pipeline import LegalGenerator


class LegalSearchService:
    """Expose a stable response shape to the web and API layers."""

    def __init__(self, client: IndianKanoonClient | None = None) -> None:
        self.client = client or IndianKanoonClient()

    def search_supreme_court(self, query: str, page: int = 0) -> dict[str, Any]:
        """Search Supreme Court judgments using Indian Kanoon."""
        raw = self.client.search(query=query, page=page, court="supremecourt")
        documents = []
        for document in raw.get("docs", []):
            documents.append(
                {
                    "title": clean_judgment_text(str(document.get("title") or "")),
                    "doc_id": document.get("tid"),
                    "source": clean_judgment_text(str(document.get("docsource") or "")),
                    "headline": clean_judgment_text(str(document.get("headline") or "")),
                    "doc_size": document.get("docsize"),
                }
            )
        return {
            "total": raw.get("found", 0),
            "page": page,
            "query": query,
            "documents": documents,
            "attribution": "Powered by Indian Kanoon",
        }

    def ask_about_document(
        self,
        doc_id: str,
        question: str,
        generator: LegalGenerator | None = None,
        language: str = "English",
    ) -> dict[str, Any]:
        """Answer a question using only one Indian Kanoon judgment."""
        if not doc_id.strip() or not question.strip():
            raise ValueError("doc_id and question must not be empty")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")
            
        document = self.client.get_document(doc_id)
        text = str(document.get("doc") or document.get("text") or "").strip()
        if not text:
            raise ValueError("The selected judgment contains no readable text.")
            
        title = document.get("title") or "Selected Supreme Court judgment"
        context = f"CASE: {title}\nDOCUMENT ID: {doc_id}\nSOURCE: Indian Kanoon\nJUDGMENT:\n{text}"
        
        language_instruction = (
            "Answer in simple Hindi using short sentences and explain legal terms in everyday language."
            if language == "Hindi"
            else "Answer in clear English using short sentences."
        )
        
        answer = (generator or LegalGenerator()).generate(
            f"{language_instruction}\n\nQuestion: {question.strip()}",
            context,
        )
        return {
            "question": question.strip(),
            "answer": answer,
            "sources": [{
                "title": title,
                "doc_id": doc_id,
                "source": "Indian Kanoon",
            }],
            "attribution": "Powered by Indian Kanoon",
            "language": language,
        }

    def summarize_document(
        self,
        doc_id: str,
        generator: LegalGenerator | None = None,
        language: str = "English",
    ) -> dict[str, Any]:
        """Return ten concise, source-grounded points from one judgment."""
        if not doc_id.strip():
            raise ValueError("doc_id must not be empty")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")
            
        document = self.client.get_document(doc_id)
        text = str(document.get("doc") or document.get("text") or "").strip()
        if not text:
            raise ValueError("The selected judgment contains no readable text.")
            
        title = document.get("title") or "Selected Supreme Court judgment"
        language_instruction = (
            "Write in simple Hindi using short sentences and explain difficult legal terms."
            if language == "Hindi"
            else "Write in clear English using short sentences."
        )
        
        prompt = f"""Summarize this Indian legal judgment for a legal researcher.
Return exactly 10 numbered points, one concise sentence per point.
{language_instruction}
Use only the judgment text. Do not invent facts, holdings, citations, or conclusions.
Include the most important facts, legal issues, reasoning, holding, and result where available.
Clearly say 'Not stated in the judgment' when a point cannot be supported.

CASE: {title}
DOCUMENT ID: {doc_id}
JUDGMENT:
{text}"""

        summary = (generator or LegalGenerator()).generate("Summarize this judgment in 10 key points.", prompt)
        return {
            "title": title,
            "doc_id": doc_id,
            "summary": summary,
            "source": "Indian Kanoon",
            "attribution": "Powered by Indian Kanoon",
            "language": language,
        }

    def build_case_strategy(
        self,
        document_text: str,
        title: str,
        generator: LegalGenerator | None = None,
        language: str = "English",
    ) -> dict[str, Any]:
        """Build a preliminary strategy grounded in the uploaded document and authorities."""
        text = document_text.strip()
        if not text:
            raise ValueError("The uploaded document contains no readable text.")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")

        query = " ".join(text.replace("\n", " ").split())[:500]
        sources: list[dict[str, Any]] = []
        limitations: list[str] = []
        
        try:
            search_result = self.search_supreme_court(query)
            sources = search_result.get("documents", [])[:5]
        except Exception:
            limitations.append("Indian Kanoon search was unavailable; verify authorities manually.")

        authority_context = "\n".join(
            f"- {item.get('title', 'Unknown case')} (Document ID: {item.get('doc_id', 'Unknown')}): {item.get('headline', '')}"
            for item in sources
        ) or "No Indian Kanoon authorities were available."
        
        language_instruction = (
            "Write in simple Hindi, keeping legal terms with a short English explanation."
            if language == "Hindi"
            else "Write in clear English with concise headings."
        )
        
        prompt = f"""Prepare a preliminary case strategy from this uploaded legal document.
{language_instruction}
This is legal research, not legal advice. Use only the uploaded document and listed Indian Kanoon search results.
Do not invent facts, citations, sections, or holdings. Mark anything uncertain as 'Needs verification'.
Return these headings exactly: Case summary, Legal issues, Petitioner's arguments, Respondent's likely objections, Evidence and gaps, Relevant authorities, Recommended next steps, Risks and uncertainties.

UPLOADED DOCUMENT ({title}):
{text[:12000]}

INDIAN KANOON SEARCH RESULTS:
{authority_context}"""

        try:
            strategy = (generator or LegalGenerator()).generate(
                "Create the preliminary case strategy described above.", prompt
            )
        except Exception:
            limitations.append("LLM strategy generation was unavailable; this result is not a legal opinion.")
            strategy = (
                "Case summary\nThe uploaded document was indexed for document-specific research.\n\n"
                "Legal issues\nNeeds verification by a qualified lawyer from the full document and applicable law.\n\n"
                "Relevant authorities\n" + authority_context
            )
            
        return {
            "title": title,
            "strategy": strategy,
            "sources": sources,
            "limitations": limitations,
            "attribution": "Authorities searched via Indian Kanoon; strategy generated for research assistance.",
            "language": language,
        }

    def adversarial_review(
        self,
        argument: str,
        evidence: str = "",
        language: str = "English",
        generator: LegalGenerator | None = None,
    ) -> dict[str, Any]:
        """Audit an argument symmetrically for support, gaps, and uncertainty."""
        argument = argument.strip()
        evidence = evidence.strip()
        if not argument:
            raise ValueError("argument must not be empty")
        if language not in {"English", "Hindi"}:
            raise ValueError("language must be English or Hindi")

        sources: list[dict[str, Any]] = []
        limitations: list[str] = []
        
        try:
            search_result = self.search_supreme_court(" ".join(argument.split())[:500])
            sources = search_result.get("documents", [])[:6]
        except Exception:
            limitations.append("Indian Kanoon search was unavailable; authorities need manual verification.")
            
        authorities = "\n".join(
            f"- {item.get('title', 'Unknown case')} (Document ID: {item.get('doc_id', 'Unknown')}): {item.get('headline', '')}"
            for item in sources
        ) or "No authorities were retrieved."
        
        language_instruction = (
            "Write in simple Hindi, retaining English legal terms in parentheses."
            if language == "Hindi"
            else "Write in clear English."
        )
        
        prompt = f"""Perform a bias-free adversarial legal review of the argument below.
{language_instruction}
Attack the argument, never the side presenting it. Apply identical tests to supporting and opposing positions.
Steelman the argument before criticizing it. Do not invent facts, citations, paragraphs, provisions, or holdings.
Separate established support, reasonable inference, and unknown facts. Mark unsupported conclusions as Needs verification.
Use the retrieved authorities only as leads unless their actual text is provided.
Return these headings exactly:
Overall assessment
Steelman
Strengths
Weaknesses
Evidence ledger
Strongest counterargument
Factual and legal fit
Current-law check
Critical gaps and unknowns
Recommended next action

ARGUMENT:
{argument}

EVIDENCE PROVIDED:
{evidence or 'No supporting evidence was provided.'}

INDIAN KANOON SEARCH LEADS:
{authorities}

Under Weaknesses, assess separately: evidence, legal authority, precedent treatment, factual mismatch, logical gap, counterargument, current law, and missing information. For each finding state severity (HIGH/MEDIUM/LOW), why it matters, and what would resolve it.
In Evidence ledger, list claims with Evidence for, Evidence against, Evidence missing, and Confidence (HIGH/MEDIUM/LOW).
In Factual and legal fit, compare the argument with the search leads and state similarity and uncertainty rather than declaring relevance without support."""

        try:
            review = (generator or LegalGenerator()).generate(
                "Produce the complete bias-free adversarial legal review.", prompt
            )
        except Exception:
            limitations.append("LLM review generation was unavailable; no legal conclusion was made.")
            review = (
                "Overall assessment\nInsufficient information for a reliable assessment.\n\n"
                "Critical gaps and unknowns\nThe argument and evidence require review against the full authorities."
            )
            
        return {
            "argument": argument,
            "review": review,
            "sources": sources,
            "limitations": limitations,
            "attribution": "Authorities searched via Indian Kanoon; adversarial review is research assistance, not legal advice.",
            "language": language,
        }