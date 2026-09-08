"""FastAPI router for legal search, RAG pipeline, document processing, and courtroom simulation."""

from __future__ import annotations

import shutil
from pathlib import Path
import requests
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from utils.database import Database
from agents.workflow import AgenticLegalResearch
from courtroom import CourtroomSimulator
from document_processor import DocumentProcessor
from utils.indian_kanoon import IndianKanoonConfigurationError
from legal_search import LegalSearchService

try:
    from rag import RAGPipeline
except ImportError:
    RAGPipeline = None

router = APIRorgter = APIRouter(prefix="/api") if "router" else APIRouter(prefix="/api") # Adjusted safely below
router = APIRouter(prefix="/api")


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=2)


class DocumentTextRequest(BaseModel):
    text: str = Field(..., min_length=1)


class DocumentQuestionRequest(BaseModel):
    document_id: str = Field(..., min_length=1)
    question: str = Field(..., min_length=2)
    language: str = "English"


class SimulationRequest(BaseModel):
    question: str = Field(..., min_length=2)
    facts: str = ""
    language: str = "English"


class HearingRequest(BaseModel):
    petitioner: str = Field(..., min_length=1)
    respondent: str = Field(..., min_length=1)
    facts: str = ""
    language: str = "English"


class AdversarialReviewRequest(BaseModel):
    argument: str = Field(..., min_length=2)
    evidence: str = ""
    language: str = "English"


class CaseQuestionRequest(BaseModel):
    question: str = Field(..., min_length=2)
    language: str = "English"


rag = RAGPipeline() if RAGPipeline else None
processor = DocumentProcessor() if DocumentProcessor else None
db = Database()
search_service = LegalSearchService()
agentic_research = AgenticLegalResearch(legal_search=search_service)
courtroom = CourtroomSimulator()


def llm_unavailable(exc: Exception) -> HTTPException:
    """Return a safe, actionable error without exposing provider credentials."""
    message = str(exc).lower()
    if "401" in message or "invalid api key" in message or "authentication" in message:
        detail = "Groq authentication failed. Check GROQ_API_KEY in .env and restart the backend."
    elif "model_not_found" in message or "does not exist" in message:
        detail = "The configured Groq model is unavailable. Set MODEL_NAME=qwen/qwen3.6-27b in .env and restart the backend."
    else:
        detail = "The Groq service could not generate an answer. Check the backend logs and try again."
    return HTTPException(status_code=503, detail=detail)



# Home & Health


@router.get("/")
def home():
    """Welcome endpoint for LexAI API."""
    return {"message": "Welcome to LexAI API"}


@router.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "Running"}



# Legal Search & Kanoon Endpoints


@router.get("/search")
def search_cases(
    query: str = Query(..., min_length=2),
    page: int = Query(0, ge=0),
):
    """Search Indian Kanoon for Supreme Court judgments."""
    try:
        return search_service.search_supreme_court(query=query, page=page)
    except IndianKanoonConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/search/{doc_id}")
def get_case(doc_id: str):
    """Retrieve a full judgment from Indian Kanoon."""
    try:
        return search_service.client.get_document(doc_id)
    except IndianKanoonConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Indian Kanoon could not retrieve this judgment.") from exc


@router.post("/search/{doc_id}/query")
def query_search_result(doc_id: str, data: CaseQuestionRequest):
    """Answer a question using only the selected Indian Kanoon judgment."""
    try:
        return search_service.ask_about_document(doc_id, data.question, language=data.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc


@router.get("/search/{doc_id}/summary")
def summarize_search_result(doc_id: str, language: str = "English"):
    """Return ten important points from the selected judgment."""
    try:
        return search_service.summarize_document(doc_id, language=language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc



# AI Research & Query Endpoints


@router.post("/query")
def query(data: QuestionRequest):
    """Query the local RAG pipeline."""
    if rag is None:
        raise HTTPException(status_code=503, detail="The local RAG pipeline is not configured.")

    question = data.question.strip()
    try:
        result = rag.answer(question)
    except Exception as exc:
        raise llm_unavailable(exc) from exc

    db.save_chat(question, result["answer"])
    return result


@router.post("/agent/query")
def agent_query(data: QuestionRequest):
    """Run the supervisor-to-verification LangGraph research workflow."""
    question = data.question.strip()
    try:
        result = agentic_research.ask(question)
    except Exception as exc:
        raise llm_unavailable(exc) from exc
    db.save_chat(question, result["answer"])
    return result


@router.post("/red-team/review")
def red_team_review(data: AdversarialReviewRequest):
    """Run a symmetric, evidence-aware adversarial review of an argument."""
    try:
        return search_service.adversarial_review(data.argument, data.evidence, data.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc



# Document Analysis Endpoints


@router.post("/document/analyze")
def analyze_document(data: DocumentTextRequest):
    """Analyze supplied document text without indexing it."""
    return processor.analyze(data.text)


@router.post("/document/query")
def query_document(data: DocumentQuestionRequest):
    """Answer a question using only the selected uploaded document."""
    if rag is None:
        raise HTTPException(status_code=503, detail="The local RAG pipeline is not configured.")
    try:
        result = rag.ask(
            data.question.strip(),
            document_id=data.document_id.strip(),
            language=data.language,
        )
    except Exception as exc:
        raise llm_unavailable(exc) from exc
    db.save_chat(f"[{data.document_id}] {data.question.strip()}", result["answer"])
    return result


@router.post("/upload")
def upload(file: UploadFile = File(...)):
    """Upload and index a PDF, TXT, or Markdown document."""
    upload_dir = Path(__file__).resolve().parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = Path(file.filename or "upload").name
    
    if Path(safe_filename).suffix.lower() not in DocumentProcessor.allowed_suffixes:
        raise HTTPException(status_code=400, detail="Only PDF, TXT, and Markdown files are supported.")

    file_path = upload_dir / safe_filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        indexed = processor.index(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        strategy = search_service.build_case_strategy(
            processor.extract_text(file_path),
            safe_filename,
        )
    except ValueError as exc:
        strategy = {"strategy": str(exc), "sources": [], "limitations": [str(exc)]}

    db.save_file(safe_filename)
    return {
        "message": "Document Uploaded",
        "chunks": indexed["chunks"],
        "analysis": indexed["analysis"],
        "strategy": strategy,
    }



# Courtroom Simulation Endpoints


@router.post("/courtroom/simulate")
def simulate_courtroom(data: SimulationRequest):
    """Run an educational petitioner/respondent/judge simulation."""
    try:
        return courtroom.simulate(data.question.strip(), data.facts.strip(), data.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/courtroom/voice")
async def simulate_courtroom_voice(
    audio: UploadFile = File(...),
    facts: str = "",
    language: str = "English",
):
    """Transcribe microphone audio and run the educational courtroom simulation."""
    try:
        content = await audio.read()
        return courtroom.simulate_voice(content, audio.filename or "recording.wav", facts, language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc


@router.post("/courtroom/transcribe")
async def transcribe_courtroom_voice(audio: UploadFile = File(...)):
    """Transcribe one participant without generating the other courtroom roles."""
    try:
        content = await audio.read()
        return {"transcript": courtroom.transcribe(content, audio.filename or "recording.wav")}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc


@router.post("/courtroom/judge")
def judge_courtroom_hearing(data: HearingRequest):
    """Judge two separately recorded participant statements."""
    try:
        return courtroom.judge_hearing(data.petitioner, data.respondent, data.facts, data.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise llm_unavailable(exc) from exc



# History & Files Management


@router.get("/history")
def history():
    """Retrieve chat history."""
    return db.get_chat_history()


@router.delete("/history/{chat_id}")
def delete_history(chat_id: int):
    """Delete one saved conversation."""
    if not db.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "Conversation deleted", "chat_id": chat_id}


@router.get("/files")
def files():
    """Retrieve list of uploaded files."""
    return db.get_uploaded_files()