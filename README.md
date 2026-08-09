# Research Agent

An autonomous, multi-agent AI system built on LangGraph that takes a raw product idea, researches competitors, mines user pain points from forums, and synthesizes actionable market gaps and positioning strategies.

## Features

- **Competitor Deep Dive**: Searches the web for competitors, filters for relevance, and uses Cerebras to extract pricing, features, and weaknesses directly from competitor landing pages.
- **Pain Point Mining**: Searches Reddit, HackerNews, and the open web to find genuine user complaints and frustrations related to the problem space.
- **Gap Synthesis**: Cross-references competitor features with user pain points to mathematically identify unserved market gaps (e.g., strong pain point + majority of competitors failing to address it).
- **Multi-Provider Strategy**: Intelligently routes tasks to Gemini (for reasoning), Groq (for fast classification), and Cerebras (for token-heavy processing) to maximize free-tier API usage.
- **Markdown Reporting**: Generates a clean, highly readable Markdown report complete with automated citations linking back to original sources.

## Installation

This project uses modern Python (3.11+) and `uv` for dependency management.

1. Clone the repository
2. Create a virtual environment:
   ```bash
   uv venv
   ```
3. Activate the virtual environment:
   - Windows: `.\.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`
4. Install dependencies:
   ```bash
   uv pip install -r pyproject.toml
   # Or using standard pip: pip install -e .
   ```
5. Set up your environment variables:
   Copy `.env.example` to `.env` and fill in your API keys (Tavily, Gemini, Groq, Cerebras, OpenRouter).
   ```bash
   cp .env.example .env
   ```

## Usage

Run the agent from the command line by passing in your product idea:

```bash
# Standard "fast" run (3 competitors)
python -m src.main "I want to build an HR automation system that includes AI resume screening and leave management."

# Deep run (5 competitors, more pain point searches)
python -m src.main "I want to build an HR automation system..." --depth deep
```

The system will stream logs to the console as the LangGraph agents execute. Upon completion, a `Report.md` file will be generated in the root directory.

## Documentation

For a detailed breakdown of how the agent graph is constructed, how the heuristics work, and how to contribute, refer to the `docs/` folder:

- [ARCHITECTURE.md](docs/ARCHITECTURE.md): Full system architecture, graph structure, schemas, and provider fallback logic.
- [PROBLEM_BRIEF.md](docs/PROBLEM_BRIEF.md): The original problem statement and constraints.
- [CONVENTIONS.md](docs/CONVENTIONS.md): Coding standards and Git conventions.
- [CHANGELOG.md](docs/CHANGELOG.md): Record of all major pipeline and architecture changes.
