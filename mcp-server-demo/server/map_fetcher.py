import pandas as pd
import urllib.parse
import os
import re
import asyncio
import time
from typing import Dict, Any, Optional
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
    # CONFIGURATION
    # =========================================================================
    MAX_REVIEWS_TO_FETCH = 10
    HEADLESS_MODE = True     # Forced True for deployment

    # =========================================================================
    # ENGINE: SYNCHRONOUS SELENIUM LOGIC
    # =========================================================================
    class MapsScraperEngine:
        def __init__(self):
            # Configuration variables
            self.max_reviews = MAX_REVIEWS_TO_FETCH
            self.headless = HEADLESS_MODE

        # --- Scraper Helpers ---
        def _get_driver(self):
            """Initializes the Chrome WebDriver with Headless and stability settings."""
            chrome_options = Options()
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'
            
            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--window-size=1920,1080") 
                chrome_options.add_argument(f'user-agent={user_agent}')

            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=chrome_options)
        
        def _format_output(self, df: pd.DataFrame, user_query:str = "") -> str:
            """Formats the DataFrame result into a clean string output."""
            
            # --- FALLBACK PRINT LOGIC ---
            if len(df) == 1 and df['author'].iloc[0] == 'Google Summary':
                rating = df['rating'].iloc[0]
                try:
                     verdict = df['text'].iloc[0].split("Verdict: ")[1]
                except:
                     verdict = "N/A"
                     
                return (
                    f"input: ({user_query})\n\n"
                    f"🌍 Google Maps Review \n"
                    f"────────────────────────\n"
                    f"⚠️ NO INDIVIDUAL REVIEWS FOUND.\n"
                    f"⭐️ Overall Rating: {rating}/5.0\n"
                    f"📊 Verdict: {verdict}\n"
                    f"────────────────────────\n"
                )
            
            # --- FULL REVIEWS OUTPUT ---
            output = f"input: ({user_query})\n\n"
            output = f"🌍 Google Maps Review \n"
            output += f"───────────────────────\n"
            output += f"✅ Fetched {len(df)} Reviews:\n\n"
            
            for _, row in df.iterrows():
                output += f"👤 Author: {row['author']}\n"
                output += f"⭐ Rating: {row['rating']}/5.0\n"
                output += f"💬 Text: {row['text'][:1000]}...\n"
                output += "-" * 20 + "\n"
                
            return output

        # --- Core Synchronous Scraper ---
        def _scrape_reviews_force_sync(self, driver):
            """Core synchronous scraping function (called via asyncio.to_thread)."""
            wait = WebDriverWait(driver, 10)
            
            # 1. AGGRESSIVE TAB HUNTING
            tab_clicked = False
            strategies = [
                "//button[contains(@aria-label, 'Reviews')]",
                "//div[@role='tablist']//button[2]", 
                "//button[.//div[text()='Reviews']]"
            ]
            
            for xpath in strategies:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    if elements:
                        driver.execute_script("arguments[0].click();", elements[0])
                        tab_clicked = True
                        break
                except:
                    continue
            
            if not tab_clicked:
                try:
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        txt = btn.text
                        aria = btn.get_attribute("aria-label")
                        if (txt and "Reviews" in txt) or (aria and "Reviews" in aria):
                            driver.execute_script("arguments[0].click();", btn)
                            tab_clicked = True
                            break
                except:
                    pass

            time.sleep(7) # Wait for reviews to fully render

            # 2. SCROLL LOOP SETUP
            try:
                review_scroll_panel = driver.find_element(By.XPATH, "//div[starts-with(@aria-label, 'Reviews for') or @role='feed' or @data-h='reviews']")
            except:
                review_scroll_panel = None
            
            reviews_data = []
            iterations = 0
            max_iterations_without_data = 10 
            
            # 2. SCROLL LOOP EXECUTION
            while len(reviews_data) < self.max_reviews:
                iterations += 1
                cards = driver.find_elements(By.CSS_SELECTOR, "div[data-review-id]")
                if not cards:
                    cards = driver.find_elements(By.CLASS_NAME, "jftiEf")
                
                if review_scroll_panel:
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", review_scroll_panel)
                elif len(cards) > 0:
                    driver.execute_script("arguments[0].scrollIntoView(true);", cards[-1])
                else:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
                
                time.sleep(2)
                
                # --- FAILURE CHECK (AND FALLBACK RATING LOGIC) ---
                if len(cards) == 0:
                    if iterations >= max_iterations_without_data:
                        # ROBUST RATING EXTRACTOR (Fallback)
                        try:
                            rating_val = 0.0
                            rating_element = driver.find_element(By.XPATH, "//div[contains(@aria-label, 'star rating') or contains(@class, 'MW4etd')] | //span[contains(@aria-label, 'stars') and not(@role='img')]")
                            rating_text = rating_element.text or rating_element.get_attribute("aria-label")
                            match = re.search(r"(\d+\.\d+)", rating_text)
                            if match: rating_val = float(match.group(1))
                                
                            if rating_val > 0:
                                sentiment = "Neutral"
                                if rating_val >= 4.5: sentiment = "Excellent / Highly Recommended"
                                elif rating_val >= 4.0: sentiment = "Good / Positive"
                                elif rating_val >= 3.0: sentiment = "Average / Okay"
                                elif rating_val >= 2.0: sentiment = "Poor / Below Average"
                                else: sentiment = "Bad / Not Recommended"
                                
                                return pd.DataFrame([{
                                    "author": "Google Summary", "rating": rating_val,
                                    "text": f"Overall rating is {rating_val}. Verdict: {sentiment}", "date": "Today"
                                }])
                            else:
                                raise Exception("Rating value still 0 after all attempts")
                        except:
                            return pd.DataFrame() 
                        return pd.DataFrame()
                
                # Logic to keep scrolling
                current_count = len(cards)
                if current_count >= self.max_reviews: break
                if current_count > 0 and current_count == len(reviews_data):
                    if iterations > (max_iterations_without_data + 5): break
                if current_count > len(reviews_data):
                     reviews_data = [0] * current_count
                     iterations = 0 

            # 3. EXTRACTION
            all_cards = driver.find_elements(By.CSS_SELECTOR, "div[data-review-id]")
            if not all_cards:
                all_cards = driver.find_elements(By.CLASS_NAME, "jftiEf")
                
            final_data = []
            
            for card in all_cards[:self.max_reviews]:
                try:
                    author = card.get_attribute("aria-label") or "Unknown"
                    try: text = card.find_element(By.CLASS_NAME, "wiI7pd").text
                    except: text = "[No Text - Rating Only]"
                    try: 
                        rating_str = card.find_element(By.CSS_SELECTOR, "span[role='img']").get_attribute("aria-label")
                        rating = float(rating_str.split(" ")[0])
                    except: rating = 0.0
                    
                    final_data.append({"author": author, "rating": rating, "text": text, "date": "Recent"})
                except:
                    continue
                    
            return pd.DataFrame(final_data)

        def run_sync_scraper(self, user_query: str) -> pd.DataFrame:
            """Main synchronous execution flow."""
            driver = self._get_driver()
            try:
                # 1. Navigation
                encoded_query = urllib.parse.quote(user_query)
                url = f"https://www.google.com/maps/search/{encoded_query}" 
                driver.get(url)
                time.sleep(5) 

                # 2. Selection/Navigation
                if "/maps/place/" not in driver.current_url:
                    wait = WebDriverWait(driver, 10)
                    first_result = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "hfpxzc")))
                    driver.execute_script("arguments[0].click();", first_result)
                    time.sleep(5) 
                
                # 3. Scraping
                return self._scrape_reviews_force_sync(driver)
            
            except Exception as e:
                # Return empty DataFrame on error
                return pd.DataFrame() 
            finally:
                driver.quit()


    engine = MapsScraperEngine()

    # =========================================================================
    # THE ASYNCHRONOUS TOOL
    # =========================================================================
    @mcp.tool()
    async def fetch_reviews(query: str) -> str:
        """
        Fetches the latest Google Maps reviews for a specified place or business.
        Format: "Reviews for [Business Name]" (e.g., "Reviews for New York Public Library")
        """
        # 1. Parse Input
        pattern = r"(?:reviews\s+for|for)\s+(.+)$"
        match = re.search(pattern, query, re.IGNORECASE)

        if not match:
            # If the simple pattern doesn't work, just use the whole query
            place_name = query.strip()
        else:
            place_name = match.group(1).strip()

        if not place_name:
            return "⚠️ Invalid format. Please specify a place or business name."

        # 2. Execute Scraping (Blocking call must be run in a thread)
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, engine.run_sync_scraper, place_name)

        if df.empty:
            return f"❌ Error: Could not fetch reviews for '{place_name}'. The location may not exist or the scraper failed to find the elements."

        # 3. Final Formatting
        return engine._format_output(df)

    return fetch_reviews

# =========================================================================
# TEST EXECUTION
# =========================================================================
# if __name__ == "__main__":
#     import asyncio
    
#     # Mocking the FastMCP class needed for the register function
#     class MockTool:
#         def __init__(self, fn):
#             self.fn = fn
            
#     class MockToolManager:
#         def list_tools(self):
#             # Returns a list containing the registered tool function
#             return [MockTool(self.tool_func)]
        
#     class MockFastMCP:
#         def __init__(self, name):
#             self.name = name
#             self._tool_manager = MockToolManager()
#             self._tool_manager.tool_func = None
        
#         def tool(self):
#             def decorator(func):
#                 self._tool_manager.tool_func = func
#                 return func
#             return decorator

#     # Create test server
#     test = MockFastMCP("test_maps_scraper")
    
#     # Register the tools
#     register(test)
    
#     # Get the tool function to test it manually
#     tool_fn = test._tool_manager.list_tools()[0].fn
    
#     # --- Test Queries ---
#     # Query 1: Should fetch actual reviews (e.g., a popular restaurant)
#     test_query_1 = "Reviews for Times Square Diner, New York"
    
#     # Query 2: Should trigger the fallback (e.g., a place that often fails to load individual reviews)
#     test_query_2 = "Reviews for Eiffel Tower, Paris" 
    
#     print("\n" + "#"*50)
#     print(f"TEST 1: Fetching reviews for: '{test_query_1}'")
#     print("#"*50)
#     print(asyncio.run(tool_fn(test_query_1)))

#     print("\n" + "#"*50)
#     print(f"TEST 2: Fetching overall rating for: '{test_query_2}'")
#     print("#"*50)
#     print(asyncio.run(tool_fn(test_query_2)))