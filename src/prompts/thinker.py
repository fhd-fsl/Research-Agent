from langchain_core.prompts import ChatPromptTemplate

def build_thinker_prompt(raw_idea: str, pp_text: str, competitors_text: str, strategy: str) -> ChatPromptTemplate:
    template = """You are the Thinker Agent (The Strategist).
Your task is to synthesize market research and find strategic gaps for the product idea: "{raw_idea}"

ORCHESTRATOR INSTRUCTIONS: {strategy}

Cross reference the competitor profiles and user pain points found earlier to identify gaps:

COMPETITOR PROFILES:
{competitors_text}

PAIN POINTS:
{pp_text}

Identify 2-3 major market gaps.
A valid gap must have evidence from both pain points (users want it) and competitors (they don't have it).
You must determine the 'confidence' of each gap (strong, moderate, weak) based on the evidence.
"""
    return ChatPromptTemplate.from_messages([
        ("system", template)
    ]).partial(
        raw_idea=raw_idea,
        strategy=strategy,
        competitors_text=competitors_text,
        pp_text=pp_text
    )
