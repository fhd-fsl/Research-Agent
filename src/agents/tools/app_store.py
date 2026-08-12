"""App Store reviews extraction tool."""

import logging
from langchain_core.tools import tool
from google_play_scraper import Sort, reviews, search
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

@tool
def get_app_store_reviews(app_name: str, filter_stars: list[int] = None) -> str:
    """Fetch Google Play app store reviews for a specific app to extract user sentiment and complaints.
    
    Args:
        app_name: The name of the app to search for (e.g. "Agiled CRM").
        filter_stars: A list of star ratings to filter by (e.g. [1, 2, 3]). Defaults to [1, 2] for negative sentiment.
        
    Returns:
        A formatted string of the most relevant reviews matching the star filters.
    """
    settings = get_settings()
    if filter_stars is None:
        filter_stars = settings.app_store_filter_stars
        
    try:
        search_results = search(
            app_name,
            lang="en",
            country="us",
            n_hits=1,
        )
        if not search_results:
            return f"No Google Play app found matching '{app_name}'."
            
        app_id = search_results[0]["appId"]
        
        result, _ = reviews(
            app_id,
            lang="en",
            country="us",
            sort=Sort.NEWEST,
            count=50,
        )
        
        filtered_reviews = [r for r in result if r["score"] in filter_stars]
        if not filtered_reviews:
            return f"App found ({app_id}), but no reviews match the star filter {filter_stars}."
            
        output = [f"Reviews for {app_id} (Stars: {filter_stars}):"]
        # Limit to top 15 to avoid token bloat
        for r in filtered_reviews[:15]:
            output.append(f"- {r['score']} Star: {r['content']}")
            
        return "\n".join(output)
        
    except Exception as e:
        logger.error("Google Play fetch failed: %s", e)
        return f"Error fetching Google Play reviews: {e}"
