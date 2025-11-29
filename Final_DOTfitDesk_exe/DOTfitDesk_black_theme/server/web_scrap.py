import time
import re
import os
import asyncio
import pandas as pd
import urllib.parse
from typing import Dict, Any, Optional

# Selenium Imports
from selenium import webdriver # type: ignore
from selenium.webdriver.chrome.service import Service # type: ignore
from selenium.webdriver.chrome.options import Options # type: ignore
from selenium.webdriver.common.by import By # type: ignore
from selenium.webdriver.common.keys import Keys # type: ignore
from selenium.webdriver.support.ui import WebDriverWait # type: ignore
from selenium.webdriver.support import expected_conditions as EC # type: ignore 
from webdriver_manager.chrome import ChromeDriverManager # type: ignore

def register(mcp):
    # =========================================================================
    # CONFIGURATION (Updated for Web Search)
    # =========================================================================
    MAX_LINKS_TO_FETCH = 10 	# Total links to scrape/return
    PRINT_LIMIT = MAX_LINKS_TO_FETCH 	 	# How many to return in the string output
    # FIX: Set HEADLESS_MODE to True to prevent the browser window from opening
    HEADLESS_MODE = True 	# Set True for background running
    # CACHE_DIR removed as we are not saving files

    # =========================================================================
    # SCRAPER ENGINE (Browser & Logic Layer)
    # =========================================================================
    class ScraperEngine:
        def __init__(self):
            # No need for CACHE_DIR logic
            
            self.chrome_options = Options()
            if HEADLESS_MODE:
                # This option ensures the browser runs without a GUI
                self.chrome_options.add_argument("--headless=new") # Using '=new' for modern headless mode
                self.chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration for headless
                self.chrome_options.add_argument("--no-first-run")  # Skip first-run tasks
                self.chrome_options.add_argument("--no-default-browser-check")  # Skip browser checks
            self.chrome_options.add_argument("--no-sandbox")
            self.chrome_options.add_argument("--disable-dev-shm-usage")
            self.chrome_options.add_argument("--start-maximized")
            self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")  # Custom user agent

        def _get_driver(self):
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=self.chrome_options)

        # Removed _get_filenames method

        def _format_output(self, df, query, source="Fresh Web Search"):
            """Formats the top results into a readable string"""
            
            # --- MODIFIED: Output format for links ---
            output = [f"✅ Source: {source} | Query: '{query}' | Total Links: {len(df)} | Showing Top {PRINT_LIMIT}\n"]
            output.append("="*80)
            # output = output.pop(0)
            
            for i, row in df.head(PRINT_LIMIT).iterrows():
                try:
                    title = row.get('title', 'No Title')
                    url = row.get('url', 'No URL')
                    
                    output.append(f"Result #{i+1}")
                    output.append(f"🔗 Title: {title}")
                    output.append(f"🌐 URL: {url}")
                    output.append("-" * 50)
                except:
                    continue
            
            if len(df) > PRINT_LIMIT:
                output.append(f"... and {len(df) - PRINT_LIMIT} more links were found.")
            
            return "\n".join(output)

        def run(self, query: str) -> str:
            """Main synchronous entry point for web search"""
            
            driver = self._get_driver()
            wait = WebDriverWait(driver, 15)
            
            try:
                # Search
                encoded_query = urllib.parse.quote(query)
                # --- MODIFIED: Standard Google Search URL ---
                url = f"https://www.google.com/search?q={encoded_query}"
                driver.get(url)
                
                # Wait for search results to load
                try:
                    wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[@id='search']//a[h3]")))
                except:
                    time.sleep(2)  # Fallback: wait 2 seconds if element not found
                
                # We skip all the complex Maps logic and go straight to scraping
                return self._scrape_links(driver, query)

            except Exception as e:
                return f"❌ Critical Error during search: {str(e)}"
            finally:
                driver.quit()

        def _scrape_links(self, driver, query):
            """
            New method to scrape standard Google Search result links.
            It targets the primary result containers on a Google Search page.
            """
            all_links = []
            
            # Strategy: Find all link containers and extract href and title
            try:
                # Wait a bit more for dynamic content to load
                time.sleep(3)
                
                # Multiple selector strategies to handle different Google Search page layouts
                selectors_to_try = [
                    ("//div[@class='g']//a", "Div.g container"), # Standard results often work best first
                    ("//div[@id='search']//a[h3]", "Primary search container"),
                    ("//div[data-sokoban-container]//a[h3]", "Sokoban container"),
                    ("//a[contains(@href, '/url?q=')]", "URL parameter links"),
                ]
                
                for xpath_selector, description in selectors_to_try:
                    if len(all_links) >= MAX_LINKS_TO_FETCH:
                        break
                    
                    try:
                        link_elements = driver.find_elements(By.XPATH, xpath_selector)
                        
                        for i, link_elem in enumerate(link_elements):
                            if len(all_links) >= MAX_LINKS_TO_FETCH:
                                break
                                
                            try:
                                url = link_elem.get_attribute('href')
                                
                                # ---------------------------------------------------------
                                # 🚫 FILTERING LOGIC (The Fix)
                                # ---------------------------------------------------------
                                if not url: continue
                                
                                # 1. Remove Google Maps
                                if "maps.google.com" in url or "/maps" in url:
                                    continue
                                    
                                # 2. Remove Google Accounts/Support/Travel internal links
                                if "accounts.google.com" in url or "support.google.com" in url or "google.com/travel" in url:
                                    continue
                                
                                # 3. Standard clean up
                                if url.startswith('javascript:') or url.startswith('/'):
                                    continue
                                # ---------------------------------------------------------

                                if 'google.com/search' in url.lower() or 'google.com/url' in url.lower():
                                    # Extract actual URL from Google redirect
                                    if '/url?q=' in url:
                                        url = url.split('/url?q=')[1].split('&')[0]
                                        try:
                                            import urllib.parse
                                            url = urllib.parse.unquote(url)
                                        except:
                                            pass
                                
                                # Try to get title from h3 tag or other text
                                title = ""
                                try:
                                    title_elem = link_elem.find_element(By.TAG_NAME, 'h3')
                                    title = title_elem.text
                                except:
                                    pass
                                
                                if not title:
                                    title = link_elem.get_attribute('aria-label') or link_elem.text or 'No Title'
                                
                                # Clean up title
                                title = title.strip()
                                
                                # Double check we didn't get a map link after decoding
                                if "maps.google.com" in url:
                                    continue

                                if url and title and len(url) > 5 and title != "No Title":
                                    # Avoid duplicates
                                    if not any(d['url'] == url for d in all_links):
                                        all_links.append({"title": title, "url": url, "rank": len(all_links) + 1})
                                        # print(f"[DEBUG] Added link: {title[:30]}...")

                            except Exception as e:
                                continue
                    except Exception as e:
                        continue

            except Exception as e:
                return f"❌ Error during link extraction: {str(e)}"

            if not all_links:
                return "⚠️ No search results could be found or extracted. Try a different query."

            df = pd.DataFrame(all_links)
            
            return self._format_output(df, query, source="Fresh Web Search 🌐")

        # Removed _fallback_rating method (it was Maps-specific)

    engine = ScraperEngine()

    # =========================================================================
    # THE TOOL (New Tool Definition)
    # =========================================================================
    @mcp.tool()
    async def fetch_web_links(query: str) -> str:
        """
        Performs a Google Web Search and returns the top search result links. 
        Example: "best python libraries for scraping"
        """
        if not query.strip():
            return "❌ Query cannot be empty."

        # Run blocking Selenium in a separate thread to keep MCP async
        return await asyncio.to_thread(engine.run, query)

    return fetch_web_links

# =========================================================================
# TEST EXECUTION
# =========================================================================
# if __name__ == "__main__":
#     import asyncio
#     from mcp.server import FastMCP # type: ignore
    
#     # Create test server
#     test = FastMCP("test_web_scraper")
    
#     # Register the tools
#     register(test)
    
#     # Get the tool function to test it manually
#     tool = test._tool_manager.list_tools()[0]
    
#     print("--- 🌍 RUNNING TEST ---")
    
#     query = "MS. Dhoni" 
#     print(f"Query: {query}")
    
#     # Run the test
#     result = asyncio.run(tool.fn(query))
#     print(result)