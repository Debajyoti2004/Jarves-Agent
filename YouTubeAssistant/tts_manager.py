import pyttsx3
from config import TTS_ENGINE_RATE

class TTSManager:
    def __init__(self):
        self.engine = None
        self._initialize_engine()

    def _initialize_engine(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', TTS_ENGINE_RATE)
            print("TTS Engine Initialized successfully.")
            self.speak("Text to speech engine initialized.", console_only=True)
        except Exception as e:
            print(f"WARNING: Failed to initialize TTS engine: {e}. Script will run without voice output.")
            self.engine = None

    def speak(self, text, console_only=False):
        print(f"ASSISTANT: {text}")
        if self.engine and not console_only:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except RuntimeError:
                print("TTS Error: Engine busy or in bad state. Skipping speech.")
            except Exception as e:
                print(f"TTS Error: {e}")