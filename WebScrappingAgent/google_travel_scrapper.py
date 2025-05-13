import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Playwright, Browser as PlaywrightBrowser, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Dict, List, Any
from browser_use import Browser, BrowserConfig, Agent
from .model import llm
from .prompt_task import get_hotel_extraction_task
import traceback
import asyncio
import json

load_dotenv()

class HotelScraperSync:
    def __init__(self, playwright_instance: Playwright):
        self.playwright: Playwright = playwright_instance
        self.browser_instance: Optional[PlaywrightBrowser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def init_browser(self, user_proxy=True, headless=False):
        print("Initializing browser (sync)...")
        browser_url = os.getenv("BRIGHT_DATA_BROWSER_URL")

        if user_proxy and browser_url:
            print(f"Connecting to browser via proxy: {browser_url}")
            try:
                self.browser_instance = self.playwright.chromium.connect(
                    browser_url,
                    timeout=120000
                )
                print("Connected to proxy browser.")
            except Exception as e:
                print(f"Error: Failed to connect to proxy browser: {e}")
                print("Falling back to local browser.")
                self.browser_instance = self.playwright.chromium.launch(headless=headless)
        else:
            if user_proxy and not browser_url:
                print("Warning: Proxy requested but BRIGHT_DATA_BROWSER_URL not set. Using local browser.")
            print(f"Launching local browser (headless={headless})...")
            self.browser_instance = self.playwright.chromium.launch(headless=headless)

        self.context = self.browser_instance.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            java_script_enabled=True,
        )
        self.context.grant_permissions(['geolocation'], origin="https://www.google.com")
        self.page = self.context.new_page()
        print("Browser initialized successfully (sync).")


    def search_hotels(self, location: str, check_in_date: str, check_out_date: str) -> Optional[str]:
        if not self.page:
            print("Error: Page is not initialized. Call init_browser first.")
            return None

        search_url = "https://www.google.com/travel/hotels"
        final_url = None

        try:
            print(f"Navigating to {search_url}...")
            self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            self.page.wait_for_timeout(3000)

            print(f"Inputting location: {location}")
            location_input_selectors = [
                'input[placeholder="Search for places, hotels and more"]',
                'input[aria-label="Search for places, hotels and more"]',
                'input[jsname="yrriRe"]',
                'input[role="combobox"][aria-expanded="true"]'
            ]
            location_input_el = None
            for selector in location_input_selectors:
                try:
                    location_input_el = self.page.wait_for_selector(selector, timeout=5000)
                    if location_input_el: break
                except PlaywrightTimeoutError:
                    print(f"Warning: Location selector failed: {selector}")
                    continue
            
            if not location_input_el:
                print("Error: Could not find the location input field.")
                self.page.screenshot(path="error_screenshot_location_input.png")
                return None

            location_input_el.fill("")
            location_input_el.click()
            self.page.keyboard.type(location, delay=100)
            self.page.wait_for_timeout(1500)
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(2500)

            print("Opening date picker...")
            date_picker_trigger_selectors = [
                'input[placeholder="Check-in"]', 'input[aria-label="Check-in"]',
                'input[jsname="yrriRe"][aria-label="Check-in"]'
            ]
            date_trigger_el = None
            for selector in date_picker_trigger_selectors:
                try:
                    date_trigger_el = self.page.wait_for_selector(selector, timeout=5000)
                    if date_trigger_el: break
                except PlaywrightTimeoutError:
                    print(f"Warning: Date trigger selector failed: {selector}")
                    continue

            if not date_trigger_el:
                print("Error: Could not find the date picker trigger element.")
                self.page.screenshot(path="error_screenshot_date_trigger.png")
                return None
            
            date_trigger_el.click()
            self.page.wait_for_timeout(3000)

            check_in_date_dom = f"div[data-iso='{check_in_date}']"
            check_out_date_dom = f"div[data-iso='{check_out_date}']"

            self.page.wait_for_selector(check_in_date_dom, timeout=10000).click()
            self.page.wait_for_timeout(500)
            print("Successfully selected Check-in date.")
            
            self.page.wait_for_selector(check_out_date_dom, timeout=10000).click()
            self.page.wait_for_timeout(500)
            print("Successfully selected Check-out date.")

            done_button_selectors = [
                "//button[.//span[text()='Done']]", "button:has-text('Done')",
                "//button[contains(., 'Done')]",
            ]
            done_button_el = None
            for selector in done_button_selectors:
                try:
                    done_button_el = self.page.locator(selector).first
                    done_button_el.wait_for(state="visible", timeout=5000)
                    if done_button_el: break
                except PlaywrightTimeoutError:
                    print(f"Warning: Done button selector failed: {selector}")
                    continue
            
            if done_button_el:
                done_button_el.click()
            else:
                print("Warning: Could not find 'Done' button.")

            print("Waiting for search results to load...")
            self.page.wait_for_timeout(3000)
            try:
                 self.page.wait_for_load_state('networkidle', timeout=25000)
            except PlaywrightTimeoutError:
                 print("Warning: Network idle state not reached, proceeding anyway.")

            final_url = self.page.url
            print(f"Search completed. Final URL: {final_url}")
            self.page.screenshot(path="travel_result_screenshot_sync.png", full_page=True)

        except PlaywrightTimeoutError as pe:
             print(f"Error: Timeout Error during hotel search: {pe}")
             if self.page: self.page.screenshot(path="error_screenshot_timeout_sync.png")
        except Exception as e:
            print(f"Error: An unexpected error occurred in search_hotels: {e}")
            traceback.print_exc()
            if self.page:
                try: self.page.screenshot(path="error_screenshot_general_sync.png")
                except Exception as se: print(f"Error taking screenshot: {se}")
        return final_url

    def shutdown_resources(self):
        print("Shutting down browser resources (sync)...")
        if self.page:
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
        print("Browser resources shutdown complete (sync).")


def generate_travel_search_url(
        user_proxy: bool,
        location: str,
        check_in_date: str,
        check_out_date: str
    ) -> Optional[str]:
    print(f"\nGenerating travel search URL (sync) for: '{location}'")
    hotel_scraper_bot_sync = None
    generated_url = None
    with sync_playwright() as p:
        try:
            hotel_scraper_bot_sync = HotelScraperSync(playwright_instance=p)
            hotel_scraper_bot_sync.init_browser(user_proxy=user_proxy)
            generated_url = hotel_scraper_bot_sync.search_hotels(
                location=location,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
            )
            if generated_url:
                print(f"Successfully generated hotel search URL: {generated_url}")
            else:
                print(f"Warning: Hotel search for {location} did not return a URL.")
        except Exception as e:
            print(f"Error in generate_travel_search_url_sync: {e}")
            traceback.print_exc()
        finally:
            if hotel_scraper_bot_sync:
                hotel_scraper_bot_sync.shutdown_resources()
    return generated_url


def extract_hotel_info(
    search_url: str,
    user_preferences: Optional[Dict[str, Any]]
) -> Optional[Any]:
    print(f"\nExtracting hotel info (sync) from: {search_url}")

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
            task_definition = get_hotel_extraction_task(current_search_url, current_user_preferences)
            
            hotel_agent = Agent(
                task=task_definition,
                browser=agent_browser_instance_async,
                llm=llm,
                initial_actions=setup_steps
            )
            hotel_history = await hotel_agent.run()

            final_result_method = getattr(hotel_history, 'final_result', None)
            if callable(final_result_method):
                return final_result_method()
            
            print("Warning: Agent result object does not have a callable 'final_result' method.")
            return hotel_history
        except Exception as e_async:
            print(f"Error during async agent execution for hotels: {e_async}")
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
                    print(f"Error closing agent browser (async context for hotels): {close_e_async}")
    
    try:
        result = asyncio.run(_run_agent_operations_async(search_url, user_preferences))
        return result
    except RuntimeError as e:
        print(f"RuntimeError encountered when trying to run agent operations for hotels: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"General Error in extract_hotel_info_sync: {e}")
        traceback.print_exc()
        return None


# def main_sync():
#     location = "Paris"
#     check_in = "2025-06-10"
#     check_out = "2025-06-15"
#     use_proxy_for_search = False
#     user_prefs_list_only = {
#         "price_max_per_night": 250,
#         "rating_min": 4.0,
#         "amenities": ["Free Wi-Fi", "Swimming pool"],
#         "number_of_guests": 2,
#         "currency": "EUR",
#         "max_results": 5
#     }
#     results_url = None
    
#     print("-" * 30)
#     print("STEP 1: Generating Google Travel Search URL (Sync)...")
#     results_url = generate_travel_search_url_sync(
#         use_proxy=use_proxy_for_search,
#         location=location,
#         check_in_date=check_in,
#         check_out_date=check_out
#     )

#     if results_url:
#         print(f"STEP 1 SUCCESS: URL generated: {results_url}")
#     else:
#         print("STEP 1 FAILED: Could not generate search URL.")
#         return
    
#     print("-" * 30)
#     print("\n" + "-" * 30)
#     print("STEP 2: Starting Agent Analysis (Sync)...")
#     print(f"Using Preferences: {user_prefs_list_only}")

#     extracted_data = extract_hotel_info_sync(results_url, user_prefs_list_only)

#     if extracted_data:
#         print("\nSTEP 2 SUCCESS: Agent Result:")
#         try:
#             print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
#         except (TypeError, OverflowError):
#             print(extracted_data)
#     else:
#         print("\nSTEP 2 FAILED: Agent did not return data or failed during execution.")
#     print("-" * 30)


# if __name__ == "__main__":
#     print("Starting Hotel Search & Agent Process (Sync)...")
#     main_sync()
#     print("\nProcess Complete (Sync).")