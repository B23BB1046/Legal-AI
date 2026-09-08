---
title: LegAIQ API
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
short_description: Indian legal research and courtroom assistant API
---

# Supreme Courtroom Assistant (LegAIQ)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/Framework-FastAPI%20%7C%20Streamlit-red.svg)]()
[![Orchestration](https://img.shields.io/badge/Orchestration-LangGraph%20%7C%20ChromaDB-green.svg)]()

An end-to-end, agentic legal research and courtroom simulation platform tailored for Indian Supreme Court judgments. Driven by Indian Kanoon API integration, local vector search via ChromaDB, and Groq LLMs (`qwen/qwen3.6-27b`), this tool simplifies precedent research, document analysis, and interactive legal reasoning.

---

## 🌟 Key Features

* ** Judgment Search & Retrieval:** Direct API integration with Indian Kanoon for real-time legal research and judgment indexing.
* ** Local Legal RAG (Retrieval-Augmented Generation):** Automated processing, chunking, and embedding of judgments stored in ChromaDB for grounded context with citations.
* ** Multi-Agent Reasoning Pipeline:** Autonomous orchestration using LangGraph (Supervisor, Multi-Query Expansion, Reranking, Evidence Analysis, Precedent Extraction, and Citation Verification).
* ** Custom Document Analysis:** Isolated context-bounded querying for uploaded files (`.pdf`, `.txt`, `.md`).
* ** Voice-First Courtroom Simulation:** Interactive, multi-stage trial simulation (Petitioner, Respondent, Judge, Outcome) powered by Groq Whisper (STT) and browser-based speech synthesis (TTS).
* ** Bilingual Support:** Full support for English and simple Hindi explanations for complex legal terminology.

---

##  Architecture Overview

| Phase | Core Capability | Highlights |
| :--- | :--- | :--- |
| **Phase 1** | Judgment Search | Direct lookup via Indian Kanoon API with mandatory attribution. |
| **Phase 2** | Local RAG Pipeline | Clean, chunk, embed, and index judgments in local ChromaDB. |
| **Phase 3** | Agentic Workflow | Multi-agent execution graph with offline sequential fallback support. |

---

## Getting Started

### Prerequisites

* **Python:** 3.10 or higher
* **API Keys Required:**
  * [Indian Kanoon API Token](https://api.indiankanoon.org/)
  * [Groq API Key](https://console.groq.com/)

### Installation

1. Navigate to the repository root:
   ```powershell
   cd SupremeCourtAI
  ```

## Free Deployment

The FastAPI backend can be deployed to Render. The Streamlit interface should
be deployed separately on Streamlit Community Cloud because Render and Vercel
do not run Streamlit's persistent WebSocket session model.

### Deploy the API to Render

1. Open [Render](https://render.com) and choose **New + → Blueprint**.
2. Connect the `Rajveer-Dhaked-Singh/LegAIQ` GitHub repository.
3. Render will detect the root `render.yaml` file and create the API service.
4. Add these environment variables in the Render service settings:

    ```text
    GROQ_API_KEY=your_groq_key
    INDIAN_KANOON_API_TOKEN=your_indiankanoon_token
    MODEL_NAME=qwen/qwen3.6-27b
    CORS_ORIGINS=https://your-streamlit-app.streamlit.app
    ```

5. Deploy and verify:

    ```text
    https://your-project.onrender.com/api/health
    ```

### Connect Streamlit

Deploy `web.py` on Streamlit Community Cloud and set its secret:

   ```text
   API_URL=https://your-project.vercel.app/api
   ```

Do not commit `.env`, API keys, `venv/`, `data/`, `database/`, or `uploads/`.