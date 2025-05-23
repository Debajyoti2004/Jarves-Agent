import os
import subprocess
import pyautogui
import time
import pytesseract
import config
from PIL import ImageGrab,ImageOps
from conversation_history_manager import ConversationHistoryManager
from message_manager import MessageAgentLLM
import re

class WhatsAppActions:
    def __init__(self, whatsapp_path, speaker,google_api_key=None):
        self.whatsapp_path = whatsapp_path
        self.speaker = speaker
        self.history_manager = ConversationHistoryManager(history_file_path=config.CONVERSATION_MEMORY_PATH)
        self.agent = MessageAgentLLM(speaker=self.speaker,history_manager=self.history_manager,google_api_key=google_api_key)

    def find_and_click(self, image_path, confidence=0.8, region=None, clicks=1, button='left', max_wait_secs=5):
        start_time = time.time()
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
                self.speaker.speak(f"Error in find_and_click for {os.path.basename(image_path)}: {e}")
                return None
        self.speaker.speak(f"Could not find UI element: {os.path.basename(image_path)} to click.")
        return None

    def open_whatsapp_window(self):
        launch_command_issued = False; self.speaker.speak("Opening WhatsApp...")
        if self.whatsapp_path and os.path.exists(self.whatsapp_path):
            try: 
                os.startfile(self.whatsapp_path)
                launch_command_issued = True
            except Exception: 
                pass
        if not launch_command_issued:
            try: 
                os.startfile("whatsapp:")
                launch_command_issued = True
            except Exception: 
                pass
        if not launch_command_issued:
            try: 
                subprocess.Popen(["whatsapp"], shell=True); launch_command_issued = True
            except Exception: 
                pass
        if not launch_command_issued: 
            self.speaker.speak("Launch failed."); return False
        time.sleep(1)
        try:
            active_window = pyautogui.getActiveWindow()
            if active_window and ("whatsapp" in active_window.title.lower()): 
                return True
        except Exception: 
            return False

    def search_whatsapp_contact(self, contact_name):
        self.speaker.speak(f"Searching for {contact_name}")
        if not self.find_and_click(image_path=config.SEARCH_BAR_IMG, confidence=0.7, max_wait_secs=5):
            self.speaker.speak("Search bar image not found. Typing into current focus.")

        pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace')
        pyautogui.typewrite(contact_name, interval=0.03)
        self.speaker.speak(f"Typed {contact_name}. Waiting for list.")
        time.sleep(0.5)
        return True
    
    def scan_previous_messages(self, current_contact_name):
        if not hasattr(config, 'CHAT_HISTORY_SNIPPET_REGION'):
            self.speaker.speak("Chat history OCR region not configured in config.py.")
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
            processed_image = ImageOps.invert(processed_image)
            
            ocr_data = pytesseract.image_to_data(
                processed_image,
                lang='eng',
                config='--oem 3 --psm 4',
                output_type=pytesseract.Output.DICT
            )
            
            n_boxes = len(ocr_data["level"])
            if n_boxes == 0:
                self.speaker.speak("OCR found no text in the chat history region.")
                return

            lines_buffer = {} 
            for i in range(n_boxes):
                if int(ocr_data['conf'][i]) > 40: 
                    word_text = ocr_data['text'][i].strip()
                    if not word_text:
                        continue

                    block_num = ocr_data['block_num'][i]
                    par_num = ocr_data['par_num'][i]
                    line_num = ocr_data['line_num'][i]
                    word_left_offset = ocr_data['left'][i]

                    line_key = (block_num, par_num, line_num)

                    if line_key not in lines_buffer:
                        lines_buffer[line_key] = {
                            'words': [],
                            'min_word_left_offset': float('inf'),
                            'avg_confidence': 0,
                            'word_count': 0
                        }
                    
                    lines_buffer[line_key]['words'].append(word_text)
                    lines_buffer[line_key]['min_word_left_offset'] = min(lines_buffer[line_key]['min_word_left_offset'], word_left_offset)
                    lines_buffer[line_key]['avg_confidence'] = (lines_buffer[line_key]['avg_confidence'] * lines_buffer[line_key]['word_count'] + int(ocr_data['conf'][i])) / (lines_buffer[line_key]['word_count'] + 1)
                    lines_buffer[line_key]['word_count'] +=1
            
            messages_logged_count = 0
            right_alignment_pixel_threshold_in_snippet = w_region * 0.40

            for line_key in sorted(lines_buffer.keys()): 
                data = lines_buffer[line_key]
                full_line_text = " ".join(data['words']).strip()

                if not full_line_text or len(full_line_text) < 3 or data['avg_confidence'] < 50:
                    continue
                if re.fullmatch(r"\d{1,2}:\d{2}\s*(AM|PM)?", full_line_text) or full_line_text.lower() in ["chats", "contacts", "messages","edited"]:
                    continue

                sender = "user" if data['min_word_left_offset'] > right_alignment_pixel_threshold_in_snippet else current_contact_name
                
                processed_text = full_line_text
                if sender == "user" and processed_text.lower().startswith("you "):
                    if data['words'][0].lower() == "you":
                        processed_text = " ".join(data['words'][1:]).strip()
                elif sender == current_contact_name:
                    contact_first_name_lower = current_contact_name.split(' ')[0].lower()
                    if processed_text.lower().startswith(contact_first_name_lower + " "):
                        temp_text = processed_text[len(contact_first_name_lower):].lstrip()
                        if temp_text.startswith(":") or temp_text.startswith(")"):
                            processed_text = temp_text[1:].strip()
                        elif len(temp_text) > 0 and len(temp_text) < len(processed_text) - len(contact_first_name_lower):
                            processed_text = temp_text
                
                if processed_text:
                    self.history_manager.add_message_to_history(
                        contact_name=current_contact_name,
                        sender=sender,
                        message=processed_text
                    )
                    messages_logged_count += 1
            
            if messages_logged_count > 0:
                self.speaker.speak(f"Logged {messages_logged_count} lines from scanned chat.")
            else:
                self.speaker.speak("No scannable messages logged from chat history.")
        except Exception as e:
            self.speaker.speak(f"Problem during scanning chat of {current_contact_name}: {e}")
            print(f"Detailed Scan Error: {e}")

    def send_message_to_top_contact_via_agent(self, searched_contact_name_for_history, raw_user_message):
        self.speaker.speak("Selecting top contact...")
        time.sleep(0.5)
        pyautogui.press('down')
        time.sleep(0.2)
        pyautogui.press('enter')

        self.speaker.speak("Chat opened.")
        time.sleep(2)

        if not self.agent or not self.history_manager:
            self.speaker.speak("Agent/History not configured. Sending raw.")
            agent_crafted_message = raw_user_message
        else:
            self.scan_previous_messages(current_contact_name=searched_contact_name_for_history)

            agent_crafted_message = self.agent.generate_refined_message(
                searched_contact_name_for_history,
                raw_user_message
            )
        if not agent_crafted_message:
            self.speaker.speak("Agent provided no message. Aborting.")
            return False
        
        if hasattr(config, 'CHAT_INPUT_BAR_IMG') and config.CHAT_INPUT_BAR_IMG and os.path.exists(config.CHAT_INPUT_BAR_IMG):
            if not self.find_and_click(config.CHAT_INPUT_BAR_IMG, confidence=0.7, max_wait_secs=5):
                self.speaker.speak("Chat input bar not found. Typing may fail.")
        else:
            self.speaker.speak("Chat input bar image not configured. Attempting to type.")

        pyautogui.typewrite(agent_crafted_message, interval=0.05)
        time.sleep(0.2)
        sent_by_button = False

        if hasattr(config, 'SEND_BUTTON_IMG') and config.SEND_BUTTON_IMG and os.path.exists(config.SEND_BUTTON_IMG):
            if self.find_and_click(config.SEND_BUTTON_IMG, confidence=0.7, max_wait_secs=2):
                sent_by_button = True
        if not sent_by_button:
            pyautogui.press('enter')

        self.speaker.speak("Message sent.")
        if self.history_manager:
            self.history_manager.add_message_to_history(
                searched_contact_name_for_history, "user", agent_crafted_message
            )
            self.speaker.speak("Message logged.")
        return True




             

            