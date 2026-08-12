def build_report_prompt(
    landscape: str,
    competitors_text: str,
    clusters_text: str,
    gaps: str,
    positioning: str,
) -> str:
    """Build the prompt for the report formatting LLM call."""
    return f"""You are an expert product strategist presenting market research to a founder.
You will be given a landscape summary, competitor profiles, pain point clusters, market gaps,
and positioning suggestions.

Your task is to write a clean, highly readable Markdown report.

CRITICAL INSTRUCTIONS ON CITATIONS:
- NEVER format your own markdown links (e.g. do not write `[1](url)` or `[source](url)`).
- YOU MUST ONLY use the exact `[SRC_COMP_X]` or `[SRC_PAIN_X]` tags provided in the input text.
- Place these tags inline where relevant (e.g. "Users complain about pricing [SRC_PAIN_0]").
- The backend will strictly search for these tags to replace them with real links. If you alter the format or invent a fake tag like `[SRC_1234]`, the citation will break.

Structure your report as follows:

# Market Research Report

## Landscape Summary
[Write the landscape summary here, polishing it for flow]

## Competitor Profiles
[For each competitor, create a heading with their name and include:
- Pricing model
- Key features (bullet list)
- Positioning / value proposition
- Weaknesses relevant to the user's idea
Keep it concise — 3-5 bullet points per competitor.]

## Pain Points & User Frustrations
[For each pain point, list the core problem and include:
- Brief description of the pain point
- Representative quotes or text with their exact `[SRC_PAIN_X]` tags]

## Market Gaps
[For each gap, write a clear heading, the description, and the evidence.
Use bullet points for readability. Include the competitors that fail to address it
and the confidence level.]

## Positioning Suggestions
[If positioning suggestions are available, list them as actionable recommendations
the founder could use to differentiate their product.]

---

INPUT DATA FOR THE REPORT:

LANDSCAPE SUMMARY:
{landscape}

COMPETITOR PROFILES:
{competitors_text}

PAIN POINTS:
{clusters_text}

GAPS:
{gaps}

POSITIONING SUGGESTIONS:
{positioning}"""
