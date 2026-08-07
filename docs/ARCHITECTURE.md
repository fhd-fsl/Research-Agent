# Product Research Assistant — Technical Design

This builds on `problem_statement.md`. That doc defines *what* and *why*; this defines *how*.

---

## 1. High-Level Architecture

The system is **asynchronous, job-based**, not a synchronous request/response API. A research run takes 60-180+ seconds — too long for a single HTTP request to survive API Gateway (29s hard timeout) or a naive Lambda invocation. So:

```
Client
  │
  ▼
POST /research  ──────────► creates Job (status: "pending"), pushes to queue
  │                          returns { job_id } immediately (202 Accepted)
  │
  ▼
GET /research/{job_id}  ──► poll for status + progress messages
                             ("searching reddit...", "filtering competitors...",
                              "synthesizing gaps...")
  │
  ▼
  Worker (separate process from the API) picks up the job from the queue,
  runs the full agent graph, writes progress + final result back to the
  job store as it goes.
```

**Why this shape**: decouples "accept the request" from "do the slow work," which is the standard fix for long-running tasks behind a web API, and it also gives you a natural place to surface progress to a future UI (poll `GET /research/{job_id}` and show a progress bar/log).

**Components:**
- **API layer** — thin. Accepts requests, creates job records, enqueues work, serves status/results. No agent logic lives here.
- **Queue** — decouples API from Worker. Also gives you retry semantics for free if a worker crashes mid-job.
- **Worker** — runs the actual LangGraph agent pipeline. Long-lived process (not a Lambda with a hard 15-min cap), polls the queue, updates job status as it progresses.
- **Job store** — holds job status, progress messages, and the final report once done.

---

## 2. Relevance Filtering: Two-Stage Pipeline

This is the mechanism behind the "relevance filtering" requirement from the problem statement — solving the catch-22 of "you need to read something to know if it's relevant, but reading it is the expensive part."

**Stage 1 — Cheap filter (every raw candidate goes through this):**
- Take the search result's title + snippet only (not the full page).
- Either: compute embedding similarity between the user's product idea and the snippet, and threshold on that — OR — send title+snippet to a small/fast model (e.g. Llama 3.1 8B on Groq, which has much higher rate limits than the 70B model) and ask for a simple YES/NO/MAYBE relevance call with one-line reasoning.
- This is cheap enough (tiny input, tiny output, fast model) to run on every single raw candidate without denting the rate-limit budget.

**Stage 2 — Deep filter (only survivors of Stage 1):**
- Only the top N candidates (e.g. top 3-5 competitors, top 8-10 pain-point threads) get their full content fetched and passed to the stronger model for real analysis.
- This is where the expensive tokens actually get spent — and only on things already pre-qualified as likely relevant.

This two-stage structure is also your main lever for controlling cost and rate-limit exposure: Stage 1 is cheap and high-volume, Stage 2 is expensive and low-volume by design.

**Depth setting** (fast vs. deep, from the problem statement) controls: how many raw candidates Stage 1 processes, and how many survivors Stage 2 processes. Fast = smaller numbers at both stages; deep = larger.

---

## 3. Source Tracking & Citation Integrity (The "Source Map" Pattern)

**Problem**: if you hand an LLM 10 sources and ask it to synthesize findings with citations, it will sometimes mix up which quote came from which URL, or invent a plausible-looking URL that doesn't exist. This directly undermines the "every claim is traceable to a real source" requirement, so it needs a structural fix, not a prompting fix.

**Fix — the LLM never outputs a raw URL. Ever.**

1. During ingestion, every piece of source content gets a short internal ID as it's collected:
   ```
   SRC_01 → { url: "https://reddit.com/r/...", text: "scraped complaint snippet" }
   SRC_02 → { url: "https://competitor.com/pricing", text: "Tier 1 starts at $49..." }
   ```
2. When content is injected into any LLM prompt, it's tagged with its ID (`[SRC_01] ...text...`).
3. The LLM is instructed to cite findings using only these IDs: `{"gap": "Expensive entry tier", "citations": ["SRC_02"]}` — never asked to reproduce or recall a URL from memory.
4. The backend deterministically resolves `SRC_02` → the real URL when building the final report. The LLM's job is pattern-matching "which tagged snippet supports this claim," which models are reliably good at — not "recall and reproduce a URL correctly," which they aren't.

This is a small amount of bookkeeping that removes an entire class of hallucination risk. It's also a good, concrete thing to point to later: "the system is structurally incapable of citing a source that doesn't exist, because the LLM never handles raw URLs."

---

## 4. Data Ingestion Strategy (Keep It Simple First)

The temptation is to build a robust scraper (headless browser, anti-bot handling, JS-rendering support) up front. Don't — start simple and only add complexity where you actually hit a wall:

1. **Primary source**: search API results (e.g. Tavily) — these already return cleaned snippets/summaries for most pages without you needing to scrape them yourself. This alone covers a large fraction of what you need.
2. **When you need a full page** (e.g. a specific competitor's pricing page): plain HTTP fetch + an HTML-to-text/Readability-style cleanup step to strip nav/footer/script clutter before it reaches the LLM. This works for a large share of normal server-rendered content.
3. **If a page is JS-rendered and returns empty content**: don't reach for a headless browser as the first fix. Options in order of effort: try a different search result that has the same info, rely on the search API's own snippet/summary of that page (it often already rendered it server-side for indexing), or skip that specific source — it's not worth the infra complexity of running a headless browser for a handful of pages.
4. **Headless browser (Playwright, etc.) is a last resort**, and if you do need it, it should run on EC2 (not Lambda) since it needs enough memory/disk that free-tier Lambda constraints make it fragile.

**Reddit specifically**: use Reddit's official API with OAuth (free tier exists for low-volume apps) — don't scrape Reddit directly, it gets IP-blocked quickly and breaks ToS.

---

## 5. Rate Limits & Cost Control

Groq's free tier is rate-limited per model (requests/min, tokens/min, requests/day, tokens/day), and the token-per-minute cap is usually the real bottleneck — a single call with a large chunk of raw scraped text can eat a big share of the per-minute budget by itself.

**Mitigations, baked into the design, not bolted on after hitting 429s:**
- **Model tiering**: Stage 1 relevance checks and simple extraction use a small/fast model with much higher limits (e.g. Llama 3.1 8B); only Gap Synthesis (and maybe Stage 2 deep extraction) uses the larger 70B model.
- **Trim input aggressively before it hits the LLM** — the Readability-style cleanup step in ingestion isn't just for readability, it's a token-budget necessity. Raw scraped pages can be 5-10x larger than the actual useful content.
- **Retry with backoff** on 429 responses, built into the worker from day one — treat rate limiting as an expected, normal condition to handle gracefully, not an error state.
- **Search API calls are also a scarce resource** on free tiers (often ~100/month) — the worker should log every search call made per job so you can see your actual consumption and tune query counts before you accidentally burn a month's quota in a handful of test runs during development.

---

## 6. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Agent orchestration | LangGraph | Explicit state, conditional/branching graphs, checkpointing support |
| LLM | Groq (Llama 3.1 8B for cheap steps, Llama 3.3 70B for synthesis) | Free tier, no card required, fast inference |
| Search | Tavily (or similar agentic-search API) | Built for LLM use, returns clean snippets |
| Reddit data | Reddit API (OAuth, free tier) | Legitimate, avoids IP-block/ToS issues of scraping |
| Backend API | FastAPI | Lightweight, async-friendly, easy to containerize |
| Queue | SQS (AWS free tier) | Decouples API from Worker, gives retry semantics |
| Job/state store | DynamoDB (AWS free tier) | Job status, progress, final report storage; also usable as LangGraph checkpoint backend |
| Worker | Long-lived Python process (not Lambda) | Avoids Lambda's 15-min hard cap and cold-start issues for long research runs |
| Containerization | Docker | Local/prod parity |
| Compute (deploy target) | EC2 (t2.micro/t3.micro, free tier) | Simple, matches local Docker setup closely, avoids Lambda packaging/timeout fights |
| CI/CD | GitHub Actions → ECR → EC2 redeploy | Automates build/test/deploy on push |
| Observability | CloudWatch logs + LangSmith free tier (tracing) | Debuggability for non-deterministic agent runs |

---

## 7. Build Sequence

1. **Local, synchronous, in-memory** — get the full agent graph working end-to-end as a script, no API, no queue, no persistence. Validate the relevance filter and source-map citation approach here first, since those are the highest-risk/most-novel parts.
2. **Wrap in FastAPI, still synchronous** — a single `/research` endpoint that blocks until done. Fine for local testing even though it won't survive as the production shape.
3. **Add the job/queue/worker split locally** — SQLite or DynamoDB Local for the job store, a simple in-process or local-queue-based worker, `POST /research` + `GET /research/{job_id}` polling. This is where the real target architecture gets proven out, still entirely on your machine.
4. **Dockerize** — API and Worker as separate containers (they scale/fail independently), `docker-compose up` running both plus a local queue/DB stand-in.
5. **Deploy to AWS free tier** — EC2 running the containers, real SQS + DynamoDB, CloudWatch logging.
6. **CI/CD + observability layer** — GitHub Actions pipeline, LangSmith tracing wired in.

---

## 8. Open Questions / Decisions Still Needed

- Exact embedding model or small-model choice for Stage 1 relevance filtering — needs a quick spike to compare cost/accuracy tradeoff.
- How progress updates get surfaced during polling — a fixed set of stage labels ("searching," "filtering," "synthesizing") vs. more granular per-agent messages.
- Whether Stage 1 relevance uses embeddings, a small LLM call, or both (e.g. embeddings as a fast pre-filter, small LLM as a second pass on borderline cases).
