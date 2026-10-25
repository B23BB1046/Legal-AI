---
title: LegAIQ API
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
short_description: Indian legal research and courtroom assistant API
---

# LegAIQ — Legal Research & Courtroom Assistant

An experimental legal-information assistant for exploring Indian judgments, document-grounded question answering, and courtroom-style simulations. It combines retrieval-augmented generation (RAG), a vector store, API-based legal search, and agentic workflows.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white) ![LangGraph](https://img.shields.io/badge/Workflow-LangGraph-6C5CE7)

> **Important:** LegAIQ is an experimental legal-information tool, not a lawyer or a substitute for professional legal advice. Verify judgments, citations, and legal interpretations against authoritative sources.

## What it can do
- **Judgment search:** integrate with the Indian Kanoon API for legal search and retrieval.
- **Local legal RAG:** process, chunk, embed, and index documents in ChromaDB for context-grounded answers.
- **Agentic workflows:** coordinate query expansion, retrieval, evidence analysis, precedent extraction, and citation checks through LangGraph components.
- **Document analysis:** work with uploaded PDF, TXT, and Markdown documents.
- **Courtroom simulation:** stage a multi-role discussion involving petitioner, respondent, judge, and outcome.
- **Accessible explanations:** provide legal concepts in plain language, including Hindi-oriented explanations where supported by the app.

## Architecture
```text
User
 ├── Streamlit interface (web.py / app.py)
 └── FastAPI service (api.py)
       ├── Legal search integration
       ├── Document processing
       ├── ChromaDB-backed retrieval
       ├── LangGraph agent workflow
       └── LLM / speech services
```

## Repository map
| Path | Responsibility |
|---|---|
| api.py | API service |
| web.py | Web interface |
| app.py | App entry point |
| courtroom.py | Courtroom simulation logic |
| legal_search.py | Legal search and retrieval |
| document_processor.py | Uploaded-document processing |
| agents/ | Agent workflow components |
| rag/ | Retrieval-augmented generation components |
| requirements.txt | Python dependencies |
| Dockerfile | Container configuration |

## Configuration
The application integrates external services. Configure credentials through environment variables or your deployment platform's secret manager. Typical settings include:
- `GROQ_API_KEY` — LLM / speech service key, where required
- `INDIAN_KANOON_API_TOKEN` — Indian Kanoon API token, where required
- `MODEL_NAME` — model identifier used by the deployment

Use the exact environment-variable names expected by the current source code and deployment configuration. Never commit API keys, private documents, or local database contents.

## Run locally
1. Clone the repository: `git clone https://github.com/B23BB1046/Legal-AI.git`
2. Enter the directory: `cd Legal-AI`
3. Create a virtual environment and activate it.
4. Install dependencies: `pip install -r requirements.txt`
5. Set required environment variables, then follow the entry-point and port configuration in the source files.

For containerized deployment, review the included Dockerfile and platform configuration.

## Design considerations
- **Grounding:** answers should be supported by retrieved passages and checked citations.
- **Traceability:** preserve the source and metadata of each retrieved judgment.
- **Failure handling:** distinguish unavailable sources from a genuine lack of evidence.
- **Privacy:** treat uploaded legal documents as potentially sensitive.
- **Evaluation:** test retrieval quality and answer faithfulness using representative queries and manually reviewed references.

## Limitations
LLM-generated summaries may omit nuance, misinterpret legal language, or produce incorrect citations. Search coverage depends on external API availability and the documents indexed locally. Always confirm legal claims from primary sources.

## Future improvements
- Add a reproducible evaluation set for retrieval and answer quality.
- Track citation correctness and evidence coverage.
- Add tests for API endpoints, document parsing, and agent failures.
- Document deployment health checks and configuration in one place.