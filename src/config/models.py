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
# These task names are referenced by agent nodes when calling LLMClient.complete() or get_chat_model()
MODEL_FOR_TASK: dict[str, TaskModelConfig] = {
    "orchestrator":          TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3-ultra-550b-a55b:free"),
    "searcher":              TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3-nano-30b-a3b:free"),
    "pain_diver":            TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3-ultra-550b-a55b:free"),
    "deep_diver":            TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3-ultra-550b-a55b:free"),
    "thinker":               TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3-ultra-550b-a55b:free"),
    "report_formatting":     TaskModelConfig(provider="openrouter",     model="nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3-nano-30b-a3b:free"),
}
