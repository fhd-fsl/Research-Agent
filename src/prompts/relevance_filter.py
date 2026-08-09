"""Prompts for the relevance filter nodes (Stage 1 filtering)."""

COMPETITOR_FILTER_SYSTEM = """You are a relevance filter for a product research system.
Your job is to determine if a search result is a direct or adjacent competitor to the user's product idea.

Ignore generic articles, unrelated products, and products that are entirely different categories.
It doesn't have to be a perfect match, but it should solve a similar core problem.

You will output a JSON object matching this schema exactly:
{
    "relevant": "YES", // or "NO" or "MAYBE"
    "reasoning": "One short sentence explaining why."
}"""

PAIN_POINT_FILTER_SYSTEM = """You are a relevance filter for a product research system.
Your job is to determine if a search result contains a genuine pain point, frustration, or complaint related to the user's product category or target audience.

Look for people expressing dissatisfaction, asking for alternatives, or struggling with existing solutions.
Ignore generic marketing copy, unrelated discussions, or purely positive reviews.

You will output a JSON object matching this schema exactly:
{
    "relevant": "YES", // or "NO" or "MAYBE"
    "reasoning": "One short sentence explaining why."
}"""

def build_competitor_messages(idea_summary: str, title: str, snippet: str) -> list[dict[str, str]]:
    """Build messages for the competitor relevance filter."""
    return [
        {"role": "system", "content": COMPETITOR_FILTER_SYSTEM},
        {"role": "user", "content": f"PRODUCT IDEA:\n{idea_summary}\n\nSEARCH RESULT:\nTitle: {title}\nSnippet: {snippet}"}
    ]

def build_pain_point_messages(idea_summary: str, title: str, snippet: str) -> list[dict[str, str]]:
    """Build messages for the pain point relevance filter."""
    return [
        {"role": "system", "content": PAIN_POINT_FILTER_SYSTEM},
        {"role": "user", "content": f"PRODUCT CATEGORY/TARGET:\n{idea_summary}\n\nSEARCH RESULT:\nTitle: {title}\nSnippet: {snippet}"}
    ]
