import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Playwright, Browser as PlaywrightBrowser, Page, BrowserContext
from typing import Optional, Dict, List, Any
from urllib.parse import quote_plus
import sys
from browser_use import Browser, BrowserConfig, Agent
from .model import llm
from .prompt_task import get_amazon_extraction_task
import json
import traceback
import asyncio

load_dotenv()

class AmazonPlaywrightScraperSync:
    def __init__(self, playwright_instance: Playwright, use_brightdata: bool = False):
        self.use_brightdata = use_brightdata
        self.playwright: Playwright = playwright_instance
        self.browser_instance: Optional[PlaywrightBrowser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.browser_url: Optional[str] = None

        if self.use_brightdata:
            self.browser_url = os.getenv("BRIGHT_DATA_BROWSER_URL")
            if not self.browser_url:
                print("Error: BRIGHT_DATA_BROWSER_URL not found in environment variables.")
                raise ValueError("BRIGHT_DATA_BROWSER_URL not set")

    def initialize_browser(self):
        try:
            if self.use_brightdata:
                if not self.browser_url:
                    raise ConnectionError("Bright Data browser URL is not set.")
                print(f"Connecting to Bright Data browser endpoint...")
                self.browser_instance = self.playwright.chromium.connect(
                    self.browser_url, timeout=120000
                )
                self.context = self.browser_instance.new_context()
            else:
                print("Launching local browser...")
                self.browser_instance = self.playwright.chromium.launch(headless=True)
                self.context = self.browser_instance.new_context()
            self.page = self.context.new_page()
            print("Browser initialized.")
        except Exception as e:
            print(f"Error during browser initialization: {e}")
            self.shutdown_resources()
            raise

    def navigate_to_search(self, query: str, domain: str = "in") -> Optional[str]:
        if not self.page or self.page.is_closed():
            print("Error: Page is not available.")
            return None

        search_url = f"https://www.amazon.{domain}/s?k={quote_plus(query)}"
        final_url: Optional[str] = None
        try:
            print(f"Navigating to: {search_url}")
            self.page.goto(search_url, wait_until='domcontentloaded', timeout=90000)
            final_url = self.page.url
            print(f"Navigation successful. Final URL: {final_url}")
        except Exception as e:
            print(f"Error during navigation: {e}")
        return final_url

    def shutdown_resources(self):
        print("Closing browser resources...")
        if self.page and not self.page.is_closed():
            try: self.page.close()
            except Exception: pass
        if self.context:
            try: self.context.close()
            except Exception: pass
        if self.browser_instance:
            try: self.browser_instance.close()
            except Exception: pass
        self.page = None
        self.context = None
        self.browser_instance = None
        print("Browser resources closed.")


def get_amazon_search_url(
    query: str,
    domain: str = "in",
    use_brightdata: bool = False
) -> Optional[str]:
    print(f"\nGetting Amazon URL for: '{query}' (domain: {domain}, proxy: {use_brightdata})")
    navigated_url = None
    with sync_playwright() as p:
        scraper = AmazonPlaywrightScraperSync(playwright_instance=p, use_brightdata=use_brightdata)
        try:
            scraper.initialize_browser()
            navigated_url = scraper.navigate_to_search(query=query, domain=domain)
        except Exception as e:
            print(f"Error in get_amazon_search_url_sync function: {e}")
        finally:
            scraper.shutdown_resources()
    return navigated_url

def extract_amazon_info(
    search_url: str,
    user_preferences: Optional[Dict[str, Any]]
) -> Optional[Any]:
    print(f"Extracting Amazon info from: {search_url}")

    async def _run_agent_operations_async(
        current_search_url: str,
        current_user_preferences: Optional[Dict[str, Any]]
    ) -> Optional[Any]:
        agent_browser_instance_async: Optional[Browser] = None
        try:
            edge_path_x86 = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            edge_path_x64 = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
            edge_executable_path = next((p for p in [edge_path_x86, edge_path_x64] if os.path.exists(p)), None)

            if edge_executable_path:
                browser_config = BrowserConfig(browser_type='edge', executable_path=edge_executable_path)
            else:
                print("Warning: Edge executable not found. Attempting default Edge launch.")
                browser_config = BrowserConfig(browser_type='edge')
            
            agent_browser_instance_async = Browser(config=browser_config)
            setup_steps: List[Dict] = [{"open_tab": {"url": current_search_url}}]
            task_definition = get_amazon_extraction_task(current_search_url, current_user_preferences)
            
            amazon_agent = Agent(
                task=task_definition,
                browser=agent_browser_instance_async,
                llm=llm,
                initial_actions=setup_steps
            )
            amazon_history = await amazon_agent.run()

            final_result_method = getattr(amazon_history, 'final_result', None)
            if callable(final_result_method):
                return final_result_method()
            
            print("Warning: Agent result object does not have a callable 'final_result' method.")
            return amazon_history
        except Exception as e_async:
            print(f"Error during async agent execution: {e_async}")
            traceback.print_exc()
            return None
        finally:
            if agent_browser_instance_async:
                try:
                    close_method = getattr(agent_browser_instance_async, 'close', None)
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    elif callable(close_method):
                        close_method()
                except Exception as close_e_async:
                    print(f"Error closing agent browser (async context): {close_e_async}")
    
    try:
        result = asyncio.run(_run_agent_operations_async(search_url, user_preferences))
        return result
    except RuntimeError as e:
        print(f"RuntimeError encountered when trying to run agent operations: {e}")
        traceback.print_exc()
        return None

# def main_sync():
#     USE_BRIGHTDATA_FOR_URL_GEN = False
#     SEARCH_QUERY = "noise cancelling headphones"
#     AMAZON_DOMAIN = "in"
#     AMAZON_PREFERENCES = {
#         "price_max": 15000,
#         "rating_min": 4.2,
#         "prime_eligible": True,
#         "currency_symbol": "₹",
#         "max_results": 3
#     }

#     print(f"--- Starting Main Sync Process ---")

#     final_url = get_amazon_search_url_sync(
#         query=SEARCH_QUERY,
#         domain=AMAZON_DOMAIN,
#         use_brightdata=USE_BRIGHTDATA_FOR_URL_GEN
#     )

#     product_info = None
#     if final_url:
#         print(f"\nProceeding to extract info from URL: {final_url}")
#         product_info = extract_amazon_info_sync(
#             search_url=final_url,
#             user_preferences=AMAZON_PREFERENCES
#         )
#     else:
#         print("\nSkipping Agent extraction because URL generation failed.")

#     print("\n--- Main Sync Process Result ---")
#     if product_info:
#         print(f"Extracted Product Info for query '{SEARCH_QUERY}':")
#         try:
#             print(json.dumps(product_info, indent=2, ensure_ascii=False))
#         except (TypeError, OverflowError):
#             print(product_info)
#     elif final_url:
#          print(f"Agent extraction failed or returned no data for URL: {final_url}")
#     else:
#          print(f"Failed to obtain both URL and product info for query '{SEARCH_QUERY}'.")

#     print("\n--- Main Sync Process Finished ---")


# if __name__ == "__main__":
#     try:
#         main_sync()
#     except Exception as e:
#          print(f"Critical error in main_sync: {e}")
#          traceback.print_exc()