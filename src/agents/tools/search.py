"""Web search tool wrapping Tavily."""

import logging
from langchain_core.tools import tool
from tavily import TavilyClient
from src.config.settings import get_settings
logger = logging.getLogger(__name__)

@tool
def search_web(query: str, max_results: int = None) -> str:
    """Search the web for real-time information, competitors, or pain points.
    
    Args:
        query: The search query to execute.
        max_results: The maximum number of results to return.
        
    Returns:
        A formatted string containing the URLs, titles, and snippets of the results.
    """
    settings = get_settings()
    if not settings.tavily_api_key:
        return "Error: TAVILY_API_KEY is not configured."
        
    client = TavilyClient(api_key=settings.tavily_api_key)
    try:
        settings = get_settings()
        limit = max_results if max_results is not None else settings.search_max_results
        
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=limit,
            include_answer=False,
            include_domains=[],
            exclude_domains=["g2.com", "capterra.com", "trustpilot.com", "getapp.com", "softwareadvice.com"],
        )
        
        results = response.get("results", [])
        if not results:
            return f"No results found for query: '{query}'"
            
        output = [f"Search Results for '{query}':"]
        for i, res in enumerate(results, 1):
            url = res.get("url", "")
            title = res.get("title", "")
            content = res.get("content", "")
            output.append(f"{i}. [{title}]({url})\n   Snippet: {content}")
            
        return "\n\n".join(output)
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return f"Error executing web search: {e}"
