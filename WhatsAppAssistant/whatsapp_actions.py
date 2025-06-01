import os
import subprocess
import pyautogui
import time
import pytesseract
import config
from PIL import ImageGrab, ImageOps
from conversation_history_manager import ConversationHistoryManager
from message_manager import MessageAgentLLM
import re
from typing import Optional

class WhatsAppActions:
    def __init__(self, whatsapp_path, speaker, google_api_key=None):
        self.whatsapp_path = whatsapp_path
        self.speaker = speaker
        self.history_manager = ConversationHistoryManager(history_file_path=config.CONVERSATION_MEMORY_PATH)
        self.agent = MessageAgentLLM(speaker=self.speaker,history_manager=self.history_manager,google_api_key=google_api_key)
        self.current_mic_button_location = None

    def find_and_click(self, image_path, confidence=0.8, region=None, clicks=1, button='left', max_wait_secs=5):
        start_time = time.time()
        location = None
        while time.time() - start_time < max_wait_secs:
            try:
                location = pyautogui.locateCenterOnScreen(image_path, confidence=confidence, region=region)
                if location:
                    pyautogui.moveTo(location, duration=0.1)
                    pyautogui.click(clicks=clicks, button=button)
                    return location
                time.sleep(0.2)
            except pyautogui.ImageNotFoundException: 
                pass
            except Exception as e:
                print(f"Error in find_and_click for {os.path.basename(image_path)}: {e}")
                return None
        if max_wait_secs > 1 and not location: 
            self.speaker.speak(f"Could not find UI element: {os.path.basename(image_path)} after {max_wait_secs}s.")
        return None

    def open_whatsapp_window(self):
        try:
            active_window = pyautogui.getActiveWindow()
            if active_window and ("whatsapp" in active_window.title.lower()):
                if not active_window.isMaximized: 
                    active_window.maximize()
                active_window.activate()
                time.sleep(0.5)
                return True
        except Exception: pass

        self.speaker.speak("Opening WhatsApp...")
        launch_command_issued = False
        
        if self.whatsapp_path and os.path.exists(self.whatsapp_path):
            try: 
                os.startfile(self.whatsapp_path)
                launch_command_issued = True
            except Exception: pass
        
        if not launch_command_issued:
            try: 
                os.startfile("whatsapp:")
                launch_command_issued = True
            except Exception: pass
        
        if not launch_command_issued:
            try: 
                subprocess.Popen(["whatsapp"], shell=True)
                launch_command_issued = True
            except Exception: pass
        
        if not launch_command_issued: 
            self.speaker.speak("Failed to launch WhatsApp using known methods.")
            return False
        
        time.sleep(3)

        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                wa_windows = pyautogui.getWindowsWithTitle("WhatsApp")
                if wa_windows:
                    wa_window = wa_windows[0]
                    wa_window.activate()
                    time.sleep(0.2)
                    if not wa_window.isMaximized: wa_window.maximize()
                    time.sleep(0.5)
                    self.speaker.speak("WhatsApp opened and focused.")
                    return True
                elif attempt < max_attempts -1 :
                    time.sleep(1)
            except Exception as e:
                print(f"Error while trying to focus WhatsApp window: {e}")
                if attempt == max_attempts -1:
                     self.speaker.speak("WhatsApp might have opened, but I couldn't focus it.")
                     return False
        
        self.speaker.speak("Could not confirm WhatsApp window presence after launch.")
        return False

    def search_whatsapp_contact(self, contact_name: str) -> bool:
        self.speaker.speak(f"Searching for contact: {contact_name}")
        search_bar_clicked = False
        if hasattr(config, 'SEARCH_BAR_IMG') and config.SEARCH_BAR_IMG and os.path.exists(config.SEARCH_BAR_IMG):
            if self.find_and_click(image_path=config.SEARCH_BAR_IMG, confidence=0.7, max_wait_secs=5):
                search_bar_clicked = True
        
        if not search_bar_clicked:
            self.speaker.speak("Search bar image not found or not clicked. Trying Ctrl+F then typing.")
            pyautogui.hotkey('ctrl', 'f') 
            time.sleep(0.5)

        pyautogui.hotkey('ctrl', 'a')
        pyautogui.press('backspace')
        pyautogui.typewrite(contact_name, interval=0.03)
        self.speaker.speak(f"Typed '{contact_name}'. Waiting for search results.")
        time.sleep(1.5)
        return True

    def select_top_searched_contact(self) -> bool:
        self.speaker.speak("Selecting the top contact from search results...")
        time.sleep(0.5) 
        pyautogui.press('down') 
        time.sleep(0.2)
        pyautogui.press('enter')
        self.speaker.speak("Chat opened.")
        time.sleep(2) 
        return True

    def scan_previous_messages(self, current_contact_name):
        if not hasattr(config, 'CHAT_HISTORY_SNIPPET_REGION') or not config.CHAT_HISTORY_SNIPPET_REGION:
            self.speaker.speak("Chat history OCR region not configured. Skipping scan.")
            return

        self.speaker.speak(f"Scanning chat history of {current_contact_name}...")
        x_region, y_region, w_region, h_region = config.CHAT_HISTORY_SNIPPET_REGION
        
        try:
            screenshot = ImageGrab.grab(bbox=(x_region, y_region, x_region + w_region, y_region + h_region))
        except Exception as e:
            self.speaker.speak(f"Error grabbing chat history screenshot: {e}")
            return

        try:
            processed_image = screenshot.convert('L')
            ocr_data = pytesseract.image_to_data(
                processed_image, lang='eng', config='--oem 3 --psm 6',
                output_type=pytesseract.Output.DICT
            )
            
            n_boxes = len(ocr_data["level"])
            if n_boxes == 0: return

            lines_buffer = {} 
            for i in range(n_boxes):
                if int(ocr_data['conf'][i]) > 40:
                    word_text = ocr_data['text'][i].strip()
                    if not word_text: continue
                    line_key = (ocr_data['block_num'][i], ocr_data['par_num'][i], ocr_data['line_num'][i])
                    if line_key not in lines_buffer:
                        lines_buffer[line_key] = {
                            'words': [], 'min_word_left_offset': ocr_data['left'][i],
                            'avg_confidence': 0, 'word_count': 0, 'line_top': ocr_data['top'][i]
                        }
                    lines_buffer[line_key]['words'].append(word_text)
                    current_total_conf = lines_buffer[line_key]['avg_confidence'] * lines_buffer[line_key]['word_count']
                    lines_buffer[line_key]['word_count'] += 1
                    lines_buffer[line_key]['avg_confidence'] = (current_total_conf + int(ocr_data['conf'][i])) / lines_buffer[line_key]['word_count']
            
            messages_logged_count = 0
            right_alignment_pixel_threshold_in_snippet = w_region * 0.35
            sorted_line_keys = sorted(lines_buffer.keys(), key=lambda k: (lines_buffer[k]['line_top'], k))

            for line_key in sorted_line_keys: 
                data = lines_buffer[line_key]
                full_line_text = " ".join(data['words']).strip()
                if not full_line_text or len(full_line_text) < 2 or data['avg_confidence'] < 50: 
                    continue
                if re.fullmatch(r"\d{1,2}:\d{2}\s*(AM|PM)?", full_line_text, re.IGNORECASE) or \
                   full_line_text.lower() in ["chats", "contacts", "messages", "edited", "typing...", "online"]: 
                    continue
                sender = "user" if data['min_word_left_offset'] > right_alignment_pixel_threshold_in_snippet else current_contact_name
                processed_text = full_line_text
                if sender == "user" and processed_text.lower().startswith("you ") and data['words'][0].lower() == "you":
                    processed_text = " ".join(data['words'][1:]).strip()
                if processed_text:
                    self.history_manager.add_message_to_history(current_contact_name, sender, processed_text)
                    messages_logged_count += 1
            if messages_logged_count > 0: self.speaker.speak(f"Logged {messages_logged_count} lines from chat history.")
        except pytesseract.TesseractNotFoundError: 
            self.speaker.speak("Tesseract not found. Cannot scan chat history.")
        except Exception as e: 
            self.speaker.speak(f"Problem during OCR for {current_contact_name}: {e}"); print(f"OCR Error: {e}")

    def send_text_in_current_chat(self, message_text: str, contact_name_for_logging: str) -> bool:
        agent_crafted_message = message_text
        if self.agent and self.history_manager:
            crafted_by_llm = self.agent.generate_refined_message(
                contact_name=contact_name_for_logging,
                user_instruction=message_text
            )
            if crafted_by_llm: 
                agent_crafted_message = crafted_by_llm
            else: 
                self.speaker.speak("Agent did not refine message. Sending as is.")
        else: 
            self.speaker.speak("LLM Agent/History not configured. Sending message as is.")
        
        if not agent_crafted_message:
            self.speaker.speak("No message content to send. Aborting.")
            return False
        
        input_bar_clicked = False
        if hasattr(config, 'CHAT_INPUT_BAR_IMG') and config.CHAT_INPUT_BAR_IMG and os.path.exists(config.CHAT_INPUT_BAR_IMG):
            if self.find_and_click(config.CHAT_INPUT_BAR_IMG, confidence=0.7, max_wait_secs=3):
                input_bar_clicked = True
        if not input_bar_clicked:
            self.speaker.speak("Chat input bar image not found/configured. Typing into current focus.")

        pyautogui.typewrite(agent_crafted_message, interval=0.05)
        time.sleep(0.2)

        sent_by_button = False
        if hasattr(config, 'SEND_BUTTON_IMG') and config.SEND_BUTTON_IMG and os.path.exists(config.SEND_BUTTON_IMG):
            if self.find_and_click(config.SEND_BUTTON_IMG, confidence=0.7, max_wait_secs=2):
                sent_by_button = True
        
        if not sent_by_button:
            self.speaker.speak("Send button image not found/clicked. Pressing Enter.")
            pyautogui.press('enter')

        self.speaker.speak("Text message sent.")
        if self.history_manager:
            self.history_manager.add_message_to_history(contact_name_for_logging, "user", agent_crafted_message)
        return True

    def send_voice_in_current_chat(self, 
                                   contact_name_for_logging: str,
                                   tts_message_content: Optional[str] = None,
                                   user_speech_duration_secs: int = 7) -> bool:
        if not hasattr(config, 'MIC_BUTTON_IMG') or not config.MIC_BUTTON_IMG or not os.path.exists(config.MIC_BUTTON_IMG):
            self.speaker.speak("MIC_BUTTON_IMG not configured. Cannot send voice message.")
            return False

        self.current_mic_button_location = self.find_and_click(config.MIC_BUTTON_IMG, confidence=0.7, max_wait_secs=5)
        if not self.current_mic_button_location:
            self.speaker.speak("Could not find/click microphone button.")
            return False
        
        if tts_message_content:
            self.speaker.speak(f"Assistant speaking: {tts_message_content}")
            self.speaker.speak(tts_message_content) 
            words = len(tts_message_content.split())
            estimated_tts_duration = max(1.0, (words * 0.45) + 1.5) 
            self.speaker.speak(f"Waiting approx {estimated_tts_duration:.1f}s for TTS.")
            time.sleep(estimated_tts_duration)
        elif user_speech_duration_secs > 0:
            self.speaker.speak(f"Recording for {user_speech_duration_secs}s. User should speak now!")
            time.sleep(user_speech_duration_secs) 
        else: 
            self.speaker.speak("No content for voice message and no user recording duration. Sending brief empty recording.")
            time.sleep(0.5) 

        self.speaker.speak("Recording finished. Attempting to send voice message.")
        
        send_button_img_to_use = None
        if hasattr(config, 'VOICE_SEND_BUTTON_IMG') and config.VOICE_SEND_BUTTON_IMG and os.path.exists(config.VOICE_SEND_BUTTON_IMG):
            send_button_img_to_use = config.VOICE_SEND_BUTTON_IMG
        elif hasattr(config, 'SEND_BUTTON_IMG') and config.SEND_BUTTON_IMG and os.path.exists(config.SEND_BUTTON_IMG):
            send_button_img_to_use = config.SEND_BUTTON_IMG
        
        sent_successfully = False
        if send_button_img_to_use:
            if self.find_and_click(send_button_img_to_use, confidence=0.7, max_wait_secs=3):
                self.speaker.speak("Voice message sent via button.")
                sent_successfully = True
            elif self.current_mic_button_location: 
                pyautogui.moveTo(self.current_mic_button_location, duration=0.1)
                pyautogui.click()
                self.speaker.speak("Voice message sent by clicking original mic button location.")
                sent_successfully = True
            else:
                self.speaker.speak(f"Could not find configured send button: {os.path.basename(send_button_img_to_use)}.")
        
        if not sent_successfully:
            self.speaker.speak("Falling back to pressing Enter to send voice message.")
            pyautogui.press('enter')
            self.speaker.speak("Voice message sent via Enter key (assumed).")
            sent_successfully = True 

        if sent_successfully and self.history_manager:
            log_msg = f"[Voice Message by Assistant: {tts_message_content}]" if tts_message_content else "[User Spoken Voice Message]"
            self.history_manager.add_message_to_history(contact_name_for_logging, "user", log_msg)

        return sent_successfully