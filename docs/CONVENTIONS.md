# Conventions

This document defines how code, prompts, and state are structured in this repo. It exists so that
every new agent, endpoint, or ingestion source added later follows the same patterns as what's
already there — for both human contributors and coding agents working in this repo.

See `PROBLEM_BRIEF.md` for *what* this system does and `ARCHITECTURE.md` for *why* it's
architected this way. This doc is about *how things are written* day to day.

---

## 1. Project Structure

```
src/
├── agents/          # one file per agent node, e.g. competitor_finder.py
├── graph/            # state schema (state.py) + graph wiring (build_graph.py)
├── prompts/           # prompt templates only — no logic
├── ingestion/          # Tavily search, HN Algolia, page fetch + cleanup
├── config/              # models.py, settings.py — all tunable config lives here
├── api/                   # FastAPI routes — thin, no agent logic
├── worker/                 # job consumer, runs the graph
└── utils/                   # retry/backoff wrapper, source-map helpers, etc.

tests/
└── eval_cases/               # eval case definitions + pytest runner
```

**Rule:** prompt text never lives inline inside a Python function. It's always imported from
`src/prompts/`. This keeps prompt iteration separate from logic changes — you should be able to
tune a prompt without touching (or re-reviewing) the surrounding code.

---

## 2. Naming Conventions

**Agent functions** — `{purpose}_agent`, and the name must match the node name used in the
agent graph diagram in `ARCHITECTURE.md` exactly. No renaming one without the other.

```python
def idea_parser_agent(state: ResearchState) -> ResearchState: ...
def competitor_searcher_agent(state: ResearchState) -> ResearchState: ...
def competitor_relevance_filter_agent(state: ResearchState) -> ResearchState: ...
def competitor_deep_dive_agent(state: ResearchState) -> ResearchState: ...
def pain_point_miner_agent(state: ResearchState) -> ResearchState: ...
def pain_point_relevance_filter_agent(state: ResearchState) -> ResearchState: ...
def pain_point_clusterer_agent(state: ResearchState) -> ResearchState: ...
def gap_synthesizer_agent(state: ResearchState) -> ResearchState: ...
def report_builder_agent(state: ResearchState) -> ResearchState: ...
```

**State fields** — `snake_case`, and must match the `ResearchState` schema documented in
`ARCHITECTURE.md` (Section 9). If a field is added or changed in code, update the doc in the
same PR — they should never drift apart.

**Source IDs** — `SRC_{NN}`, zero-padded (`SRC_01`, `SRC_02`, ...). Assigned **only** at ingestion
time, in one place (`src/ingestion/source_map.py`). An LLM never generates a `SRC_ID` — it only
ever references one that already exists in the map it was given.

---

## 3. State & Data Rules

- All data passed between agents goes through the typed `ResearchState` object. No global
  variables, no agents writing intermediate results to disk on their own.
- **Every** piece of content injected into an LLM prompt must already be tagged with its `SRC_ID`.
  There is no code path where raw, untagged scraped/searched text reaches a model directly. This
  is a hard rule — it's what makes the citation system trustworthy.

```python
# good
prompt_content = f"[{src_id}] {cleaned_text}"

# not allowed — untagged content reaching the LLM
prompt_content = raw_scraped_text
```

- Final URL resolution (`SRC_ID` → real URL) happens once, in the backend, when building the
  report — never inside a prompt, never inferred by the model.

---

## 4. Model Usage

- The system uses **multiple LLM providers** (Gemini Flash, Groq, Cerebras, OpenRouter). Model
  and provider choice per task lives in one place: `src/config/models.py`. Agents reference a task
  name, never a hardcoded model string or provider.

```python
# src/config/models.py
MODEL_FOR_TASK = {
    "idea_parsing":       {"provider": "gemini",   "model": "gemini-2.0-flash"},
    "relevance_filter":   {"provider": "groq",     "model": "llama-3.1-8b-instant"},
    "competitor_extraction": {"provider": "cerebras", "model": "llama-3.3-70b"},
    "pain_point_clustering": {"provider": "groq",  "model": "llama-3.1-8b-instant"},
    "gap_synthesis":      {"provider": "gemini",   "model": "gemini-2.0-flash"},
    "report_formatting":  {"provider": "groq",     "model": "llama-3.1-8b-instant"},
}

FALLBACK_PROVIDER = "openrouter"  # used when primary provider returns 429
```

- All LLM calls go through one shared wrapper (`src/utils/llm_client.py`) that:
  - Routes to the correct provider based on the task name
  - Falls back to OpenRouter if the primary provider returns 429
  - Handles retry with backoff
  - Logs token usage per provider per job
  - No agent calls any provider API directly

---

## 5. Prompt Conventions

- Every prompt template declares its expected output format explicitly — usually strict JSON with
  a shown example — not left to the model to infer.
- Every prompt that includes source content repeats the citation rule inline: cite only the given
  `SRC_ID` values, never invent one, never output a raw URL.
- When a prompt is changed because an eval case failed, leave a one-line comment above the change
  noting which eval case prompted it, e.g. `# tightened after eval case "vague_idea_input" failed`.
  This stops future edits (human or agent) from silently reverting a fix.

---

## 6. Error Handling

- Ingestion failures degrade gracefully: if a page fails to fetch or an API call errors, log it,
  skip that one source, and continue the run. A single bad source should never crash a job.
- Worker jobs persist progress after each stage completes (not just at the end), so a crash at
  stage 4 doesn't lose the work from stages 1–3 — the job store should always reflect the latest
  completed stage.

---

## 7. Testing / Eval Conventions

- New agent behavior isn't done until it has at least one case in `tests/eval_cases/`.
- Two kinds of checks, used together, not one or the other:
  - **Structural** (cheap, deterministic): which tools/nodes were hit, was the output valid JSON,
    were citation IDs present. Asserted directly.
  - **Semantic** (needs judgment): is the output actually correct/reasonable. Uses the
    LLM-as-judge pattern with an explicit rubric string per case.
- Track eval pass rate over time, not strict 100%-or-fail — LLM outputs have some natural
  variance. CI fails only if pass rate drops below the agreed threshold.
- When a real bug is found through manual testing, add it as a new eval case before considering
  the fix done — this is how the eval set grows into real regression coverage over time.

---

## 8. Git / Commit Conventions

Conventional-commit style, kept simple:

```
feat(agents): add pain point miner agent
fix(ingestion): handle empty page content gracefully
docs: update ARCHITECTURE with async job flow
test(eval): add regression case for ambiguous product idea
```

Not strictly enforced, but agents generating commits should default to this format for
consistency across the history.

**Changelog** — every PR or meaningful commit that changes behavior must have a matching entry in
`CHANGELOG.md`. See that file for format, categories, and examples. Doc-only and formatting
changes are exempt.