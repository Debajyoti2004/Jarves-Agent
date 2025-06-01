import time
import os
import pyautogui
import re
from typing import Tuple, Optional, List, Dict, Any

import config 
from voice_recognizer import SpeechService 
from whatsapp_actions import WhatsAppActions 

class WhatsAppVoiceAssistant:
    def __init__(self):
        self.config = config
        self.speaker = SpeechService()

        google_api_key = getattr(self.config, 'GOOGLE_API_KEY', None)
        if google_api_key == "YOUR_GOOGLE_API_KEY":
            self.speaker.speak("Warning: Google API Key is a placeholder.")
            google_api_key = None

        self.wa_actions = WhatsAppActions(
            whatsapp_path=self.config.WHATSAPP_EXE_PATH,
            speaker=self.speaker,
            google_api_key=google_api_key
        )
        pyautogui.FAILSAFE = True
        self.current_open_contact: Optional[str] = None
        self.is_whatsapp_open_and_focused: bool = False


    def extract_contact_and_message_for_text(self, command: str) -> Tuple[Optional[str], Optional[str]]:
        prefix_pattern = re.compile(r"^(?:send\s+message|message)\s+", re.IGNORECASE)
        content_after_prefix = prefix_pattern.sub("", command, 1).strip()

        if not content_after_prefix:
            return None, None

        separator_literal = " to "
        temp_lower_content = content_after_prefix.lower()
        last_sep_idx = temp_lower_content.rfind(separator_literal.lower())

        if last_sep_idx != -1:
            message = content_after_prefix[:last_sep_idx].strip()
            contact = content_after_prefix[last_sep_idx + len(separator_literal):].strip()
            return contact, message
        else:
            if temp_lower_content.startswith("to ") and len(content_after_prefix) > len("to "):
                contact = content_after_prefix[len("to "):].strip()
                message = "" 
                return contact, message
            else: 
                return None, content_after_prefix

    def extract_voice_message_details(self, command: str) -> Tuple[Optional[str], Optional[str], int]:
        contact_name: Optional[str] = None
        tts_message: Optional[str] = None
        duration_secs: int = 7 
        default_duration_for_user_speech = duration_secs
        command_lower = command.lower()

        patterns_with_tts = [
            re.compile(r"(?:send\s+(?:a\s+)?(?:(\d+)\s*second)?\s*)?voice\s+(?:message|note)\s+(?:saying\s+|that\s+says\s+|with\s+the\s+message\s+)?(?:\"([^\"]+)\"|\'([^\']+)\')\s+to\s+([^\d\"'\s][^\"]*?)(?:\s+for\s+(\d+)\s*second(?:s)?)?$", re.IGNORECASE),
            re.compile(r"(?:send\s+(?:a\s+)?(?:(\d+)\s*second)?\s*)?voice\s+(?:message|note)\s+saying\s+(.+?)\s+to\s+([^\d\"'\s][^\"]*?)(?:\s+for\s+(\d+)\s*second(?:s)?)?$", re.IGNORECASE),
            re.compile(r"(?:send\s+(?:a\s+)?(?:(\d+)\s*second)?\s*)?voice\s+(?:message|note)\s+(.+?)\s+to\s+([^\d\"'\s][^\"]*?)(?:\s+for\s+(\d+)\s*second(?:s)?)?$", re.IGNORECASE)
        ]
        for idx, pattern in enumerate(patterns_with_tts):
            match = pattern.search(command)
            if match:
                g = match.groups()
                dur_start, tts_content_group1, tts_content_group2, contact, dur_end = (None, None, None, None, None)
                if idx == 0: dur_start, tts_double, tts_single, contact, dur_end = g; tts_message = tts_double if tts_double else tts_single
                elif idx == 1: dur_start, tts_message, contact, dur_end = g
                elif idx == 2: dur_start, tts_message, contact, dur_end = g; 
                if tts_message and re.match(r"^\d+\s*second(s)?$", tts_message.strip(), re.IGNORECASE): tts_message = None 
                if tts_message: tts_message = tts_message.strip()
                if contact: contact_name = contact.strip()
                if dur_start: duration_secs = int(dur_start)
                elif dur_end: duration_secs = int(dur_end)
                if contact_name and tts_message: return contact_name, tts_message, duration_secs 
                elif contact_name and not tts_message and idx == 2: contact_name = None; pass 
        
        patterns_user_speaks = [
            (r"(?:send|record)\s+(?:a\s+)?(\d+)\s*second(?:s)?\s+voice\s+(?:message|note)\s+to\s+(.+)", lambda m: (m.group(2).strip(), None, int(m.group(1)))),
            (r"(?:send|record)\s+voice\s+(?:message|note)\s+to\s+(.+?)\s+for\s+(\d+)\s*second(?:s)?", lambda m: (m.group(1).strip(), None, int(m.group(2)))),
            (r"(?:send|record)\s+voice\s+(?:message|note)\s+to\s+(.+)", lambda m: (re.sub(r'\s+for\s+\d+\s*second(s)?$', '', m.group(1).strip(), flags=re.IGNORECASE).strip(), None, default_duration_for_user_speech)),
        ]
        for pat_str, handler in patterns_user_speaks:
            match = re.search(pat_str, command, re.IGNORECASE)
            if match: return handler(match)
        
        fallback_match = re.search(r"to\s+(.+)", command_lower) 
        if fallback_match and ("voice" in command_lower or "audio" in command_lower):
             words_after_to = fallback_match.group(1).strip()
             if not (re.search(r" for \d+ second", words_after_to) or "\"" in words_after_to or "'" in words_after_to):
                contact_name = words_after_to
                return contact_name, None, default_duration_for_user_speech 
        return None, None, default_duration_for_user_speech 

    def parse_sub_commands(self, main_command: str) -> List[str]:
        processed_command = main_command.strip()
        if not processed_command: return []
        if processed_command.lower().startswith("first "):
            processed_command = processed_command[len("first "):].strip()
        
        processed_command = re.sub(r'\s+and then\s+', ' @@SPLIT@@ ', processed_command, flags=re.IGNORECASE)
        processed_command = re.sub(r'\s+after that\s+', ' @@SPLIT@@ ', processed_command, flags=re.IGNORECASE)
        processed_command = re.sub(r'\s+then\s+', ' @@SPLIT@@ ', processed_command, flags=re.IGNORECASE)
        processed_command = re.sub(r'\s+and\s+(?=(?:send|voice|record|message\s+to|text\s+to))', 
                                   ' @@SPLIT@@ ', processed_command, flags=re.IGNORECASE)
        return [cmd.strip() for cmd in processed_command.split('@@SPLIT@@') if cmd.strip()]

    def _ensure_whatsapp_open_and_contact_selected(self, target_contact_name: Optional[str]) -> bool:
        if not target_contact_name:
            self.speaker.speak("No contact name specified for the action.")
            return False

        if not self.is_whatsapp_open_and_focused:
            self.speaker.speak("Opening WhatsApp...")
            if not self.wa_actions.open_whatsapp_window():
                self.speaker.speak("Could not open or focus WhatsApp.")
                self.is_whatsapp_open_and_focused = False
                self.current_open_contact = None
                return False
            self.is_whatsapp_open_and_focused = True
            self.current_open_contact = None 

        if self.current_open_contact is None or self.current_open_contact.lower() != target_contact_name.lower():
            self.speaker.speak(f"Searching for {target_contact_name}...")
            if not self.wa_actions.search_whatsapp_contact(target_contact_name):
                self.speaker.speak(f"Problem initiating search for '{target_contact_name}'.")
                self.current_open_contact = None
                return False
            if not self.wa_actions.select_top_searched_contact(): 
                self.speaker.speak(f"Problem selecting top contact for '{target_contact_name}'.")
                self.current_open_contact = None
                return False
            self.current_open_contact = target_contact_name
            self.speaker.speak(f"Chat with {target_contact_name} is now open.")
        return True

    def handle_send_text_message(self, command_part: str):
        contact_name, message = self.extract_contact_and_message_for_text(command_part)

        if not contact_name:
            self.speaker.speak("For the text message, who is the recipient?")
            contact_name_input = self.speaker.listen()
            if not contact_name_input or not contact_name_input.strip():
                self.speaker.speak("No recipient provided for text message. Skipping.")
                return
            contact_name = contact_name_input.strip()
        
        if not message: 
            self.speaker.speak(f"What is the text message for {contact_name}?")
            message_input = self.speaker.listen()
            if message_input is None: 
                self.speaker.speak("No message content provided. Skipping.")
                return
            message = message_input 

        if message is not None and not message.strip() and message == "": 
             self.speaker.speak("Message content is empty. Do you still want to send an empty message? Say yes to confirm.")
             confirmation = self.speaker.listen()
             if not confirmation or "yes" not in confirmation.lower():
                 self.speaker.speak("Sending empty message cancelled.")
                 return
        elif message is None: 
            self.speaker.speak("No message content. Skipping.")
            return

        if not self._ensure_whatsapp_open_and_contact_selected(contact_name):
            return

        self.speaker.speak(f"Sending text message to {contact_name}: '{message}'")
        if self.wa_actions.send_text_in_current_chat(message, contact_name): 
            self.speaker.speak("Text message sent.")
        else:
            self.speaker.speak(f"Issue sending text message to {contact_name}.")


    def handle_send_voice_message(self, command_part: str):
        contact_name, tts_content, user_duration = self.extract_voice_message_details(command_part)

        if not contact_name:
            self.speaker.speak("For the voice message, who is the recipient?")
            contact_name_input = self.speaker.listen()
            if not contact_name_input or not contact_name_input.strip():
                self.speaker.speak("No recipient provided for voice message. Skipping.")
                return
            contact_name = contact_name_input.strip()

        if not tts_content: 
            self.speaker.speak(f"For the voice message to {contact_name}, should I speak something or will you record it?")
            self.speaker.speak("Say 'speak' followed by your message, or 'record' for a few seconds.")
            user_choice_input = self.speaker.listen()
            if user_choice_input:
                if user_choice_input.lower().startswith("speak "):
                    tts_content = user_choice_input[len("speak "):].strip()
                    if not tts_content:
                        self.speaker.speak("No message to speak was provided. Skipping voice message.")
                        return
                elif "record" in user_choice_input.lower():
                    tts_content = None 
                    if not user_duration or user_duration <=0 : user_duration = 7 
                    self.speaker.speak(f"Okay, I'll record for {user_duration} seconds.")
                else:
                    self.speaker.speak("Didn't understand choice. Assuming you will record for a few seconds.")
                    tts_content = None
                    user_duration = 7
            else: 
                 self.speaker.speak(f"Okay, prepare to record your voice message for {contact_name} for about {user_duration} seconds.")
                 tts_content = None 

        if not self._ensure_whatsapp_open_and_contact_selected(contact_name):
            return
        
        if tts_content:
            self.speaker.speak(f"Sending assistant-spoken voice message to {contact_name}.")
        else:
            self.speaker.speak(f"Preparing for you to record a {user_duration}-second voice message to {contact_name}.")

        if self.wa_actions.send_voice_in_current_chat( 
            contact_name_for_logging=contact_name,
            tts_message_content=tts_content,
            user_speech_duration_secs=user_duration if not tts_content else 0
            ):
            self.speaker.speak("Voice message process initiated.")
        else:
            self.speaker.speak(f"Issue sending voice message to {contact_name}.")


    def execute_actions(self, sub_commands: List[str]):
        if not sub_commands:
            self.speaker.speak("No actions to perform.")
            return

        initial_open_success = self.wa_actions.open_whatsapp_window()
        if not initial_open_success:
            self.speaker.speak("Failed to open WhatsApp. Cannot proceed with actions.")
            self.is_whatsapp_open_and_focused = False
            self.current_open_contact = None
            return
        self.is_whatsapp_open_and_focused = True
        self.current_open_contact = None 

        for i, command_part in enumerate(sub_commands):
            self.speaker.speak(f"Processing step {i+1}: {command_part}")
            command_part_lower = command_part.lower()

            if "voice" in command_part_lower and ("message" in command_part_lower or "note" in command_part_lower or "audio" in command_part_lower):
                self.handle_send_voice_message(command_part)
            elif "message" in command_part_lower or "text" in command_part_lower : 
                self.handle_send_text_message(command_part)
            else:
                self.speaker.speak(f"I'm not sure how to handle: '{command_part}'. I can send text or voice messages.")
            
            time.sleep(1) 

    def run(self):
        self.speaker.speak("WhatsApp Voice Assistant (Standalone) activated! How can I help?")
        while True:
            user_command_str = self.speaker.listen()
            if user_command_str is None:
                time.sleep(0.5)
                continue
            
            if isinstance(user_command_str, str):
                user_command_lower = user_command_str.lower()
                
                if "exit" in user_command_lower or "stop" in user_command_lower:
                    self.speaker.speak("Goodbye!")
                    break
                
                sub_commands = self.parse_sub_commands(user_command_str)
                if sub_commands:
                    self.execute_actions(sub_commands)
                else:
                    if "send message" in user_command_lower and not any(kw in user_command_lower for kw in [" to ", "voice", "audio"]):
                         self.handle_send_text_message(user_command_str) 
                    else:
                        self.speaker.speak("I can help send WhatsApp messages (text or voice). Try saying 'send message hello to John' or 'send a voice message to Jane saying hi'.")
            else:
                 self.speaker.speak("Sorry, I received an unexpected command type. Please try again.")

            self.speaker.speak("Ready for your next command.")
            self.current_open_contact = None 
            self.is_whatsapp_open_and_focused = False 
            time.sleep(0.5)

if __name__ == "__main__":
    assistant = WhatsAppVoiceAssistant()
    assistant.run()