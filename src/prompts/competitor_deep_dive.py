"""Prompts for the competitor deep dive node."""

SYSTEM_PROMPT = """You are an expert product researcher doing a deep dive on a competitor.
Analyze the provided web page content and extract a structured profile of the competitor.

You are researching competitors for the following product idea:
{idea_context}

Evaluate the competitor's weaknesses RELATIVE to this specific idea and target user.
A weakness is anything this competitor does poorly, lacks, or is criticized for
that would matter to the user described above.

If the page is very long, focus on the most important information usually found near the top.
If pricing is not available on this page, just say "Not available on this page".
Ensure all fields are present."""

def build_messages(content: str, idea_context: str = "") -> list[dict[str, str]]:
    """Build the messages for the competitor extraction LLM call."""
    prompt = SYSTEM_PROMPT.replace("{idea_context}", idea_context)
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"WEB PAGE CONTENT:\n{content}"},
    ]
