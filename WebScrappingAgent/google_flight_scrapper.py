from playwright.sync_api import sync_playwright
from browser_use import Agent, Browser, BrowserConfig
import asyncio
import threading
import traceback
from typing import List, Dict, Optional, Any, Callable
from dotenv import load_dotenv
import os
import json
import time
from .model import llm
from .prompt_task import get_flight_extraction_task

load_dotenv()


def run_async_in_thread(async_func: Callable, *args, **kwargs) -> Any:
    result_container = []
    exception_container = []
    def thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(async_func(*args, **kwargs))
            result_container.append(result)
        except Exception as e:
            exception_container.append(e)
        finally:
            loop.close()
    thread = threading.Thread(target=thread_target)
    thread.start()
    thread.join()
    if exception_container: raise exception_container[0]
    if result_container: return result_container[0]
    return None

class FlightFinder:
    def __init__(self):
        self.playwright = None
        self.browser_instance = None
        self.context = None
        self.page = None

    def initialize_browser(self, use_proxy=True):
        self.playwright = sync_playwright().start()
        if use_proxy and os.getenv("BRIGHT_DATA_BROWSER_URL"):
            print("Attempting proxy connection (sync - needs verification for Bright Data).")
            try:
                self.browser_instance = self.playwright.chromium.connect_over_cdp(os.getenv("BRIGHT_DATA_BROWSER_URL"))
            except Exception as e_proxy:
                print(f"Proxy connection failed: {e_proxy}. Falling back to direct launch.")
                self.browser_instance = self.playwright.chromium.launch(headless=False)
        else:
            self.browser_instance = self.playwright.chromium.launch(headless=False)
        self.context = self.browser_instance.new_context(viewport={"width": 1280, "height": 800})
        self.page = self.context.new_page()

    def input_airport(self, selector, airport):
        try:
            input_box = self.page.wait_for_selector(selector, timeout=20000)
            input_box.press("Control+a"); input_box.press("Delete")
            input_box.type(airport, delay=100)
            options = [f'li[role="option"][aria-label*="{airport}"]', f'li[role="option"] .zsRT0d:text-is("{airport}")', f'.zsRT0d:has-text("{airport}")']
            for option_selector in options:
                try:
                    item = self.page.wait_for_selector(option_selector, timeout=20000)
                    if item: item.click(); self.page.wait_for_load_state("networkidle", timeout=15000); return True
                except Exception: continue
            raise Exception(f"Unable to select airport: {airport}")
        except Exception as err:
            self.page.screenshot(path=f"error_sync_{airport.lower()}.png"); return False

    def perform_flight_search(self, source, target, departure_date, return_date):
        try:
            self.page.goto("https://www.google.com/flights", wait_until="networkidle", timeout=30000)
            if not self.input_airport('div[data-placeholder="Where from?"]', source): raise Exception("Failed to set origin")
            if not self.input_airport('div[data-placeholder="Where to?"]', target): raise Exception("Failed to set destination")
            self.page.query_selector('input[aria-label="Departure"]').click(); self.page.wait_for_timeout(1500)
            self.page.wait_for_selector(f'div[data-iso="{departure_date}"]', timeout=10000).click(); self.page.wait_for_timeout(1500)
            self.page.wait_for_selector(f'div[data-iso="{return_date}"]', timeout=10000).click(); self.page.wait_for_timeout(1500)
            try:
                self.page.wait_for_selector("button[aria-label^='Done.']", timeout=20000).click(); self.page.wait_for_timeout(1500)
                self.page.wait_for_selector("button[aria-label^='Search']", timeout=10000).click()
                self.page.wait_for_load_state("networkidle", timeout=30000)
            except Exception as e_button:
                self.page.screenshot(path="error_sync_search_button.png"); raise Exception(f"Done/Search button error: {e_button}")
            return self.page.url
        except Exception as e_search:
            self.page.screenshot(path="search_error_sync.png"); return None

    def shutdown(self):
        if self.page: self.page.close()
        if self.context: self.context.close()
        if self.browser_instance: self.browser_instance.close()
        if self.playwright: self.playwright.stop()
        self.playwright = None; self.context = None; self.browser_instance = None; self.page = None

def generate_search_url(from_airport, to_airport, depart_on, return_on):
    bot = None
    try:
        bot = FlightFinder()
        bot.initialize_browser(use_proxy=bool(os.getenv("BRIGHT_DATA_BROWSER_URL")))
        flight_url = bot.perform_flight_search(from_airport, to_airport, depart_on, return_on)
        if flight_url: return flight_url
    except Exception as e: print(f"Error in generate_search_url (sync): {e}")
    finally:
        if bot: bot.shutdown()
    return None

async def _async_extract_flight_logic(
    search_url: str, user_preferences: Optional[Dict[str, Any]],
    browser_config: BrowserConfig, llm_instance: Any
) -> Optional[Any]:
    headless_browser = None
    try:
        headless_browser = Browser(config=browser_config)
        setup_steps: List[Dict] = [{"open_tab": {"url": search_url}}]
        task_definition = get_flight_extraction_task(search_url, user_preferences)
        travel_agent = Agent(task=task_definition, browser=headless_browser, llm=llm_instance, initial_actions=setup_steps)
        flight_history = await travel_agent.run()
        final_result_method = getattr(flight_history, 'final_result', None)
        if callable(final_result_method): return final_result_method()
        return flight_history
    except Exception as e: print(f"Error within _async_extract_flight_logic: {e}"); traceback.print_exc(); return None
    finally:
        if headless_browser:
            try:
                close_method = getattr(headless_browser, 'close', None)
                if callable(close_method):
                    if asyncio.iscoroutinefunction(close_method): await close_method()
                    else: close_method()
            except Exception as close_e: print(f"Error closing agent browser (Async worker): {close_e}")

def extract_flight_info(
    search_url: str, user_preferences: Optional[Dict[str, Any]]
) -> Optional[Any]:
    global llm 
    if llm is None: print("ERROR: Global LLM instance not available for extract_flight_info."); return None
    edge_path_x86 = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    edge_path_x64 = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    edge_executable_path = next((p for p in [edge_path_x86, edge_path_x64] if os.path.exists(p)), None)
    browser_config = BrowserConfig(browser_type='edge', executable_path=edge_executable_path) if edge_executable_path else BrowserConfig(browser_type='edge')
    try:
        flight_data = run_async_in_thread(_async_extract_flight_logic, search_url, user_preferences, browser_config, llm)
        return flight_data
    except Exception as e: print(f"Error: Error during flight information extraction (Sync wrapper): {e}"); traceback.print_exc(); return None

# def main_flight_test_sync():
#     from_airport = "Kolkata"; to_airport = "London"
#     depart_on = "2025-08-01"; return_on = "2025-08-07" # Example dates
#     user_preferences = {"price_max": 95000, "stops_max": 1}
#     print("\nSTEP 1: Generating Flight Search URL (Sync)...")
#     search_url = generate_search_url(from_airport, to_airport, depart_on, return_on)
#     if search_url: print(f"\nSTEP 1 SUCCESS: URL: {search_url}")
#     else: print("\nSTEP 1 FAILED: Could not generate URL."); return
#     time.sleep(1)
#     print("\nSTEP 2: Extracting Flight Information (Sync wrapper)...")
#     flight_info = extract_flight_info(search_url, user_preferences)
#     if flight_info:
#         print("STEP 2 SUCCESS: Agent Result:")
#         try: print(json.dumps(flight_info, indent=2))
#         except TypeError: print(flight_info)
#     else: print("STEP 2 FAILED: No flight data returned.")

# if __name__ == "__main__":
#     if llm: main_flight_test_sync()
#     else: print("Cannot run test, Global LLM not initialized.")