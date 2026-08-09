"""Competitor Deep Dive Agent Node.

Fetches the full web page for the top N filtered competitors, cleans the HTML,
and uses Cerebras to extract a detailed profile. If the competitor has a mobile
app, it conditionally fetches 1-2 star reviews from the app store.

Also implements negative review targeting (ARCHITECTURE.md Section 6):
after extracting competitor names, fires additional Tavily queries for
negative sentiment to enrich the evidence base.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pydantic import BaseModel
import httpx
from bs4 import BeautifulSoup
from google_play_scraper import Sort, reviews, search
from readability import Document
from tavily import TavilyClient
from urllib.parse import urljoin, urlparse

from src.config.settings import get_settings
from src.graph.state import CompetitorProfile, ParsedIdea, ResearchState
from src.ingestion.source_map import SourceMap
from src.prompts.competitor_deep_dive import build_messages
from src.utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


def fetch_and_clean_page(url: str, llm_client: LLMClient | None = None) -> str:
    """Fetch a web page, optionally spider subpages using LLM, and clean using readability."""
    try:
        settings = get_settings()
        with httpx.Client(timeout=settings.http_timeout, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = client.get(url, headers=headers)
            response.raise_for_status()

            doc = Document(response.text)
            clean_html = doc.summary()
            soup = BeautifulSoup(clean_html, "html.parser")
            main_text = soup.get_text(separator="\n", strip=True)

            subpage_texts = []
            if llm_client:
                orig_soup = BeautifulSoup(response.text, "html.parser")
                links = []
                for a in orig_soup.find_all("a", href=True):
                    href = a["href"]
                    text = a.get_text(strip=True)
                    if href and text and not href.startswith(("javascript:", "mailto:", "tel:")):
                        full_url = urljoin(url, href)
                        if urlparse(full_url).netloc == urlparse(url).netloc:
                            links.append(f"{full_url} | {text}")
                
                # Deduplicate while preserving order
                links = list(dict.fromkeys(links))
                links_text = "\n".join(links[:100])
                
                if links_text:
                    try:
                        from src.prompts.subpage_navigator import build_messages as build_nav_messages
                        
                        class SubpageNavigationResult(BaseModel):
                            urls: list[str]
                            
                        nav_response = llm_client.complete(
                            task="subpage_navigation",
                            messages=build_nav_messages(links_text),
                            temperature=0.1,
                            response_model=SubpageNavigationResult
                        )
                        urls_to_fetch = nav_response.parse_pydantic(SubpageNavigationResult).urls[:3]
                        
                        if urls_to_fetch:
                            def fetch_subpage(sub_url: str) -> str:
                                try:
                                    sub_resp = client.get(sub_url, headers=headers)
                                    sub_resp.raise_for_status()
                                    sub_doc = Document(sub_resp.text)
                                    sub_soup = BeautifulSoup(sub_doc.summary(), "html.parser")
                                    return f"\n\n--- SUBPAGE: {sub_url} ---\n" + sub_soup.get_text(separator="\n", strip=True)
                                except Exception:
                                    return ""
                                    
                            with ThreadPoolExecutor(max_workers=3) as executor:
                                futures = {executor.submit(fetch_subpage, u): u for u in urls_to_fetch}
                                for future in as_completed(futures):
                                    subpage_texts.append(future.result())
                                    
                    except Exception as e:
                        logger.warning("Subpage navigation failed for %s: %s", url, e)

            final_text = main_text + "".join(subpage_texts)
            return final_text[:settings.max_html_chars]
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return ""


def fetch_google_play_reviews(app_name: str, country: str = "us") -> list[dict]:
    """Search Google Play for the app and fetch 1-2 star reviews."""
    try:
        # Search for the app
        search_results = search(
            app_name,
            lang="en",
            country=country,
        )
        if not search_results:
            return []

        # Take the top result
        app_id = search_results[0]["appId"]

        # Fetch 1-star reviews
        result_1, _ = reviews(
            app_id,
            lang='en',
            country=country,
            sort=Sort.NEWEST,
            count=10,
            filter_score_with=1
        )
        # Fetch 2-star reviews
        result_2, _ = reviews(
            app_id,
            lang='en',
            country=country,
            sort=Sort.NEWEST,
            count=10,
            filter_score_with=2
        )

        all_results = result_1 + result_2
        # Filter for 1-2 stars (sanity check) and take top 10
        negative_reviews = [
            {"score": r["score"], "content": r["content"], "store": "google_play"}
            for r in all_results if r["score"] in (1, 2)
        ][:10]

        return negative_reviews
    except Exception as e:
        logger.warning("Failed to fetch Google Play reviews for %s: %s", app_name, e)
        return []


def fetch_apple_app_store_reviews(app_store_id: str, country: str = "us") -> list[dict]:
    """Fetch 1-2 star reviews from Apple App Store via public RSS feed.

    See ARCHITECTURE.md Section 6: Apple RSS feed returns JSON, no auth required.
    Limited to ~50 most recent reviews, filtered client-side to 1-2 stars.
    """
    if not app_store_id:
        return []

    # Clean the ID — might come as "id123456789" or just "123456789"
    numeric_id = app_store_id.replace("id", "").strip()
    if not numeric_id.isdigit():
        return []

    url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={numeric_id}/sortby=mostrecent/json"
    try:
        settings = get_settings()
        with httpx.Client(timeout=settings.http_timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            data = response.json()

        entries = data.get("feed", {}).get("entry", [])
        negative_reviews = []
        for entry in entries:
            # Skip the metadata entry (first entry is usually app info)
            rating_data = entry.get("im:rating", {})
            if not rating_data:
                continue
            try:
                rating = int(rating_data.get("label", "0"))
            except (ValueError, TypeError):
                continue

            if rating in (1, 2):
                content = entry.get("content", {}).get("label", "")
                if content:
                    negative_reviews.append({
                        "score": rating,
                        "content": content[:500],
                        "store": "apple",
                    })

        return negative_reviews[:10]
    except Exception as e:
        logger.warning("Failed to fetch Apple App Store reviews for ID %s: %s", app_store_id, e)
        return []


def _run_negative_sentiment_queries(
    competitor_name: str, source_map: SourceMap, tavily_client: TavilyClient
) -> tuple[dict[str, dict], list[str]]:
    """Fire Tavily queries targeting negative reviews for a specific competitor.

    Returns (new_sources_dict, list_of_weakness_snippets).
    See ARCHITECTURE.md Section 6: Negative Review Targeting.
    """
    queries = [
        f'"{competitor_name}" review "1 star" OR "terrible" OR "disappointed"',
        f'"{competitor_name}" problems OR issues OR complaints',
        f'"alternative to {competitor_name}" OR "{competitor_name} vs"',
        f'site:trustpilot.com "{competitor_name}"',
    ]

    new_sources = {}
    weakness_snippets = []

    for query in queries:
        try:
            response = tavily_client.search(
                query=query,
                search_depth="basic",
                max_results=3,
            )
            for result in response.get("results", []):
                url = result.get("url", "")
                title = result.get("title", "")
                snippet = result.get("content", "")
                if not url or not snippet:
                    continue

                src_id = source_map.add(
                    url=url,
                    title=title,
                    snippet=snippet,
                    source_type="web",
                )
                new_sources[src_id] = source_map.get(src_id)
                weakness_snippets.append(snippet[:300])
        except Exception as e:
            logger.warning("Negative sentiment query failed for '%s': %s", query, e)

    return new_sources, weakness_snippets


class CompetitorExtraction(BaseModel):
    """Pydantic model for the competitor extraction LLM output."""
    name: str
    pricing: str
    features: list[str]
    positioning: str
    weaknesses: list[str]
    has_mobile_app: bool
    app_store_id: str | None = None


def _format_idea_context(parsed_idea: ParsedIdea) -> str:
    """Format the parsed idea into a context string for the deep dive prompt."""
    return (
        f"Category: {parsed_idea.category}\n"
        f"Target User: {parsed_idea.target_user}\n"
        f"Core Problem: {parsed_idea.core_problem}\n"
        f"Country Code: {parsed_idea.target_country_code}"
    )


def _process_competitor(
    client: LLMClient,
    cand: dict,
    source_map: SourceMap,
    idea_context: str,
    tavily_client: TavilyClient | None,
) -> dict:
    """Fetch page, extract profile, fetch app reviews, and run negative sentiment queries."""
    url = cand["candidate"]["url"]
    src_id = cand["candidate"]["src_id"]

    # 1. Fetch and clean
    content = fetch_and_clean_page(url, llm_client=client)
    if not content:
        # Fallback to the snippet if full fetch fails
        content = cand["candidate"]["snippet"]

    # 2. Extract profile (now with idea context)
    messages = build_messages(content, idea_context=idea_context)
    try:
        response = client.complete(
            task="competitor_extraction",
            messages=messages,
            temperature=0.1,
            response_model=CompetitorExtraction,
        )
        parsed = response.parse_pydantic(CompetitorExtraction)
        tokens = response.input_tokens + response.output_tokens
        provider = response.provider
    except Exception as e:
        logger.error("Extraction failed for %s: %s", url, e)
        return {"success": False, "tokens": 0, "provider": "unknown", "new_sources": {}}

    name = parsed.name or cand["candidate"]["name"]
    has_app = parsed.has_mobile_app

    # 3. Conditional app reviews — now with SRC_IDs
    app_reviews = []
    new_sources = {}
    country_code = idea_context.split("Country Code: ")[-1].strip() if "Country Code: " in idea_context else "us"

    if has_app:
        # Google Play reviews
        gplay_reviews = fetch_google_play_reviews(name, country=country_code)
        for review in gplay_reviews:
            review_src_id = source_map.add(
                url=f"https://play.google.com/store/apps (search: {name})",
                title=f"Google Play Review — {name} ({review['score']} star)",
                snippet=review["content"][:300],
                source_type="app_store",
            )
            new_sources[review_src_id] = source_map.get(review_src_id)
            review["src_id"] = review_src_id
            app_reviews.append(review)

        # Apple App Store reviews (via RSS)
        apple_id = parsed.app_store_id
        if apple_id:
            apple_reviews = fetch_apple_app_store_reviews(apple_id, country=country_code)
            for review in apple_reviews:
                review_src_id = source_map.add(
                    url=f"https://apps.apple.com/app/id{apple_id.replace('id', '')}",
                    title=f"Apple App Store Review — {name} ({review['score']} star)",
                    snippet=review["content"][:300],
                    source_type="app_store",
                )
                new_sources[review_src_id] = source_map.get(review_src_id)
                review["src_id"] = review_src_id
                app_reviews.append(review)

    # 4. Negative review targeting queries
    if tavily_client and name:
        neg_sources, _weakness_snippets = _run_negative_sentiment_queries(
            name, source_map, tavily_client
        )
        new_sources.update(neg_sources)

    profile = CompetitorProfile(
        src_ids=[src_id],
        name=name,
        url=url,
        pricing=parsed.pricing,
        features=parsed.features,
        positioning=parsed.positioning,
        weaknesses=parsed.weaknesses,
        has_mobile_app=has_app,
        app_store_reviews=app_reviews,
    )

    return {
        "success": True,
        "profile": profile,
        "tokens": tokens,
        "provider": provider,
        "new_sources": new_sources,
    }


def competitor_deep_dive(state: ResearchState) -> dict:
    """Run deep extraction on the top N filtered competitors."""
    filtered = state.get("filtered_competitors", [])
    if not filtered:
        return {
            "competitor_profiles": [],
            "progress_messages": ["No filtered competitors for deep dive."],
        }

    depth = state.get("depth", "fast")
    max_competitors = 3 if depth == "fast" else 5

    # Take top N
    to_process = filtered[:max_competitors]

    client = LLMClient()
    # Read the existing source map so we can access URLs.
    source_map_dict = state.get("source_map", {})
    source_map = SourceMap(existing_map=source_map_dict)

    # Build idea context for the deep dive prompt
    parsed_idea = state.get("parsed_idea")
    idea_context = _format_idea_context(parsed_idea) if parsed_idea else ""  # type: ignore

    # Set up Tavily client for negative sentiment queries
    settings = get_settings()
    api_key = settings.tavily_api_key or os.environ.get("TAVILY_API_KEY")
    tavily_client = TavilyClient(api_key=api_key) if api_key else None

    # Reconstruct the candidate dictionary that _process_competitor expects
    candidates = []
    for cand in to_process:
        # Access url from source map using src_id
        try:
            url = source_map.resolve(cand["src_id"])
            candidates.append({
                "candidate": {
                    "src_id": cand["src_id"],
                    "url": url,
                    "name": cand["name"],
                    "snippet": ""  # not strictly needed if we fetch full page
                }
            })
        except KeyError:
            continue

    profiles = []
    total_tokens: dict[str, int] = {}
    all_new_sources: dict = {}

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = []
        for cand in candidates:
            futures.append(
                executor.submit(
                    _process_competitor, client, cand, source_map, idea_context, tavily_client
                )
            )

        for future in as_completed(futures):
            res = future.result()
            if res.get("success"):
                profiles.append(res["profile"])
                provider = res["provider"]
                total_tokens[provider] = total_tokens.get(provider, 0) + res["tokens"]
                all_new_sources.update(res.get("new_sources", {}))

    return {
        "competitor_profiles": profiles,
        "source_map": all_new_sources,
        "token_usage": total_tokens,
        "progress_messages": [f"Extracted deep profiles for {len(profiles)} competitors."]
    }
