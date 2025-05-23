from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
from config import (
    CHROME_DRIVER_MANUAL_PATH, 
    IMPLICIT_WAIT_SECONDS,
    VIDEO_SELECTOR_ID,
    SEARCH_BOX_NAME
)

class BrowserManager:
    def __init__(self, tts_manager=None):
        self.driver = None
        self.tts_manager = tts_manager

    def _speak(self, message, console_only=False):
        if self.tts_manager:
            self.tts_manager.speak(message, console_only=console_only)
        else:
            print(f"BROWSER: {message}")

    def setup_browser(self):
        self._speak("Setting up Webdriver.", console_only=True)
        try: 
            if not os.path.exists(CHROME_DRIVER_MANUAL_PATH):
                self._speak(f"ERROR: Chrome Driver application not found at {CHROME_DRIVER_MANUAL_PATH}", console_only=True)
                return False
            
            self._speak(f"Attempting to use Chrome Driver from: {CHROME_DRIVER_MANUAL_PATH}", console_only=True)
            service = ChromeService(executable_path=CHROME_DRIVER_MANUAL_PATH)
            chrome_options = webdriver.ChromeOptions()
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            self.driver.maximize_window()
            self.driver.implicitly_wait(IMPLICIT_WAIT_SECONDS)
            self._speak("Web driver initialized")
            return True
        
        except Exception as e: 
            self._speak(f"Fatal Error: Could not initialize Web driver:{e}")
            self.driver = None
            return False
    
    def get_current_url(self):
        if not self.driver: return None
        return self.driver.current_url
    
    def close_browser(self):
        if self.driver:
            self._speak("Closing Browser")
            self.driver.quit()
            self.driver = None

    def highlight_element(self, element, remove=False):
        if not self.driver or not element:
            return 
        try:
            border_style = "3px solid red" if not remove else ""
            self.driver.execute_script(f"arguments[0].style.border='{border_style}'", element)
        except Exception as e:
            self._speak(f"Error highlighting element: {e}", console_only=True)

    def click_element(self, element, title="Unknown Element"):
        if not self.driver or not element:
            return False
        
        try: 
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center', inline: 'center'});", element)
            time.sleep(0.2)

            clickable_element = WebDriverWait(self.driver, 7).until(
                EC.element_to_be_clickable(element))
            clickable_element.click()
            self._speak(f"Clicked (Standard) on: {title}")
            return True
        
        except Exception as e_std_click:
            self._speak(f"Standard click failed for '{title}'.Trying JavaScript click. Error: {e_std_click}", console_only=True)
            
            try: 
                self.driver.execute_script("arguments[0].click();", element)
                self._speak(f"Clicked (JavaScript) on: {title}")
                return True 
            except Exception as e_js_click:
                self._speak(f"JavaScript click also failed for '{title}'.Error: {e_js_click}")
                return False 
            
    def scroll_window(self, pixels):
        if not self.driver:
            return
        self._speak(f"Scrolling window by {pixels} pixels.", console_only=True)
        self.driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(1.5)

    def hover_element(self, element):
        if not self.driver or not element:
            return 
        
        try: 
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
        except Exception as e:
            self._speak(f"Error hovering over element: {e}", console_only=True)

    def visible_vedio_elements(self, timeout=15):
        if not self.driver:
            self._speak("Driver not available in visible_vedio_elements", console_only=True)
            return []
        
        self._speak(f"Attempting to find visible video elements using ID: '{VIDEO_SELECTOR_ID}'", console_only=True)
        visible_elements_list = []
        try: 
            locator_strategy = By.ID
            
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((locator_strategy, VIDEO_SELECTOR_ID)) 
            ) 
            time.sleep(1) 

            all_potential_elements = self.driver.find_elements(locator_strategy, VIDEO_SELECTOR_ID)
            
            if not all_potential_elements:
                self._speak(f"No elements found with selector '{VIDEO_SELECTOR_ID}' after explicit wait.", console_only=True)
                return []

            self._speak(f"Found {len(all_potential_elements)} raw elements with selector '{VIDEO_SELECTOR_ID}'. Filtering for display properties...", console_only=True)
            
            count_displayed_positive = 0
            for i, el in enumerate(all_potential_elements):
                try:
                    is_disp = el.is_displayed()
                    el_size = el.size
                    if is_disp:
                        count_displayed_positive += 1
                        if el_size.get('height', 0) > 0 and el_size.get('width', 0) > 0:
                            visible_elements_list.append(el)
                except Exception as e_filter:
                    self._speak(f"Error checking display status for element {i}: {e_filter}", console_only=True)
                    continue
            
            self._speak(f"{count_displayed_positive} elements reported is_displayed() as True.", console_only=True)
            if not visible_elements_list and all_potential_elements:
                self._speak(f"All {len(all_potential_elements)} raw elements were filtered out (not displayed or zero size).", console_only=True)
            elif visible_elements_list:
                self._speak(f"Successfully found {len(visible_elements_list)} visible video elements.", console_only=True)

            return visible_elements_list

        except Exception as e: 
            self._speak(f"General error or timeout in visible_vedio_elements for selector '{VIDEO_SELECTOR_ID}': {e}", console_only=True)
            return []       
    
    def navigate_and_search(self, base_url, search_term):
        if not self.driver:
            self._speak("Driver not available in navigate_and_search", console_only=True)
            return False
        
        self._speak(f"Navigating to YouTube and searching for: {search_term}")
        try:
            current_url_val = self.get_current_url()
            if current_url_val and current_url_val.startswith(base_url + "/watch"):
                self.driver.get(base_url)
                WebDriverWait(self.driver,10).until(EC.presence_of_element_located((By.NAME,SEARCH_BOX_NAME)))
            elif not current_url_val or not current_url_val.startswith(base_url):
                self.driver.get(base_url)
                WebDriverWait(self.driver,10).until(EC.presence_of_element_located((By.NAME,SEARCH_BOX_NAME)))
            
            search_box_locator = (By.NAME, SEARCH_BOX_NAME)
            search_box = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(search_box_locator)
            )

            search_box.clear()
            search_box.send_keys(search_term)
            search_box.send_keys(Keys.RETURN)

            self._speak(f"Searched for '{search_term}'. Waiting for results page to load...")
            
            locator_strategy_results = By.ID
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((locator_strategy_results, VIDEO_SELECTOR_ID)) 
            )
            time.sleep(1.5)
            self._speak("Search results page seems to have loaded.", console_only=True)
            return True
        
        except Exception as e:
            self._speak(f"Error during YouTube search for '{search_term}': {e}")
            return False