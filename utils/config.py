import os
from pathlib import Path
from dotenv import load_dotenv
from types import SimpleNamespace

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Configuration constants
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

INDIAN_KANOON_API_TOKEN = os.getenv("INDIAN_KANOON_API_TOKEN")

MODEL_NAME = os.getenv("MODEL_NAME", "qwen/qwen3.6-27b")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))

CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 100))

TOP_K = int(os.getenv("TOP_K", 5))

AGENT_MAX_QUERIES = int(os.getenv("AGENT_MAX_QUERIES", 2))

AGENT_TOP_K = int(os.getenv("AGENT_TOP_K", 2))

AGENT_MAX_EVIDENCE = int(os.getenv("AGENT_MAX_EVIDENCE", 3))

AGENT_MAX_PRECEDENTS = int(os.getenv("AGENT_MAX_PRECEDENTS", 2))

INDEX_PATH = os.getenv("INDEX_PATH", "data/faiss_index")

CHROMA_PATH = os.getenv(
	"CHROMA_PATH",
	str(Path(__file__).resolve().parent.parent / "data" / "chroma"),
)

COLLECTION_NAME = os.getenv("COLLECTION_NAME", "supreme_court_judgments")


# Backwards-compatible settings object used by some modules
settings = SimpleNamespace(
	GROQ_API_KEY=GROQ_API_KEY,
	INDIAN_KANOON_API_TOKEN=INDIAN_KANOON_API_TOKEN,
	MODEL_NAME=MODEL_NAME,
	EMBEDDING_MODEL=EMBEDDING_MODEL,
	CHUNK_SIZE=CHUNK_SIZE,
	CHUNK_OVERLAP=CHUNK_OVERLAP,
	TOP_K=TOP_K,
	AGENT_MAX_QUERIES=AGENT_MAX_QUERIES,
	AGENT_TOP_K=AGENT_TOP_K,
	AGENT_MAX_EVIDENCE=AGENT_MAX_EVIDENCE,
	AGENT_MAX_PRECEDENTS=AGENT_MAX_PRECEDENTS,
	INDEX_PATH=INDEX_PATH,
	CHROMA_PATH=CHROMA_PATH,
	COLLECTION_NAME=COLLECTION_NAME,
)