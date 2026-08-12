# Changelog

All notable changes to this project are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This project does not
use strict semver (it's not a library), but versions are tagged as `v0.X` milestones corresponding
to the build sequence stages in `ARCHITECTURE.md`.

---

## Instructions for Contributors (Human and Agent)

- **Every PR or meaningful commit must have a corresponding entry here.** If you changed behavior,
  added a feature, fixed a bug, or modified the agent pipeline, it goes in the changelog. Doc-only
  changes and formatting tweaks are exempt.

- **Add entries under an `## [Unreleased]` section** at the top. When a milestone is reached
  (e.g. "agent graph works end-to-end locally"), the unreleased block gets a version header and
  date, and a new `## [Unreleased]` is started above it.

- **Use these categories** (skip any that don't apply):
  - `### Added` — new features, agents, sources, endpoints
  - `### Changed` — modifications to existing behavior, prompt changes, model swaps
  - `### Fixed` — bug fixes, including prompt fixes triggered by eval failures
  - `### Removed` — removed features, deprecated sources, dropped dependencies

- **Each entry should be one line**, written from the user's perspective when possible. Include
  the agent node or component name in parentheses if it's not obvious.

- **Link eval cases when relevant.** If a change was prompted by an eval failure, note the eval
  case name — same convention as `CONVENTIONS.md` Section 5 (prompt change annotations).

**Good entries:**
```
- Added `idea_parser` agent with structured output for category, target user, and search terms
- Changed gap synthesis to two-pass design (clustering + cross-reference) to reduce token usage
- Fixed competitor relevance filter accepting non-competing enterprise tools (eval: `wrong_scale_competitor`)
- Removed Reddit API integration in favor of Tavily `site:reddit.com` search
```

**Bad entries:**
```
- Updated code
- Fixed stuff
- Refactored things
```

---

## [Unreleased]

### Added
- Added new agent tools `read_webpage` and `get_app_store_reviews` to replace rigid, single-purpose scraping nodes.
- Added explicit HTTP timeouts (`timeout=settings.http_timeout`) to LangChain `ChatOpenAI` wrapper in `langchain_models.py` to prevent infinite hanging when OpenRouter connections stall.

### Changed
- Major architecture refactor: Migrated from a hard-coded 6-agent parallel LangGraph pipeline to a dynamic ReAct agent pipeline managed by a central Orchestrator.
- Replaced custom `llm_client.py` and raw string prompts with LangChain `BaseChatModel` and `ChatPromptTemplate` abstractions.
- Changed structured output extraction logic to use native `create_react_agent` tool calling rather than `with_structured_output` to prevent double LLM calls and reduce latency.
- Updated `src/config/models.py` to utilize smaller, high-speed Nemotron models (`nemotron-3.5-lightning:free`, `nemotron-nano-9b-v2:free`) for `searcher` and `report_formatting` tasks to bypass harsh OpenRouter rate limits.
- Changed `gaps` state append logic from `operator.add` to simple overwrite in `state.py` to prevent holistic state bloating.

### Fixed
- Fixed data loss bug (URL tracking collision) in `orchestrator.py`, `deep_diver.py`, and `pain_diver.py` by transitioning from `processed_urls` to `processed_candidates` (tracking by unique `src_id`).
- Fixed `'ChatPromptTemplate' object has no attribute 'to_messages'` runtime error across all agents by migrating invocation logic to `.format_messages()`.
- Fixed missing key bug in `report_builder.py` by switching from `parsed_idea` to `raw_idea`.
- Fixed orchestrator hallucinations by explicitly calculating and injecting the count of unprocessed URLs.

### Removed
- Removed legacy, rigid scraping agents (`competitor_deep_dive`, `competitor_searcher`, `gap_synthesizer`, `idea_parser`, `pain_point_clusterer`, `pain_point_miner`, `relevance_filter`) in favor of dynamic ReAct `deep_diver`, `pain_diver`, and `thinker`.

---

## [v0.3.0] - 2026-08-10

### Added
- Created `src/api/main.py` containing a FastAPI application with a synchronous `/research` endpoint.
- Completed Phase 2 of the Build Sequence: A thin API wrapper for local testing of the research graph.
- Completed Phase 3 of the Build Sequence: Asynchronous Job Worker pattern.
- Created `src/worker/main.py` containing a standalone polling worker process that consumes background research jobs.
- Implemented SQLite `jobs.db` database and `src/db/job_store.py` for atomic job queueing, state tracking, and storing serialized Pydantic result models.
- Added `subpage_navigator.py` prompt and `subpage_navigation` task to `LLMClient` (routed to Groq).
- Implemented "Two-Shot LLM Subpage Spidering" in `competitor_deep_dive.py`: the agent now uses a fast LLM to parse homepage links and fetch critical subpages (like Pricing/Features) in parallel.
- Updated `README.md` to document the new decoupled FastAPI and Worker process architecture.

### Changed
- Increased `max_html_chars` from 16,000 to 32,000 in `settings.py` to accommodate the massive text blobs generated by fetching multiple subpages.
- Refactored `pain_point_miner.py` to dynamically search communities output by the LLM (`parsed_idea.target_communities`) rather than hardcoding Reddit and Hacker News.
- Moved hardcoded limits (max competitors, HTML truncation, HTTP timeouts) into `src/config/settings.py` for easier configuration.
- Centralized database path config into `settings.py`.
- Refactored `/research` API endpoint in `src/api/main.py` to be asynchronous, immediately returning a `202 Accepted` and offloading processing to the database queue.
- Added `GET /research/{job_id}` endpoint to allow polling for real-time progress messages and the final report.

### Fixed
- Fixed `NameError` in `relevance_filter.py` by adding missing `get_settings` import.
- Fixed schema parroting bug in `LLMClient` where fallback logic lost the strict Pydantic JSON schema format.
- Fixed region hardcoding in scrapers to respect `parsed_idea.target_country_code`.
- Fixed JSON serialization crashes in the worker by explicitly dumping Pydantic models (e.g. `ParsedIdea`) via `.model_dump()` before saving to SQLite.

## [v0.2.0] - 2026-08-09

### Added
- Implemented the complete 9-node LangGraph execution pipeline (`src/graph/build_graph.py`) with parallel fan-out and fan-in routing.
- Built the `LLMClient` (`src/utils/llm_client.py`) with automatic multi-provider routing (Gemini, Groq, Cerebras) and OpenRouter fallback on quota exhaustion.
- Implemented the `SourceMap` utility to deterministically track and resolve `[SRC_XXXX]` citations from raw search results to the final markdown report.
- Developed the 9 core agent nodes (`src/agents/`) and their associated prompts (`src/prompts/`) for end-to-end autonomous execution.
- Added automated `tenacity` retries for rate limits and connection errors across all API calls.

### Changed
- Migrated data structures (`ParsedIdea`, `CompetitorProfile`, `Gap`, `PainPointCluster`) from `TypedDict` to Pydantic `BaseModel` to fix structured output validation errors.
- Updated `LLMClient` to strictly enforce Pydantic structured output using JSON Schema injection and robust regex parsing.
- Reduced `max_workers` from 5 to 2 in `relevance_filter.py` and `competitor_deep_dive.py` to prevent 429 RateLimitErrors on Groq/Gemini free tiers.
- Switched Cerebras provider from `llama-3.3-70b` to `gemma-4-31b` to align with free tier availability.
- Updated `report_builder` prompt to prevent hallucinatory empty headers (e.g., "Moderate Signals") when no data is present.
- Enforced strict citation formatting in `report_builder` to prevent the LLM from inventing fake `[1](url)` tags, ensuring the `SourceMap` successfully resolves `[SRC_XXXX]` tags.

### Fixed
- Fixed `NameError` in `LLMClient` OpenRouter fallback logic when referencing the primary model name.
- Fixed 400 Bad Request errors from OpenRouter by updating the fallback mapping to use `openai/gpt-4o-mini` when Gemini rate limits are hit.
- Fixed `301 Moved Permanently` errors during Hacker News searches by switching the Algolia API URL from `http://` to `https://` in `pain_point_miner.py`.

## [v0.1.0] - 2026-08-07

### Added
- Project documentation: `PROBLEM_BRIEF.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `CHANGELOG.md`
- Designed 9-node LangGraph agent pipeline with parallel competitor/pain-point branches
- Designed two-pass gap synthesis strategy (pain point clustering → cross-reference synthesis)
- Multi-provider LLM strategy (Gemini Flash, Groq, Cerebras, OpenRouter fallback)
- `ResearchState` schema with full type definitions
- Conditional app store review fetching (1-2 star reviews) inside competitor deep dive
- Depth settings (fast vs. deep) with concrete token/query budgets
