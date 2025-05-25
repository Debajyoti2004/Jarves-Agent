import time
import os
import pyautogui
import re
from typing import Tuple, Optional

import config
from voice_recognizer import SpeechService
from whatsapp_actions import WhatsAppActions

class WhatsAppVoiceAssistant:
    def __init__(self):
        self.config = config
        self.speaker = SpeechService()

        google_api_key = getattr(self.config, 'GOOGLE_API_KEY', None)
        if google_api_key == "YOUR_GOOGLE_API_KEY":
            self.speaker.speak("Warning: Google API Key is placeholder.")
            google_api_key = None

        self.wa_actions = WhatsAppActions(
            whatsapp_path=self.config.WHATSAPP_EXE_PATH,
            speaker=self.speaker,
            google_api_key=google_api_key
        )
        pyautogui.FAILSAFE = True

    def extract_contact_and_message(self, command: str) -> Tuple[Optional[str], Optional[str]]:
        prefix_pattern = re.compile(r"send message", re.IGNORECASE)
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
            if temp_lower_content.startswith("to ") and len(content_after_prefix) > 3:
                contact = content_after_prefix[3:].strip()
                message = ""
                return contact, message
            else:
                return None, content_after_prefix

    def handle_send_message_flow(self, command=None):
        self.speaker.speak("Okay, let's send a message.")
        if not self.wa_actions.open_whatsapp_window():
            self.speaker.speak("Could not open WhatsApp.")
            return

        contact_name, message = self.extract_contact_and_message(command or "")

        if not contact_name:
            contact_name_input = self.speaker.listen("Who do you want to send a message to?")
            if not contact_name_input:
                self.speaker.speak("No contact name provided.")
                return
            contact_name = contact_name_input

        if not contact_name.strip():
            self.speaker.speak("No valid contact name provided.")
            return

        if not self.wa_actions.search_whatsapp_contact(contact_name):
            self.speaker.speak(f"Problem searching for '{contact_name}'.")
            return

        if not message:
            message_input = self.speaker.listen(f"What message for top result for '{contact_name}'?")
            if not message_input:
                self.speaker.speak("No message provided.")
                return
            message = message_input
        
        if not message.strip() and message is not None :
            if message == "":
                self.speaker.speak("No message content provided.")
                return

        self.speaker.speak(f"Sending message to top result for '{contact_name}'.")
        if self.wa_actions.send_message_to_top_contact_via_agent(contact_name, message):
            pass
        else:
            self.speaker.speak(f"Issue sending message to '{contact_name}'.")

    def run(self):
        self.speaker.speak("WhatsApp Voice Assistant activated! How can I help?")
        while True:
            user_command = self.speaker.listen()
            if user_command is None:
                time.sleep(1)
                continue
            
            if isinstance(user_command, str):
                user_command_lower = user_command.lower()
                if "send message" in user_command_lower:
                    self.handle_send_message_flow(user_command)
                elif "exit" in user_command_lower or "stop" in user_command_lower:
                    self.speaker.speak("Goodbye!")
                    break
                else:
                    self.speaker.speak("I can help send a WhatsApp message or say 'exit'.")
            else:
                 self.speaker.speak("Sorry, I received an unexpected command type. Please try again.")

            self.speaker.speak("Ready for your next command.")
            time.sleep(0.5)

if __name__ == "__main__":
    assistant = WhatsAppVoiceAssistant()
    assistant.run()