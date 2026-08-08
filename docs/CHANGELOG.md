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
- Project documentation: `PROBLEM_BRIEF.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `CHANGELOG.md`
- Designed 9-node LangGraph agent pipeline with parallel competitor/pain-point branches
- Designed two-pass gap synthesis strategy (pain point clustering → cross-reference synthesis)
- Multi-provider LLM strategy (Gemini Flash, Groq, Cerebras, OpenRouter fallback)
- `ResearchState` schema with full type definitions
- Conditional app store review fetching (1-2 star reviews) inside competitor deep dive
- Depth settings (fast vs. deep) with concrete token/query budgets
