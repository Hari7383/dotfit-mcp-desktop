import httpx
import re
import asyncio
import time
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

def register(mcp):
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    GOOGLE_NEWS_URL = "https://www.google.com/search?q={query}&tbm=nws"
    CACHE_TTL_SECONDS = 3600
    MAX_ARTICLES = 10
    PRINT_LIMIT = 5

    # News topic mappings
    NEWS_TOPICS = {
        'trichy': 'Trichy news today',
        'sports': 'sports news today',
        'technology': 'technology news today',
        'tech': 'technology news today',
        'cinema': 'cinema news today',
        'movies': 'movies news today',
        'finance': 'finance news',
        'business': 'business news today',
        'politics': 'politics news today',
        'health': 'health news today',
        'entertainment': 'entertainment news today',
        'world': 'world news today',
        'india': 'india news today',
    }

    # =========================================================================
    # DATA ENGINE (Caching Layer)
    # =========================================================================
    class DataEngine:
        def __init__(self):
            self._cache = {}
            self._expiry = {}
        
        def get(self, key):
            if key in self._cache and time.time() < self._expiry[key]:
                return self._cache[key]
            return None
            
        def set(self, key, value, ttl=CACHE_TTL_SECONDS):
            self._cache[key] = value
            self._expiry[key] = time.time() + ttl

    engine = DataEngine()

    async def fetch_json(url: str) -> Optional[Dict]:
        """Robust network fetcher with timeout handling"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                print(f"[DEBUG] JSON fetch failed: {str(e)}")
                return None

    async def fetch_html(url: str) -> Optional[str]:
        """Fetch HTML content with error handling"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                print(f"[DEBUG] HTML fetch failed: {str(e)}")
                return None

    async def parse_topic(user_query: str) -> Optional[str]:
        """Parse user query to identify the news topic"""
        query_lower = user_query.lower().strip()
        query_lower = query_lower.replace('today', '').replace('latest', '').strip()
        
        for topic_key in NEWS_TOPICS.keys():
            if topic_key in query_lower:
                return topic_key
        
        return None

    async def scrape_news(query: str) -> List[Dict]:
        """Scrapes news articles from Google News"""
        cache_key = f"news_{query.lower()}"
        
        # Check cache first
        if cached := engine.get(cache_key):
            return cached
        
        search_query = query.replace('today', '').replace('latest', '').strip()
        search_url = f"{GOOGLE_NEWS_URL.format(query=search_query.replace(' ', '+'))}"
        
        print(f"[DEBUG] Fetching from: {search_url}")
        
        html = await fetch_html(search_url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        articles = []
        
        # Find all links
        links = soup.find_all('a', href=True)
        print(f"[DEBUG] Found {len(links)} total links")
        
        for link in links:
            if len(articles) >= MAX_ARTICLES:
                break
            
            try:
                title = link.get_text(strip=True)
                url = link.get('href', '')
                
                # Filter for news-like content
                if (title and len(title) > 20 and len(title) < 300 and
                    url and len(url) > 10 and
                    not any(x in url.lower() for x in ['google.com/search', 'javascript:', '/search', 'maps.google', 'youtube.com', 'images.google'])):
                    
                    # Clean URL if it's a Google redirect
                    if '/url?q=' in url:
                        url = url.split('/url?q=')[1].split('&')[0]
                        try:
                            import urllib.parse
                            url = urllib.parse.unquote(url)
                        except:
                            pass
                    
                    if url.startswith('http'):
                        articles.append({
                            "title": title,
                            "url": url,
                            "source": "News Source",
                            "rank": len(articles) + 1
                        })
                        print(f"[DEBUG] Article added: {title[:50]}...")
            except Exception as e:
                continue
        
        # Cache the results
        if articles:
            engine.set(cache_key, articles)
        
        return articles

    def format_output(articles: List[Dict], topic: str) -> str:
        """Formats the articles into a readable string"""
        if not articles:
            return f"[ERROR] No news articles found for '{topic}'. Try a different topic."
        
        output = []
        output.append(f"[NEWS] Topic: '{topic}' | Total Articles: {len(articles)} | Showing Top {PRINT_LIMIT}")
        output.append("=" * 80)
        
        for i, article in enumerate(articles[:PRINT_LIMIT]):
            output.append(f"\n[Article #{i+1}]")
            output.append(f"Title: {article.get('title', 'No Title')}")
            output.append(f"URL: {article.get('url', 'No URL')}")
            output.append(f"Source: {article.get('source', 'Unknown')}")
            output.append("-" * 80)
        
        # if len(articles) > PRINT_LIMIT:
        #     output.append(f"\n... and {len(articles) - PRINT_LIMIT} more articles were found.")
        
        return "\n".join(output)

    # =========================================================================
    # THE TOOL
    # =========================================================================
    @mcp.tool()
    async def fetch_news(query: str) -> str:
        """
        Fetches latest news based on the specified topic.
        Examples:
        - "today trichy news" -> Latest Trichy news
        - "sports news" -> Latest sports news
        - "technology news" -> Latest technology news
        - "cinema news" -> Latest cinema news
        - "finance news" -> Latest finance news
        
        Supported topics: trichy, sports, technology, cinema, finance, business, 
        politics, health, entertainment, world, india
        """
        if not query.strip():
            return "[ERROR] Query cannot be empty."
        
        # Parse topic
        topic = await parse_topic(query)
        
        if topic is None:
            search_query = query.replace('today', '').replace('latest', '').strip()
            if not search_query:
                return "[ERROR] Please provide a valid news topic. Examples: 'today trichy news', 'sports news', 'finance news'"
            topic_display = search_query
        else:
            topic_display = NEWS_TOPICS[topic]
        
        # Fetch news
        articles = await scrape_news(topic_display)
        
        # Format and return
        return format_output(articles, topic_display)

    return fetch_news


# =========================================================================
# TEST EXECUTION
# =========================================================================
# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP # type: ignore
    
#     # Create test server
#     test = FastMCP("test_news_fetcher")
    
#     # Register the tools
#     register(test)
    
#     # Get the tool function to test it manually
#     tool = test._tool_manager.list_tools()[0]
    
#     print("=" * 80)
#     print("RUNNING NEWS FETCHER TEST")
#     print("=" * 80)
    
#     # Test different news topics
#     test_queries = [
#         "today trichy news",
#         "sports news",
#         "technology news",
#         "finance news",
#     ]
    
#     for query in test_queries:
#         print(f"\n{'='*80}")
#         print(f"Testing: {query}")
#         print(f"{'='*80}\n")
        
#         result = asyncio.run(tool.fn(query))
#         print(result)
        
#         time.sleep(1)
