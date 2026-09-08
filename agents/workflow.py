"""Complete multi-step legal research workflow."""

from __future__ import annotations

import re

from agents.core import LegalLLM, LegalState, add_error, parse_json
from utils.config import AGENT_MAX_EVIDENCE, AGENT_MAX_PRECEDENTS, AGENT_MAX_QUERIES, AGENT_TOP_K
from legal_search import LegalSearchService
from rag.pipeline import LegalRetriever


def supervisor_agent(state: LegalState, llm: LegalLLM | None = None) -> LegalState:
    """Analyze the user query and plan legal issues and search strategies."""
    query = state.get("user_query", "").strip()
    if not query:
        add_error(state, "Supervisor received an empty user query.")
        return state
        
    prompt = f"""You are the supervisor of an Indian Supreme Court legal research workflow.
Analyze this user question: {query}
Return only JSON with string legal_topic, array legal_issues, and array search_queries.
Keep the plan focused and use no more than {AGENT_MAX_QUERIES} search queries."""

    try:
        data = parse_json(
            (llm or LegalLLM()).generate(prompt),
            {"legal_topic": query, "legal_issues": [query], "search_queries": [query]},
        )
    except Exception as exc:
        add_error(state, f"Supervisor error: {exc}")
        data = {"legal_topic": query, "legal_issues": [query], "search_queries": [query]}
        
    state["legal_topic"] = str(data.get("legal_topic") or query)
    state["legal_issues"] = [str(item) for item in data.get("legal_issues", [query])][:8]
    state["search_queries"] = [str(item) for item in data.get("search_queries", [query])][:4]
    return state


def _terms(text: str) -> set[str]:
    """Extract significant lower-case terms for lexical scoring."""
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _rerank(query: str, results: list[dict]) -> list[dict]:
    """Rerank retrieved legal passages based on a hybrid lexical and semantic score."""
    query_terms = _terms(query)
    for result in results:
        metadata = result.get("metadata", {})
        result_terms = _terms(f"{result.get('text', '')} {metadata.get('title', '')} {metadata.get('headline', '')}")
        lexical_score = len(query_terms & result_terms) / max(len(query_terms), 1)
        distance = result.get("distance")
        semantic_score = 1 / (1 + max(float(distance), 0)) if distance is not None else 0
        source_boost = 0.05 if result.get("source") == "Indian Kanoon" else 0
        result["score"] = round(lexical_score * 0.65 + semantic_score * 0.3 + source_boost, 4)
    return sorted(results, key=lambda item: item["score"], reverse=True)


def search_agent(
    state: LegalState,
    retriever: LegalRetriever | None = None,
    legal_search: LegalSearchService | None = None,
) -> LegalState:
    """Retrieve relevant passages from ChromaDB and Indian Kanoon based on search queries."""
    searcher = retriever or LegalRetriever()
    kanoon = legal_search or LegalSearchService()
    queries = (state.get("search_queries") or [state.get("user_query", "")])[:AGENT_MAX_QUERIES]
    
    results, seen = [], set()
    for query in queries:
        try:
            for item in searcher.retrieve(query, top_k=AGENT_TOP_K):
                metadata = item.get("metadata", {})
                key = (metadata.get("doc_id"), metadata.get("chunk_id"), item.get("text"))
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "query": query,
                        "text": item.get("text", ""),
                        "metadata": metadata,
                        "distance": item.get("distance"),
                        "source": "ChromaDB",
                    })
        except Exception as exc:
            add_error(state, f"ChromaDB search error for '{query}': {exc}")
            
        try:
            response = kanoon.search_supreme_court(query)
            for document in response.get("documents", [])[:AGENT_TOP_K]:
                doc_id = document.get("doc_id")
                text = document.get("headline") or document.get("title") or ""
                title = document.get("title") or "Unknown Case"
                client = getattr(kanoon, "client", None)
                
                if doc_id and client is not None:
                    try:
                        full_document = client.get_document(str(doc_id))
                        text = str(full_document.get("doc") or full_document.get("text") or text).strip()
                        title = full_document.get("title") or title
                    except Exception as exc:
                        add_error(state, f"Judgment retrieval error for '{doc_id}': {exc}")
                        
                key = (doc_id, None, text)
                if key not in seen and text:
                    seen.add(key)
                    results.append({
                        "query": query,
                        "text": text,
                        "metadata": {
                            "doc_id": doc_id,
                            "title": title,
                            "source": document.get("source") or "Indian Kanoon",
                            "headline": document.get("headline") or "",
                        },
                        "source": "Indian Kanoon",
                    })
        except Exception as exc:
            add_error(state, f"Indian Kanoon search error for '{query}': {exc}")
            
    state["search_results"] = _rerank(state.get("user_query", ""), results)
    return state


def evidence_agent(state: LegalState, llm: LegalLLM | None = None) -> LegalState:
    """Analyze retrieved search results to verify relevance and extract legal propositions."""
    analyzer = llm or LegalLLM()
    evidence = []
    
    for result in state.get("search_results", [])[:AGENT_MAX_EVIDENCE]:
        text = result.get("text", "")
        prompt = f"""You are a legal evidence analyst.
User question: {state.get('user_query', '')}
Passage: {text}
Return only JSON: {{"relevant": true, "reason": "...", "legal_proposition": "...", "strength": 0.0}}
Set strength from 0 to 1 and mark relevant only when the passage supports the question."""

        try:
            analysis = parse_json(
                analyzer.generate(prompt),
                {"relevant": True, "reason": "Fallback review", "legal_proposition": text, "strength": 0.5},
            )
        except Exception as exc:
            add_error(state, f"Evidence error: {exc}")
            analysis = {"relevant": False, "reason": "Evidence analysis failed", "legal_proposition": "", "strength": 0}
            
        if analysis.get("relevant"):
            evidence.append({
                "text": text,
                "metadata": result.get("metadata", {}),
                "reason": str(analysis.get("reason", "")),
                "legal_proposition": str(analysis.get("legal_proposition", text)),
                "strength": max(0.0, min(1.0, float(analysis.get("strength", 0.5)))),
            })
            
    state["evidence"] = evidence
    return state


def precedent_agent(state: LegalState, llm: LegalLLM | None = None) -> LegalState:
    """Extract legal principles and related case citations from validated evidence."""
    analyzer = llm or LegalLLM()
    precedents = []
    
    for item in state.get("evidence", [])[:AGENT_MAX_PRECEDENTS]:
        prompt = f"""You are an Indian Supreme Court precedent analyst.
Analyze this passage: {item.get('text', '')}
Return only JSON with case_name, legal_principle, and related_cases.
related_cases must be an array of {{"case": "...", "relationship": "followed, distinguished, overruled, relied upon, or criticized"}}."""

        try:
            analysis = parse_json(
                analyzer.generate(prompt),
                {
                    "case_name": item.get("metadata", {}).get("title", "Unknown Case"),
                    "legal_principle": item.get("legal_proposition", ""),
                    "related_cases": [],
                },
            )
        except Exception as exc:
            add_error(state, f"Precedent error: {exc}")
            analysis = {
                "case_name": item.get("metadata", {}).get("title", "Unknown Case"),
                "legal_principle": "",
                "related_cases": [],
            }
            
        precedents.append({"source": item, "analysis": analysis})
        
    state["precedents"] = precedents
    return state


def verification_agent(state: LegalState, llm: LegalLLM | None = None) -> LegalState:
    """Verify extracted legal claims against their source passages."""
    verifier = llm or LegalLLM()
    results = []
    
    for precedent in state.get("precedents", [])[:AGENT_MAX_PRECEDENTS]:
        source = precedent.get("source", {})
        claim = precedent.get("analysis", {}).get("legal_principle", "")
        prompt = f"""You verify legal citations without assuming a claim is true.
Claim: {claim}
Source passage: {source.get('text', '')}
Return only JSON: {{"supported": true, "confidence": 0.0, "explanation": "..."}}"""

        try:
            result = parse_json(
                verifier.generate(prompt),
                {"supported": False, "confidence": 0.0, "explanation": "Verification response could not be parsed."},
            )
        except Exception as exc:
            add_error(state, f"Verification error: {exc}")
            result = {"supported": False, "confidence": 0.0, "explanation": "Verification failed."}
            
        results.append({"claim": claim, "result": result, "source": source.get("metadata", {})})
        
    state["verification_results"] = results
    return state


def answer_agent(state: LegalState, llm: LegalLLM | None = None) -> LegalState:
    """Synthesize the final grounded legal research report from verified evidence and claims."""
    evidence_text = []
    for item in state.get("evidence", []):
        metadata = item.get("metadata", {})
        evidence_text.append(
            "CASE: {title}\nDOCUMENT ID: {doc_id}\nSOURCE: {source}\nPASSAGE: {text}\nPROPOSITION: {proposition}".format(
                title=metadata.get("title", "Unknown Case"),
                doc_id=metadata.get("doc_id", "Unknown"),
                source=metadata.get("source", "Indian Kanoon"),
                text=item.get("text", ""),
                proposition=item.get("legal_proposition", ""),
            )
        )
        
    evidence_context = "\n\n".join(evidence_text)
    prompt = f"""You are the final answer agent for an Indian Supreme Court legal research assistant.
Question: {state.get('user_query', '')}
Evidence:\n{evidence_context}
Verification results:\n{state.get('verification_results', [])}
Answer only from the evidence. Clearly distinguish supported and uncertain claims, cite case names and document IDs, and say when evidence is insufficient. This is legal research assistance, not legal advice."""

    try:
        state["final_answer"] = (llm or LegalLLM()).generate(prompt)
    except Exception as exc:
        add_error(state, f"Answer generation error: {exc}")
        state["final_answer"] = "The agentic workflow could not generate an answer. Review the recorded errors and sources."
        
    return state


class _FallbackGraph:
    """Sequential fallback graph execution when LangGraph is unavailable."""

    def __init__(self, llm, retriever, legal_search) -> None:
        self.llm, self.retriever, self.legal_search = llm, retriever, legal_search

    def invoke(self, state: LegalState) -> LegalState:
        supervisor_agent(state, self.llm)
        search_agent(state, self.retriever, self.legal_search)
        evidence_agent(state, self.llm)
        precedent_agent(state, self.llm)
        verification_agent(state, self.llm)
        answer_agent(state, self.llm)
        return state


def build_graph(llm: LegalLLM | None = None, retriever=None, legal_search=None):
    """Build and compile the LangGraph workflow graph, with fallback support."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return _FallbackGraph(llm, retriever, legal_search)
        
    graph = StateGraph(LegalState)
    graph.add_node("supervisor", lambda state: supervisor_agent(state, llm))
    graph.add_node("search", lambda state: search_agent(state, retriever, legal_search))
    graph.add_node("evidence", lambda state: evidence_agent(state, llm))
    graph.add_node("precedent", lambda state: precedent_agent(state, llm))
    graph.add_node("verification", lambda state: verification_agent(state, llm))
    graph.add_node("answer", lambda state: answer_agent(state, llm))
    
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", "search")
    graph.add_edge("search", "evidence")
    graph.add_edge("evidence", "precedent")
    graph.add_edge("precedent", "verification")
    graph.add_edge("verification", "answer")
    graph.add_edge("answer", END)
    
    return graph.compile()


class AgenticLegalResearch:
    """Orchestrator for multi-step agentic legal research workflows."""

    def __init__(self, llm: LegalLLM | None = None, retriever=None, legal_search=None) -> None:
        self.llm = llm
        self.retriever = retriever
        self.legal_search = legal_search
        self._graph = None

    @property
    def graph(self):
        """Lazy-load and compile the workflow graph."""
        if self._graph is None:
            self._graph = build_graph(self.llm, self.retriever, self.legal_search)
        return self._graph

    def ask(self, question: str) -> dict:
        """Execute the complete agentic research workflow for a given question."""
        result = self.graph.invoke({"user_query": question, "errors": []})
        return {
            "question": question,
            "answer": result.get("final_answer", "No answer generated."),
            "topic": result.get("legal_topic"),
            "issues": result.get("legal_issues", []),
            "sources": [item.get("metadata", {}) for item in result.get("evidence", [])],
            "verification": result.get("verification_results", []),
            "errors": result.get("errors", []),
        }