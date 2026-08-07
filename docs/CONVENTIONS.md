# Conventions

This document defines how code, prompts, and state are structured in this repo. It exists so that
every new agent, endpoint, or ingestion source added later follows the same patterns as what's
already there — for both human contributors and coding agents working in this repo.

See `problem_statement.md` for *what* this system does and `technical_design.md` for *why* it's
architected this way. This doc is about *how things are written* day to day.

---

## 1. Project Structure

```
src/
├── agents/          # one file per agent node, e.g. competitor_finder.py
├── graph/            # state schema (state.py) + graph wiring (build_graph.py)
├── prompts/           # prompt templates only — no logic
├── ingestion/          # search API calls, Reddit API, page fetch + cleanup
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
architecture diagram in `technical_design.md` exactly. No renaming one without the other.

```python
def competitor_finder_agent(state: ResearchState) -> ResearchState: ...
def gap_synthesis_agent(state: ResearchState) -> ResearchState: ...
```

**State fields** — `snake_case`, and must match the `ResearchState` schema documented in
`technical_design.md`. If a field is added or changed in code, update the doc in the same PR —
they should never drift apart.

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

- Model choice per task lives in one place: `src/config/models.py`. Agents reference a task name
  (`"relevance_filter"`, `"gap_synthesis"`), not a hardcoded model string.

```python
# src/config/models.py
MODEL_FOR_TASK = {
    "relevance_filter": "llama-3.1-8b-instant",
    "extraction":         "llama-3.1-8b-instant",
    "gap_synthesis":      "llama-3.3-70b-versatile",
}
```

- All LLM calls go through one shared wrapper (`src/utils/llm_client.py`) that handles retry with
  backoff on 429s and logs token usage. No agent calls the Groq API directly.

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