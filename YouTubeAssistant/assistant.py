import time
from config import (
    YOUTUBE_URL,
    SCROLL_AMOUNT_PX,
    HOVER_LISTEN_TIMEOUT_SECONDS,
    GENERAL_LISTEN_TIMEOUT_SECONDS,
    FUZZY_MATCH_THRESHOLD
)
from tts_manager import TTSManager
from voice_recognizer import VoiceRecognizer
from browser_manager import BrowserManager
from thefuzz import fuzz

class YouTubeVoiceAssistant:
    def __init__(self):
        self.tts = TTSManager()
        self.recognizer = VoiceRecognizer(self.tts)
        self.browser = BrowserManager(self.tts)
        self.hover_mode_active = True 
        self.last_hovered_element = None

    def _initial_youtube_setup(self):
        self.tts.speak("Navigating to YouTube. Please handle any consent popups manually during the 10 second pause.", console_only=True)
        if not self.browser.driver:
            self.tts.speak("Browser not set up, cannot navigate to YouTube.")
            return False
        try:
            self.browser.driver.get(YOUTUBE_URL)
        except Exception as e:
            self.tts.speak(f"Failed to navigate to YouTube: {e}")
            return False
        time.sleep(10)
        
        initial_search_query = "latest tech reviews"
        self.tts.speak(f"Performing initial search for: {initial_search_query}", console_only=True)
        if self.browser.navigate_and_search(YOUTUBE_URL, initial_search_query):
            self.hover_mode_active = True
        else:
            self.tts.speak("Failed to perform initial YouTube search. You can try searching via voice command.")
            self.hover_mode_active = False
        return True

    def _start_hover_and_listen_sequence(self):
        if not self.browser.driver:
            self.tts.speak("Driver not available for hover sequence.", console_only=True)
            return "no_driver"
        
        if not self.hover_mode_active:
            self.tts.speak("Hover mode is not active. Say 'start hover' to begin.", console_only=True)
            return "hover_mode_off"

        self.tts.speak("Starting hover sequence. Say 'play video' or 'stop'.", console_only=True)
        
        visible_video_elements = self.browser.visible_vedio_elements()

        if not visible_video_elements:
            self.tts.speak("No visible video titles found to hover over.")
            return "hover_completed_no_videos"

        self.tts.speak(f"Found {len(visible_video_elements)} visible videos to hover over.", console_only=True)

        for i, video_element in enumerate(visible_video_elements):
            self.last_hovered_element = video_element
            current_page_url = self.browser.get_current_url()
            if current_page_url and "watch?v=" in current_page_url:
                self.tts.speak("Page changed to a video, stopping hover sequence.", console_only=True)
                self.hover_mode_active = False
                if self.last_hovered_element: self.browser.highlight_element(self.last_hovered_element, remove=True)
                return "page_changed_to_video"
            try:
                video_title_attr = video_element.get_attribute('title')
                video_text_content = video_element.text
                video_title = video_title_attr if video_title_attr else video_text_content
                if not video_title: video_title = f"Video {i+1}"
                
                self.browser.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'});", 
                    video_element
                )
                time.sleep(0.4)

                print(f"Hovering over: {video_title.strip()}")
                self.browser.highlight_element(video_element)
                self.browser.hover_element(video_element)
                
                hover_command = self.recognizer.listen_for_command(listen_timeout=HOVER_LISTEN_TIMEOUT_SECONDS)
                
                self.browser.highlight_element(video_element, remove=True)
                self.last_hovered_element = None

                if not hover_command:
                    time.sleep(0.1)
                    continue

                if "stop" in hover_command:
                    self.tts.speak("Stopping hover sequence as per your command.")
                    self.hover_mode_active = False
                    return "hover_stopped_by_user"
                
                elif "play video" in hover_command or "play this video" in hover_command:
                    self.tts.speak(f"Command 'play video' received for: {video_title.strip()}")
                    if self.browser.click_element(video_element, video_title.strip()):
                        time.sleep(2) 
                        self.hover_mode_active = False
                        return "played_video"
                    else:
                        self.tts.speak(f"Failed to play '{video_title.strip()}'. Continuing hover.")
                else:
                    self.tts.speak(f"Command '{hover_command}' ignored during hover sequence. Continuing to next item. Say 'stop' to pause hovering.", console_only=True)
                
                time.sleep(0.1)
            except Exception as e_hover_item:
                if self.last_hovered_element: 
                    try: self.browser.highlight_element(self.last_hovered_element, remove=True)
                    except: pass
                self.last_hovered_element = None
                self.tts.speak(f"Error during hover or listen for video '{video_title if 'video_title' in locals() else 'N/A'}': {e_hover_item}", console_only=True)
                continue 
        
        if self.last_hovered_element: self.browser.highlight_element(self.last_hovered_element, remove=True)
        self.last_hovered_element = None
        self.tts.speak("Hover sequence completed (all items viewed).", console_only=True)
        return "hover_completed_all_items"

    def _handle_play_by_title_command(self, recognized_title_query):
        if not self.browser.driver:
            self.tts.speak("Browser not available to play by title.")
            return False

        self.tts.speak(f"Attempting to find and play video matching: '{recognized_title_query}'")
        visible_videos = self.browser.visible_vedio_elements()

        if not visible_videos:
            self.tts.speak("No videos found on the page to match against.")
            return False

        best_match_score = 0
        best_match_element = None
        best_match_title_text = ""

        for video_el in visible_videos:
            try:
                actual_title_attr = video_el.get_attribute('title')
                actual_title_content = video_el.text
                current_video_title_text = actual_title_attr if actual_title_attr else actual_title_content
                current_video_title_lower = current_video_title_text.strip().lower() if current_video_title_text else ""
                
                if not current_video_title_lower:
                    continue

                score = fuzz.token_sort_ratio(recognized_title_query.lower(), current_video_title_lower)
                print(f"  Comparing '{recognized_title_query}' with '{current_video_title_lower}': Score {score}")

                if score > best_match_score:
                    best_match_score = score
                    best_match_element = video_el
                    best_match_title_text = current_video_title_text 
            except Exception as e:
                self.tts.speak(f"Error processing a video element for title match: {e}", console_only=True)
                continue
        
        if best_match_element and best_match_score >= FUZZY_MATCH_THRESHOLD:
            self.tts.speak(f"Found best match: '{best_match_title_text.strip()}' with score {best_match_score}%. Playing it.")
            if self.browser.click_element(best_match_element, best_match_title_text.strip()):
                self.hover_mode_active = False
                time.sleep(2)
                return True
            else:
                self.tts.speak(f"Failed to click the matched video: '{best_match_title_text.strip()}'.")
        else:
            self.tts.speak(f"Sorry, I couldn't find a good match for '{recognized_title_query}' on this page. Best score was {best_match_score}%.")
        return False

    def _is_on_valid_hover_page(self):
        if not self.browser.driver: return False
        current_page_url = self.browser.get_current_url()
        return current_page_url and "watch?v=" not in current_page_url

    def run(self):
        if not self.browser.setup_browser():
            self.tts.speak("Browser setup failed. Exiting assistant.")
            return

        if not self._initial_youtube_setup():
             self.tts.speak("Initial YouTube setup failed.")
        
        self.tts.speak("\nWelcome to the Enhanced YouTube Voice Assistant!")
        self.tts.speak("Commands: scroll, search, play [title], start hover, stop (during hover), back, or exit.")

        running = True
        while running:
            self.tts.speak(f"\nListening for general command... (Hover mode: {'ON' if self.hover_mode_active else 'OFF'})", console_only=True)
            command = self.recognizer.listen_for_command(listen_timeout=GENERAL_LISTEN_TIMEOUT_SECONDS)
            
            if not command:
                continue

            action_taken_might_trigger_hover = False 

            if "exit" in command:
                self.tts.speak("Exiting assistant...")
                running = False
                continue

            elif "stop" in command: 
                if self.hover_mode_active:
                    self.tts.speak("Hover mode deactivated by general 'stop' command.")
                    self.hover_mode_active = False
                    if self.last_hovered_element:
                        try: self.browser.highlight_element(self.last_hovered_element, remove=True)
                        except: pass
                        self.last_hovered_element = None
                else:
                    self.tts.speak("Hover mode is already off.")
            
            elif "start hover" in command:
                if not self.hover_mode_active:
                    if self._is_on_valid_hover_page():
                        self.tts.speak("Activating hover mode.")
                        self.hover_mode_active = True
                        action_taken_might_trigger_hover = True 
                    else:
                        self.tts.speak("Cannot start hover on the current page (e.g., a video watch page).")
                else:
                    self.tts.speak("Hover mode is already active.")
                    if self._is_on_valid_hover_page():
                        action_taken_might_trigger_hover = True

            elif "back" in command:
                if self.browser.driver:
                    self.tts.speak("Going back to the previous page.")
                    self.browser.driver.back()
                    time.sleep(1.5) 
                    if self._is_on_valid_hover_page():
                        self.hover_mode_active = True 
                        action_taken_might_trigger_hover = True
                    else:
                        self.hover_mode_active = False
                        self.tts.speak("Landed on a video watch page after 'back', hover mode off.", console_only=True)
                else:
                    self.tts.speak("Browser not available to go back.")

            elif "scroll down" in command:
                self.browser.scroll_window(SCROLL_AMOUNT_PX)
                if self.hover_mode_active and self._is_on_valid_hover_page():
                    action_taken_might_trigger_hover = True
            elif "scroll up" in command:
                self.browser.scroll_window(-SCROLL_AMOUNT_PX)
                if self.hover_mode_active and self._is_on_valid_hover_page():
                    action_taken_might_trigger_hover = True

            elif command.startswith("search for"):
                try:
                    query = command.split("search for", 1)[1].strip()
                    if query:
                        if self.browser.navigate_and_search(YOUTUBE_URL, query):
                            self.hover_mode_active = True 
                            action_taken_might_trigger_hover = True
                    else:
                        self.tts.speak("No search query provided after 'search for'.")
                except IndexError:
                    self.tts.speak("Could not parse search query from 'search for' command.")
            
            elif command.startswith("play ") and "play video" not in command and "play this video" not in command:
                title_query = command.split("play", 1)[1].strip()
                if title_query:
                    self._handle_play_by_title_command(title_query)
                else:
                    self.tts.speak("Please specify a title after 'play'.")
            
            elif "play video" in command or "play this video" in command:
                if self.hover_mode_active and self._is_on_valid_hover_page():
                    self.tts.speak("Hover mode is ON. Starting hover sequence to find a video to play.")
                    action_taken_might_trigger_hover = True 
                elif not self.hover_mode_active:
                    self.tts.speak("Hover mode is off. Say 'start hover' or 'play [video title]'.")
                else: 
                    self.tts.speak("Cannot start hover to play video on the current page.")
                    self.hover_mode_active = False


            else:
                self.tts.speak(f"Command '{command}' not recognized.")

            if action_taken_might_trigger_hover and self.hover_mode_active and running:
                if self._is_on_valid_hover_page():
                    hover_result = self._start_hover_and_listen_sequence()
                    if hover_result == "hover_stopped_by_user" or \
                       hover_result == "played_video" or \
                       hover_result == "page_changed_to_video":
                        self.tts.speak(f"Hover sequence ended with: {hover_result}. Awaiting next command.", console_only=True)
                else: 
                    self.hover_mode_active = False 
                    self.tts.speak("Not on a valid page to start hover after action.", console_only=True)
        
        self.browser.close_browser()
        self.tts.speak("Assistant has shut down.")