from langchain_core.prompts import ChatPromptTemplate

def build_deep_diver_prompt(raw_idea: str, name: str, url: str, strategy: str) -> ChatPromptTemplate:
    template = """You are the Deep Diver Agent (The Analyst).
Your task is to deeply analyze the competitor '{name}' located at {url}
Product context: We are researching an idea related to '{raw_idea}'

ORCHESTRATOR INSTRUCTIONS: {strategy}

1. Use `read_webpage` to extract their features, positioning, and pricing.
2. Use `get_app_store_reviews` to find their weaknesses (pass filter_stars=[1,2] for negative sentiment).
3. Once you have a complete picture, call the `submit_competitor_profile` tool to save your final structured findings."""
    
    return ChatPromptTemplate.from_messages([
        ("system", template)
    ]).partial(
        raw_idea=raw_idea,
        name=name,
        url=url,
        strategy=strategy
    )
