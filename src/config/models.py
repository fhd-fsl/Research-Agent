"""Model-per-task routing configuration.

Each task maps to a primary provider and model. When the primary provider
is rate-limited (429), the system falls back to OpenRouter automatically.

See ARCHITECTURE.md Section 2 (Node Responsibilities) for why each task
uses its assigned provider.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskModelConfig:
    """Provider + model assignment for a single task."""
    provider: str
    model: str


# Task name → primary provider + model
# These task names are referenced by agent nodes when calling LLMClient.complete()
MODEL_FOR_TASK: dict[str, TaskModelConfig] = {
    "idea_parsing":          TaskModelConfig(provider="gemini",   model="gemini-2.0-flash"),
    "relevance_filter":      TaskModelConfig(provider="groq",     model="llama-3.1-8b-instant"),
    "competitor_extraction":  TaskModelConfig(provider="cerebras", model="gemma-4-31b"),
    "pain_point_clustering": TaskModelConfig(provider="groq",     model="llama-3.1-8b-instant"),
    "gap_synthesis":         TaskModelConfig(provider="gemini",   model="gemini-2.0-flash"),
    "report_formatting":     TaskModelConfig(provider="groq",     model="llama-3.1-8b-instant"),
}

# Fallback provider when the primary returns 429 or is unavailable
FALLBACK_PROVIDER = "openrouter"

# Explicit mapping from primary model → OpenRouter equivalent
# Used when falling back to OpenRouter. Avoids brittle substring matching.
OPENROUTER_MODEL_MAP: dict[str, str] = {
    "gemini-2.0-flash": "openai/gpt-4o-mini",
    "llama-3.1-8b-instant": "meta-llama/llama-3.1-8b-instruct",
    "llama-3.3-70b": "meta-llama/llama-3.3-70b-instruct",
}
OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"

# Provider → OpenAI-compatible API base URL
# All four providers expose OpenAI-compatible chat/completions endpoints,
# so we use a single OpenAI SDK client per provider with different base URLs.
PROVIDER_BASE_URLS: dict[str, str] = {
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq":       "https://api.groq.com/openai/v1",
    "cerebras":   "https://api.cerebras.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}
