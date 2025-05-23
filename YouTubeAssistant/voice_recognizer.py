import speech_recognition as sr
from config import GENERAL_LISTEN_TIMEOUT_SECONDS, HOVER_LISTEN_TIMEOUT_SECONDS

class VoiceRecognizer:
    def __init__(self, tts_manager=None):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_manager = tts_manager
        with self.microphone as source:
            print("VoiceRecognizer: Adjusting for ambient noise, please wait...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1.5)
            print("VoiceRecognizer: Ambient noise adjustment complete.")


    def _provide_feedback(self, message, console_only=False):
        if self.tts_manager:
            self.tts_manager.speak(message, console_only=console_only)
        else:
            print(f"RECOGNIZER: {message}")

    def listen_for_command(self, listen_timeout=GENERAL_LISTEN_TIMEOUT_SECONDS, phrase_limit=5):
        with self.microphone as source:
            speak_listening_prompt = listen_timeout >= GENERAL_LISTEN_TIMEOUT_SECONDS - 0.1
            if speak_listening_prompt:
                self._provide_feedback(f"Listening for command...")
            else:
                print(f"Listening for command ({listen_timeout}s)...")
            
            try:
                audio = self.recognizer.listen(source, timeout=listen_timeout, phrase_time_limit=phrase_limit)
                command = self.recognizer.recognize_google(audio).lower()
                self._provide_feedback(f"You said: {command}")
                return command
            except sr.WaitTimeoutError:
                if speak_listening_prompt:
                     self._provide_feedback("No speech detected within timeout.")
                return None
            except sr.UnknownValueError:
                self._provide_feedback("Could not understand audio.")
                return None
            except sr.RequestError as e:
                self._provide_feedback(f"Google Speech Recognition service error; {e}")
                return None