"""Web reading tool for extracting clean text from URLs."""

import logging
import httpx
import urllib.parse
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from readability import Document
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

@tool
def read_webpage(url: str) -> str:
    """Fetch a web page and clean it to extract the main readable text.
    
    Args:
        url: The URL of the web page to read.
        
    Returns:
        The extracted clean text of the webpage along with a list of extracted internal links, so you can navigate the website by calling this tool again.
    """
    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.http_timeout, follow_redirects=True) as client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = client.get(url, headers=headers)
            response.raise_for_status()

            # Extract internal links from the raw HTML to capture nav bars
            raw_soup = BeautifulSoup(response.text, "html.parser")
            base_url = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
            internal_links = {}
            for a in raw_soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True)
                if not text:
                    continue
                    
                full_url = urllib.parse.urljoin(base_url, href)
                # Ensure it's an internal link
                if full_url.startswith(base_url):
                    # Dedup by URL
                    if full_url not in internal_links:
                        internal_links[full_url] = text

            # readability-lxml extracts the main article content
            doc = Document(response.text)
            clean_html = doc.summary()

            # Strip remaining HTML tags
            soup = BeautifulSoup(clean_html, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            
            # Format output
            output = text[:settings.max_html_chars]
            output += "\n\n--- INTERNAL LINKS (You can call this tool again with these URLs to explore) ---\n"
            for link_url, link_text in list(internal_links.items())[:settings.web_max_internal_links]:
                output += f"- {link_text}: {link_url}\n"

            return output
    except Exception as e:
        logger.error("Failed to read webpage %s: %s", url, e)
        return f"Error reading webpage: {e}"
