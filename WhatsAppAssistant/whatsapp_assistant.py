import time
import os
import pyautogui

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

    def extract_contact_and_message(self, command):
        parts = command.replace("send message", "", 1).strip()
        if not parts:
            return None, None
        if " to " in parts:
            message, contact = parts.rsplit(" to ", 1)
            return contact.strip(), message.strip()
        return None, parts.strip()

    def handle_send_message_flow(self, command=None):
        self.speaker.speak("Okay, let's send a message.")
        if not self.wa_actions.open_whatsapp_window():
            self.speaker.speak("Could not open WhatsApp.")
            return

        contact_name, message = self.extract_contact_and_message(command or "")
        if not contact_name:
            contact_name = self.speaker.listen("Who do you want to send a message to?")
            if not contact_name:
                self.speaker.speak("No contact name provided.")
                return

        if not self.wa_actions.search_whatsapp_contact(contact_name):
            self.speaker.speak(f"Problem searching for '{contact_name}'.")
            return

        if not message:
            message = self.speaker.listen(f"What message for top result for '{contact_name}'?")
            if not message:
                self.speaker.speak("No message provided.")
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
            if "exit" in user_command or "stop" in user_command:
                self.speaker.speak("Goodbye!")
                break
            elif "send message" in user_command:
                self.handle_send_message_flow(user_command)
            else:
                self.speaker.speak("I can help send a WhatsApp message or say 'exit'.")

            self.speaker.speak("Ready for your next command.")
            time.sleep(0.5)

if __name__ == "__main__":
    assistant = WhatsAppVoiceAssistant()
    assistant.run()
