import streamlit as st
import requests
import os
import time
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from utils.evaluation import calculate_metrics

try:
    configured_api_url = st.secrets.get("API_URL")
except Exception:
    configured_api_url = None
API_URL = configured_api_url or os.getenv("API_URL", "http://127.0.0.1:8000/api")

# Helper Functions


def response_error(response: requests.Response, fallback: str) -> str:
    """Return an API error detail, handling plain-text and empty responses."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("detail"):
        return str(payload["detail"])
    body = response.text.strip()
    return body[:300] if body else fallback


def render_answer(result: dict, heading: str = "AI Answer") -> None:
    st.success(heading)
    st.write(result.get("answer", "No answer generated."))
    if result.get("topic"):
        st.caption(f"Topic: {result['topic']}")
    if result.get("sources"):
        st.caption("Sources")
        for source in result["sources"]:
            st.write(
                f"{source.get('title', 'Unknown case')} "
                f"(Document ID: {source.get('doc_id', 'Unknown')})"
            )


def render_courtroom_stage(
    result: dict | None = None,
    api_available: bool = False,
    language: str = "English",
) -> None:
    """Render courtroom roles as a sequential native Streamlit hearing."""
    result = result if isinstance(result, dict) else {}
    outcome = "The judge's view will appear here after the hearing."
    if result:
        outcome = result.get("outcome", outcome)

    with st.container(border=True):
        header_column, delete_column = st.columns([8, 1])
        with header_column:
            st.markdown(
                '<div class="courtroom-title"><span class="courtroom-title-icon">⚖️</span>Judge\'s Bench</div>',
                unsafe_allow_html=True,
            )
        with delete_column:
            if st.button("🗑️", key="clear-courtroom", help="Clear this hearing and start again"):
                for key in (
                    "courtroom_result",
                    "petitioner_statement",
                    "respondent_statement",
                    "petitioner_audio_signature",
                    "respondent_audio_signature",
                    "courtroom_animated",
                    "courtroom_spoken",
                ):
                    st.session_state.pop(key, None)
                st.session_state["courtroom_reset_version"] = st.session_state.get(
                    "courtroom_reset_version", 0
                ) + 1
                st.rerun()
        st.caption("The hearing will unfold one voice at a time.")
        animate = bool(result) and not st.session_state.get("courtroom_animated")

        _, judge_column, _ = st.columns([1, 2, 1])
        with judge_column:
            judge_placeholder = st.empty()
            if animate:
                time.sleep(0.5)
            with judge_placeholder.container(border=True):
                st.markdown(
                    '<div class="courtroom-role-title"><span class="courtroom-role-icon">⚖️</span>Judge</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Listens and explains the legal issue")
                st.write(result.get("judge", "Waiting for the hearing..."))

        petitioner_column, respondent_column = st.columns(2)
        side_placeholders = [petitioner_column.empty(), respondent_column.empty()]
        side_roles = [
            ("Petitioner", "The person asking the court for help", "petitioner"),
            ("Respondent", "The other side in the matter", "respondent"),
        ]
        
        for index, (label, subtitle, key) in enumerate(side_roles):
            if animate:
                time.sleep(0.5)
            with side_placeholders[index].container(border=True):
                icon = "👤" if key == "petitioner" else "👥"
                st.markdown(
                    f'<div class="courtroom-role-title"><span class="courtroom-role-icon">{icon}</span>{label}</div>',
                    unsafe_allow_html=True,
                )
                st.caption(subtitle)
                st.write(
                    result.get(
                        key,
                        st.session_state.get(f"{key}_statement", "Waiting for the hearing..."),
                    )
                )
                reset_version = st.session_state.get("courtroom_reset_version", 0)
                audio = st.audio_input(
                    f"Record {label.lower()}",
                    key=f"{key}-audio-{reset_version}",
                )
                if audio is not None:
                    audio_signature = hashlib.sha256(audio.getvalue()).hexdigest()
                    signature_key = f"{key}_audio_signature"
                    if st.session_state.get(signature_key) != audio_signature:
                        if not api_available:
                            st.error("Start the backend before recording a statement.")
                        else:
                            try:
                                response = requests.post(
                                    f"{API_URL}/courtroom/transcribe",
                                    files={
                                        "audio": (
                                            f"{key}.wav",
                                            audio.getvalue(),
                                            audio.type or "audio/wav",
                                        )
                                    },
                                    timeout=180,
                                )
                                if response.status_code == 200:
                                    st.session_state[f"{key}_statement"] = response.json().get("transcript", "")
                                    st.session_state[signature_key] = audio_signature
                                    st.rerun()
                                else:
                                    st.error(response_error(response, f"Transcription failed: {response.status_code}"))
                            except requests.RequestException as exc:
                                st.error(f"Transcription service unavailable: {exc}")
                                
        if animate:
            time.sleep(0.5)
            st.session_state["courtroom_animated"] = True
            
        st.info(f"Hearing status: {outcome}")
        
        if result and not st.session_state.get("courtroom_spoken"):
            speech_text = f"Judge. {result.get('judge', '')}. Decision. {result.get('outcome', '')}"
            speech_language = "hi-IN" if language == "Hindi" else "en-IN"
            speech_html = f"""<!doctype html><html><body><script>
            const text = {json.dumps(speech_text)};
            const targetLanguage = {json.dumps(speech_language)};
            const speak = () => {{
                const voices = window.speechSynthesis.getVoices();
                const indianVoices = voices.filter((voice) => voice.lang.toLowerCase() === targetLanguage.toLowerCase());
                const maleVoice = indianVoices.find((voice) => /male|ravi|hemant|madhur|prabhat|aditya/i.test(voice.name));
                const voice = maleVoice || indianVoices[0] || voices.find((item) => item.lang.toLowerCase().startsWith(targetLanguage.slice(0, 2))) || voices[0];
                const utterance = new SpeechSynthesisUtterance(text);
                utterance.lang = targetLanguage;
                utterance.rate = 0.95;
                if (voice) utterance.voice = voice;
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            }};
            speak();
            window.speechSynthesis.onvoiceschanged = speak;
            </script></body></html>"""
            st.iframe(f"data:text/html,{quote(speech_html)}", height=1)
            st.session_state["courtroom_spoken"] = True



# App Configuration & Health Check


st.set_page_config(
    page_title="⚖️✦ LegAIQ",
    page_icon="⚖️✦",
    layout="wide"
)

st.markdown(
    """
    <style>
    .courtroom-title, .courtroom-role-title {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        font-weight: 700;
    }
    .courtroom-title { font-size: 1.2rem; }
    .courtroom-title-icon { font-size: 1.8rem; }
    .courtroom-role-title { font-size: 1.15rem; }
    .courtroom-role-icon { font-size: 2.2rem; line-height: 1; }
    .legaiq-brand {
        color: #d6a84f;
        
        text-decoration: underline;
        text-decoration-color: #d6a84f;
        text-decoration-thickness: 3px;
        text-underline-offset: 8px;
    }
    .legaiq-tagline {
        color: #5ec8c5;
        font-size: 1.15rem;
    }
    .legaiq-description {
        color: #c8cbd4;
        font-size: 1.05rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="legaiq-brand">✦ LegAIQ ✦</h1>', unsafe_allow_html=True)
st.markdown(
    '<div class="legaiq-tagline">Research • Analyze • Verify • Simulate</div>',
    unsafe_allow_html=True,
)

try:
    requests.get(f"{API_URL}/health", timeout=2).raise_for_status()
    api_available = True
except requests.RequestException:
    api_available = False
    st.warning(
        "Backend is offline. Start it with `python main.py` in another terminal, "
        "then refresh this page."
    )

st.markdown(
    '<div class="legaiq-description">Explore jurisprudence, trace precedents, analyze cases, and build evidence-backed legal insights.</div>',
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "Search",
    "Argument Review",
    "Case Workspace",
    "Courtroom Simulation",
    "Evaluation",
])



#"""Sidebar: Language & Chat History"""

with st.sidebar:
    app_language = st.selectbox(
        "Language",
        ["English", "Hindi"],
        format_func=lambda value: "हिंदी" if value == "Hindi" else value,
        key="app-language",
    )
    st.divider()
    st.title("Chats")
    st.caption("Recent research conversations")
    
    if not api_available:
        st.info("Start the backend to load chat history.")
    else:
        try:
            history_response = requests.get(f"{API_URL}/history", timeout=10)
            if history_response.status_code == 200:
                history = history_response.json()
                if history:
                    for item in history[:30]:
                        question_preview = item[1].strip().replace("\n", " ")
                        label = question_preview[:45] + ("..." if len(question_preview) > 45 else "")
                        
                        # Layout columns with better spacing ratio
                        chat_cols = st.columns([5, 1], gap="small",vertical_alignment="center")
                        
                        with chat_cols[0]:
                            with st.expander(label or "Untitled conversation"):
                                st.caption("Question")
                                st.write(item[1])
                                st.caption("Answer")
                                st.write(item[2])
                                
                        with chat_cols[1]:
                        
                            if st.button("🗑️", key=f"delete-chat-{item[0]}", help="Delete this chat"):
                                try:
                                    delete_response = requests.delete(
                                        f"{API_URL}/history/{item[0]}",
                                        timeout=10,
                                    )
                                    if delete_response.status_code == 200:
                                        st.rerun()
                                    else:
                                        st.error(response_error(delete_response, "Unable to delete chat."))
                                except requests.RequestException as exc:
                                    st.error(f"Delete service unavailable: {exc}")
                else:
                    st.caption("No conversations yet.")
            else:
                st.error(response_error(history_response, "Chat history unavailable."))
        except requests.RequestException as exc:
            st.error(f"Chat history unavailable: {exc}")

# Tab 0: Search Supreme Court Judgments


with tabs[0]:
    st.header("Search Supreme Court Judgments")
    search_query = st.text_input(
        "Search Indian Kanoon",
        placeholder="Article 21 right to privacy",
    )
    if st.button("Search Supreme Court"):
        if len(search_query.strip()) < 2:
            st.warning("Enter at least two characters.")
        else:
            try:
                response = requests.get(
                    f"{API_URL}/search",
                    params={"query": search_query},
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state["search_documents"] = data.get("documents", [])
                    st.session_state["search_total"] = data.get("total", 0)
                else:
                    st.error(response_error(response, f"Search failed: {response.status_code}"))
            except requests.RequestException as exc:
                st.error(f"Search service unavailable: {exc}")

    documents = st.session_state.get("search_documents", [])
    if documents:
        st.caption(
            f"{st.session_state.get('search_total', len(documents))} results | Powered by Indian Kanoon"
        )
    for document in documents:
        doc_id = document.get("doc_id")
        saved_answer = st.session_state.get("case_answers", {}).get(doc_id)
        st.markdown(f"- **{document.get('title') or 'Untitled judgment'}**")
        with st.expander(
            "View case details",
            expanded=saved_answer is not None,
        ):
            st.write(document.get("headline") or "No headline available.")
            if doc_id:
                st.caption(f"Document ID: {doc_id}")
                if st.button("Show 10 key points", key=f"doc-{doc_id}"):
                    detail = requests.get(
                        f"{API_URL}/search/{doc_id}/summary",
                        params={"language": app_language},
                        timeout=180,
                    )
                    if detail.status_code == 200:
                        summary = detail.json()
                        st.markdown("**10 important points**")
                        st.write(summary.get("summary", "No summary returned."))
                    else:
                        st.error(response_error(detail, f"Summary failed: {detail.status_code}"))
            result_question = st.text_input(
                "Ask AI about this case",
                placeholder="What principle did the Court establish?",
                key=f"case-question-{doc_id}",
            )
            if st.button("Ask about this result", key=f"case-ask-{doc_id}"):
                if len(result_question.strip()) < 2:
                    st.warning("Enter a question about this case.")
                else:
                    try:
                        case_response = requests.post(
                            f"{API_URL}/search/{doc_id}/query",
                            json={"question": result_question, "language": app_language},
                            timeout=180,
                        )
                        if case_response.status_code == 200:
                            st.session_state.setdefault("case_answers", {})[doc_id] = case_response.json()
                        else:
                            st.error(response_error(case_response, f"Case question failed: {case_response.status_code}"))
                    except requests.RequestException as exc:
                        st.error(f"Case question service unavailable: {exc}")
            if saved_answer:
                render_answer(saved_answer, "Case-specific answer")


# Tab 1: Bias-Free Adversarial Review


with tabs[1]:
    st.header("Bias-Free Adversarial Legal Review")
    st.caption(
        "Steelman the argument first, then test its evidence, logic, authorities, factual fit, and uncertainty."
    )
    review_argument = st.text_area(
        "Legal argument",
        placeholder="Example: Government surveillance violates Article 21 because it lacks proportionality and safeguards.",
        key="review-argument",
    )
    review_evidence = st.text_area(
        "Evidence and cited authorities (optional)",
        placeholder="Paste facts, documents, case names, citations, or the opposing material you have.",
        key="review-evidence",
    )
    if st.button("Run Adversarial Review", type="primary"):
        if len(review_argument.strip()) < 2:
            st.warning("Enter the argument you want to test.")
        else:
            try:
                response = requests.post(
                    f"{API_URL}/red-team/review",
                    json={
                        "argument": review_argument,
                        "evidence": review_evidence,
                        "language": app_language,
                    },
                    timeout=180,
                )
                if response.status_code == 200:
                    st.session_state["adversarial_review"] = response.json()
                else:
                    st.error(response_error(response, f"Adversarial review failed: {response.status_code}"))
            except requests.RequestException as exc:
                st.error(f"Review service unavailable: {exc}")

    review = st.session_state.get("adversarial_review")
    if review:
        st.success("Adversarial review complete")
        st.markdown(review.get("review", "No review generated."))
        sources = review.get("sources", [])
        if sources:
            st.subheader("Indian Kanoon research leads")
            for source in sources:
                st.write(
                    f"- {source.get('title', 'Unknown case')} "
                    f"(Document ID: {source.get('doc_id', 'Unknown')})"
                )
        for limitation in review.get("limitations", []):
            st.warning(limitation)



# Tab 2: Case Workspace & Document Upload


with tabs[2]:
    st.header("Case Workspace")
    st.caption("Upload a petition or judgment to prepare a case strategy and explore its contents.")
    upload_area = st.container(border=True)
    with upload_area:
        uploaded_file = st.file_uploader(
            "Choose a petition or judgment",
            type=["pdf", "txt", "md"],
            help="PDF, text, and Markdown files are supported.",
        )
        if uploaded_file is not None and st.button("Analyze Document"):
            if not api_available:
                st.error("Start the backend before indexing documents.")
            else:
                try:
                    response = requests.post(
                        f"{API_URL}/upload",
                        files={
                            "file": (
                                uploaded_file.name,
                                uploaded_file,
                                uploaded_file.type,
                            )
                        },
                        timeout=120,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state["document_status"] = data
                        st.session_state["selected_document"] = uploaded_file.name
                        st.success(f"{uploaded_file.name} has been analyzed and is ready.")
                    else:
                        st.error(response_error(response, f"Document analysis failed: {response.status_code}"))
                except requests.RequestException as exc:
                    st.error(f"Document service unavailable: {exc}")

    document_status = st.session_state.get("document_status")
    if document_status:
        analysis = document_status.get("analysis", {})
        st.markdown(
            f"**{st.session_state.get('selected_document', 'Selected document')}**  "
            f"· {document_status.get('chunks', 0)} passages analyzed"
        )
        if analysis:
            details = []
            if analysis.get("sections"):
                details.append("Sections: " + ", ".join(analysis["sections"]))
            if analysis.get("issues"):
                details.append("Issues: " + ", ".join(analysis["issues"]))
            if details:
                st.caption(" · ".join(details))
        strategy = document_status.get("strategy", {})
        if strategy:
            st.subheader("Preliminary Case Strategy")
            st.caption(
                "Research assistance only. Verify every fact, provision, and authority with a qualified lawyer."
            )
            st.markdown(strategy.get("strategy", "Strategy could not be generated."))
            strategy_sources = strategy.get("sources", [])
            if strategy_sources:
                st.write("**Indian Kanoon authorities considered**")
                for source in strategy_sources:
                    st.write(
                        f"- {source.get('title', 'Unknown case')} "
                        f"(Document ID: {source.get('doc_id', 'Unknown')})"
                    )
            for limitation in strategy.get("limitations", []):
                st.warning(limitation)

    if api_available:
        try:
            files_response = requests.get(f"{API_URL}/files", timeout=10)
            uploaded_records = files_response.json() if files_response.status_code == 200 else []
        except (requests.RequestException, ValueError):
            uploaded_records = []
        file_options = {
            record[1]: Path(record[1]).stem
            for record in uploaded_records
            if isinstance(record, (list, tuple)) and len(record) > 1
        }
        if file_options:
            selected_file = st.session_state.get("selected_document")
            if selected_file not in file_options:
                selected_file = next(reversed(file_options))
                st.session_state["selected_document"] = selected_file
            document_question = st.chat_input("Ask a question about this document")
            if document_question:
                with st.chat_message("user"):
                    st.write(document_question)
                try:
                    response = requests.post(
                        f"{API_URL}/document/query",
                        json={
                            "document_id": file_options[selected_file],
                            "question": document_question,
                            "language": app_language,
                        },
                        timeout=120,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state.setdefault("document_answers", {})[selected_file] = result
                    else:
                        st.error(response_error(response, f"Document question failed: {response.status_code}"))
                except requests.RequestException as exc:
                    st.error(f"Document questions are unavailable: {exc}")
            saved_result = st.session_state.get("document_answers", {}).get(selected_file)
            if saved_result:
                with st.chat_message("assistant"):
                    st.write(saved_result.get("answer", "No answer returned."))
                    for source in saved_result.get("sources", []):
                        st.caption(
                            f"Source: {source.get('title', selected_file)} "
                            f"(chunk {source.get('chunk_id', '?')})"
                        )
        else:
            st.info("Analyze a petition or judgment above to start asking questions.")


# Tab 3: Courtroom Simulation


with tabs[3]:
    st.header("Understand Your Legal Problem")
    st.caption("No legal language is required. Explain your situation in your own words and hear both sides plus a judge-style explanation.")
    st.info("Example: 'My landlord is asking me to leave without notice. What can I do?'")
    
    render_courtroom_stage(
        st.session_state.get("courtroom_result"),
        api_available=api_available,
        language=app_language,
    )
    
    petitioner_statement = st.session_state.get("petitioner_statement", "")
    respondent_statement = st.session_state.get("respondent_statement", "")
    
    st.subheader("Start the hearing")
    if petitioner_statement and respondent_statement and st.button("Start Hearing", type="primary"):
        if not api_available:
            st.error("Start the backend before requesting the judge's decision.")
        else:
            try:
                response = requests.post(
                    f"{API_URL}/courtroom/judge",
                    json={
                        "petitioner": petitioner_statement,
                        "respondent": respondent_statement,
                        "facts": "",
                        "language": app_language,
                    },
                    timeout=180,
                )
                if response.status_code == 200:
                    st.session_state["courtroom_result"] = response.json()
                    st.session_state["courtroom_animated"] = False
                    st.session_state["courtroom_spoken"] = False
                else:
                    st.error(response_error(response, f"Judge request failed: {response.status_code}"))
            except requests.RequestException as exc:
                st.error(f"Judge service unavailable: {exc}")
                
    if petitioner_statement or respondent_statement:
        st.caption("Your recorded statements appear above as text before the judge decides.")



# Tab 4: Legal AI Evaluation


with tabs[4]:
    st.header("Legal AI Evaluation")
    st.caption("Measure research quality against labeled benchmark cases, not illustrative numbers.")
    evaluation_file = st.file_uploader(
        "Upload evaluation cases (JSON)",
        type=["json"],
        help="Use a JSON array of cases with expected and observed retrieval, citation, evidence, and completion fields.",
        key="evaluation-cases",
    )
    cases = []
    if evaluation_file is not None:
        try:
            loaded = json.loads(evaluation_file.getvalue().decode("utf-8"))
            cases = loaded if isinstance(loaded, list) else loaded.get("cases", [])
            if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
                raise ValueError("Expected a JSON array of evaluation case objects.")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, ValueError) as exc:
            st.error(f"Evaluation file could not be read: {exc}")

    if cases:
        metrics = calculate_metrics(cases)
        metric_items = [
            ("Citation Accuracy", "citation_accuracy", True),
            ("Evidence Support Rate", "evidence_support_rate", True),
            ("Retrieval Precision", "retrieval_precision", True),
            ("Retrieval Recall", "retrieval_recall", True),
            ("Hallucination Rate", "hallucination_rate", True),
            ("Precedent Identification", "precedent_identification_accuracy", True),
            ("Research Completion", "research_completion_rate", True),
            ("Average Search Iterations", "average_search_iterations", False),
        ]
        metric_columns = st.columns(4)
        for index, (label, key, percentage) in enumerate(metric_items):
            value = metrics[key]
            display = "Not measured" if value is None else f"{value * 100:.1f}%" if percentage else f"{value:.1f}"
            metric_columns[index % 4].metric(label, display)
        st.caption(f"Based on {metrics['case_count']} labeled evaluation case(s).")
    else:
        st.info("Upload labeled evaluation cases to calculate these metrics.")
        st.markdown(
            "**Required fields per case:** `expected_doc_ids`, `retrieved_doc_ids`, `expected_citations`, `cited_citations`, `supported_claims`, `total_claims`, `hallucinated_claims`, `expected_precedents`, `identified_precedents`, `completed`, `search_iterations`."
        )