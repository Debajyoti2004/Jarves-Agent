from assistant import YouTubeVoiceAssistant
import traceback

if __name__ == "__main__":
    print("Starting YouTube Voice Assistant...")
    assistant = YouTubeVoiceAssistant()
    try:
        assistant.run()
    except Exception as e:
        print(f"An unexpected error occurred in the main execution: {e}")
        print("-------------------- TRACEBACK --------------------")
        traceback.print_exc()
        print("-------------------------------------------------")
        if hasattr(assistant, 'browser') and assistant.browser and hasattr(assistant.browser, 'driver') and assistant.browser.driver:
            assistant.browser.close_browser()
    finally:
        print("Application finished.")