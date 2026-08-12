# AI Market Research Agent 🚀

An autonomous, multi-agent AI system built on **LangGraph** that takes a raw product idea, actively researches the competitive landscape, mines user pain points from the web, and synthesizes actionable market gaps and positioning strategies.

Designed for robust execution, the system employs a central orchestrator managing specialized ReAct agents, fully decoupled via an asynchronous FastAPI & SQLite worker queue, and powered by intelligent multi-provider LLM failovers.

---

## 🏗️ Architecture & Core Features

### 1. Dynamic ReAct Agent Pipeline (LangGraph)
Migrated from a rigid parallel graph to a highly dynamic **ReAct pipeline**, the system features 5 specialized reasoning agents:
- **Orchestrator**: The central brain. Evaluates the current state of research, injects task counts, and conditionally routes execution to the appropriate worker agent until the strategy is fulfilled.
- **Searcher**: Identifies primary competitors and pain point sources across the web.
- **Deep Diver**: Uses native tool-calling to scrape and analyze specific competitor websites, extracting pricing, feature gaps, and weaknesses.
- **Pain Diver**: Scrapes Reddit, HackerNews, and blogs to extract detailed, authentic user frustrations.
- **Thinker**: Synthesizes the scraped data to identify unserved market gaps (e.g., strong pain point + majority of competitors failing to address it).

### 2. Asynchronous Job Architecture
Built to handle long-running, multi-minute LLM workflows without blocking:
- **FastAPI**: Provides a RESTful API to submit raw product ideas, immediately returning a `202 Accepted` and a unique `job_id`.
- **Background Worker**: A standalone Python polling process that consumes jobs from a queue, processes them through the LangGraph pipeline, and updates real-time progress messages.
- **SQLite Job Store**: Handles atomic job queueing, state tracking, and storing serialized Pydantic result models.

### 3. Resilient Multi-Provider LLM Routing
Optimized for high-volume free-tier usage:
- **Auto-Failover**: Intelligently routes tasks across OpenRouter models (NVIDIA Nemotron 3 Ultra 550b, Lightning, Llama 3.1). If a model hits a 429 rate limit or connection stall, the client immediately catches the timeout and fails over to the next configured model.
- **Speed/Reasoning Separation**: Uses smaller, lightning-fast models for simple scraping/formatting tasks, reserving massive 550B parameter models strictly for complex reasoning (Orchestrator, Thinker).

### 4. Deterministic Citation Engine (SourceMap)
No LLM hallucinations allowed. The system maps raw scraped sources (competitor URLs, Reddit threads, app store reviews) via unique `src_id`s directly to the final generated markdown report, ensuring every claim is backed by a traceable `[1]` citation link.

### 5. Advanced State Management
- Utilizes custom LangGraph reducers to safely merge dictionaries and append arrays without holistic state bloating.
- Employs unique `src_id` tracking (vs. raw URL tracking) to prevent candidate collisions and data loss when agents parse multiple competitors from a single aggregator listicle.

---

## 🚀 Quickstart

This project uses modern Python (3.11+) and `uv` for dependency management.

### 1. Setup Environment
```bash
uv venv
# Windows: .\.venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
uv pip install -r pyproject.toml
```

### 2. Configure API Keys
Copy `.env.example` to `.env` and fill in your keys (Tavily, OpenRouter).
```bash
cp .env.example .env
```

### 3. Run the System

**Terminal 1 (Start the API):**
```bash
uvicorn src.api.main:app --reload
```

**Terminal 2 (Start the Worker):**
```bash
python -m src.worker.main
```

**Terminal 3 (Submit a Job):**
```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"idea": "A CRM for pet sitters", "depth": "fast"}'
```
*This will instantly return a `job_id`.*

**Poll for Progress:**
```bash
curl http://127.0.0.1:8000/research/{your_job_id}
```
*The response will stream real-time orchestrator progress messages and the final Markdown report once completed.*

---

## 📚 Documentation
For a historical record of all major pipeline refactors, bug squashes, and architectural pivots, please refer to the [CHANGELOG.md](./CHANGELOG.md).
