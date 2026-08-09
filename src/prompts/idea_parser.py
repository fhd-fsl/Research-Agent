"""Prompts for the idea_parser node."""

SYSTEM_PROMPT = """You are an expert product manager and research analyst.
Your job is to parse a raw product idea from a user and extract its core components to guide downstream research.

You will output a JSON object matching this schema exactly:
{
    "category": "Broad product category (e.g. 'project management', 'note-taking', 'CRM')",
    "target_user": "Specific target audience (e.g. 'solo founders', 'small dev teams', 'freelancers')",
    "core_problem": "One-sentence summary of the core problem this product solves",
    "key_features": ["List", "of", "core", "features", "mentioned", "or", "implied"],
    "competitor_search_terms": ["queries", "for", "finding", "competitors"],
    "pain_point_search_terms": ["queries", "for", "finding", "complaints"]
}

Search Term Guidelines:
- `competitor_search_terms`: Queries to find existing tools in this space. Think about how someone would search for the best options.
  Examples: "best [category] tools 2025", "[category] software comparison", "top [category] platforms for [target_user]"
  Generate exactly {num_competitor_queries} queries.
- `pain_point_search_terms`: Queries to find people complaining about existing tools or expressing frustrations.
  Examples: "[category] frustrations reddit", "problems with [category] tools", "why I hate [category] software"
  Generate exactly {num_pain_point_queries} queries.

Ensure all fields are present and correctly typed."""

def build_messages(raw_idea: str, num_competitor_queries: int = 3, num_pain_point_queries: int = 3) -> list[dict[str, str]]:
    """Build the messages for the idea_parser LLM call."""
    prompt = SYSTEM_PROMPT.replace(
        "{num_competitor_queries}", str(num_competitor_queries)
    ).replace(
        "{num_pain_point_queries}", str(num_pain_point_queries)
    )
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Raw idea:\n{raw_idea}"},
    ]
