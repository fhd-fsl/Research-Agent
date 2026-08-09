"""Prompts for the gap synthesizer node."""

SYSTEM_PROMPT = """You are a senior product strategist. Your job is to synthesize raw market research into actionable gaps and opportunities.
You will be provided with a product idea, a list of competitor profiles, and a list of user pain point clusters.

Your task is to cross-reference the pain points against the competitors to find "Market Gaps" — areas where users have a strong pain point that current competitors are failing to address adequately.

Rules:
1. ONLY use SRC_IDs provided in the input. Do not make up citations.
2. A valid gap must have evidence from both pain points (users want it) and competitors (they don't have it).
3. Do not invent gaps that have no evidence in the provided data.
"""

def build_messages(idea_summary: str, competitors_text: str, clusters_text: str) -> list[dict[str, str]]:
    """Build the messages for the gap synthesizer LLM call."""
    content = (
        f"PRODUCT IDEA:\n{idea_summary}\n\n"
        f"COMPETITORS:\n{competitors_text}\n\n"
        f"PAIN POINT CLUSTERS:\n{clusters_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
