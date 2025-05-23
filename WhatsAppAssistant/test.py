
import pyautogui
import time
import os

import config
from voice_recognizer import SpeechService
from whatsapp_actions import WhatsAppActions

class DummySpeakerForTest:
    def speak(self, text):
        print(f"Speaker (Test): {text}")

if __name__ == "__main__":
    pyautogui.FAILSAFE = True
    
    speaker = SpeechService()

    google_api_key_from_config =config.GOOGLE_API_KEY

    wa_actions = WhatsAppActions(
        whatsapp_path=config.WHATSAPP_EXE_PATH,
        speaker=speaker,
        google_api_key=google_api_key_from_config
    )

    test_contact_name = "chandan majee" 
    test_message_to_send = "okay,i will say"

    speaker.speak(f"\n--- Starting Test: Send message to '{test_contact_name}' ---")
    speaker.speak(f"Message to send: '{test_message_to_send}'")

    speaker.speak("\nStep 1: Opening WhatsApp...")
    if not wa_actions.open_whatsapp_window():
        speaker.speak("FAILURE: Could not open or focus WhatsApp. Test aborted.")
        exit()
    speaker.speak("SUCCESS: WhatsApp window should be open and focused.")
    time.sleep(1)

    speaker.speak(f"\nStep 2: Searching for contact '{test_contact_name}'...")
    if not wa_actions.search_whatsapp_contact(test_contact_name): 
        speaker.speak(f"FAILURE: Search for '{test_contact_name}' did not complete successfully. Test aborted.")

    speaker.speak(f"SUCCESS: Searched for '{test_contact_name}'. Top result should match.")
    time.sleep(1)

    speaker.speak(f"\nStep 3: Sending message to top result for '{test_contact_name}' via agent...")
    print(f"   (Ensure that after searching for '{test_contact_name}', the desired contact is the TOP result)")
    print(f"   (The script will press 'down' once, then 'enter')")
    print("   You have 5 seconds to observe...")
    time.sleep(5)

    if wa_actions.send_message_to_top_contact_via_agent(test_contact_name, test_message_to_send):
        speaker.speak(f"SUCCESS: Message sending process for '{test_contact_name}' completed.")
        speaker.speak("Please check WhatsApp to verify the message was sent to the correct contact.")
        speaker.speak("Also, check 'conversations.json' for the logged message.")
    else:
        speaker.speak(f"FAILURE: Could not complete sending the message to '{test_contact_name}'.")

    print("\n--- Test Finished ---")