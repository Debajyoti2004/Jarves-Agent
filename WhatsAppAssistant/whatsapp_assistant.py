
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

    def handle_send_message_flow(self):
        self.speaker.speak("Okay, let's send a message.")
        
        if not self.wa_actions.open_whatsapp_window():
            self.speaker.speak("Could not open WhatsApp.")
            return

        contact_name_query = self.speaker.listen("Who do you want to send a message to?")
        if not contact_name_query:
            self.speaker.speak("No contact name provided.")
            return

        if not self.wa_actions.search_whatsapp_contact(contact_name_query):
            self.speaker.speak(f"Problem searching for '{contact_name_query}'.")
            return 
        
        raw_message_to_send = self.speaker.listen(f"What message for top result for '{contact_name_query}'?")
        if not raw_message_to_send:
            self.speaker.speak("No message provided.")
            return

        self.speaker.speak(f"Sending message to top result for '{contact_name_query}'.")
        if self.wa_actions.send_message_to_top_contact_via_agent(contact_name_query, raw_message_to_send):
            pass 
        else:
            self.speaker.speak(f"Issue sending message to '{contact_name_query}'.")

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
                self.handle_send_message_flow()
            else:
                self.speaker.speak("I can help send a WhatsApp message or say 'exit'.")
            
            self.speaker.speak("Ready for your next command.") 
            time.sleep(0.5)


if __name__ == "__main__":
    assistant = WhatsAppVoiceAssistant()
    assistant.run()