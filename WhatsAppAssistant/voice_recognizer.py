import pyttsx3
import speech_recognition as sr
import config

class SpeechService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.speaker = pyttsx3.init()

    def speak(self, text):
        print(f"Bot: {text}")
        try:
            self.speaker.say(text)
            self.speaker.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")

    def listen(self, prompt_text=None):
        if prompt_text:
            self.speak(prompt_text)
        with sr.Microphone() as source:
            print("Listening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=config.SPEECH_TIMEOUT_SECONDS,
                    phrase_time_limit=config.SPEECH_PHRASE_LIMIT_SECONDS
                )
                recognized_text = self.recognizer.recognize_google(audio)
                print(f"You: {recognized_text}")
                return recognized_text.lower()
            except sr.WaitTimeoutError:
                self.speak("Listening timed out.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I didn't understand that.")
                return None
            except sr.RequestError as e:
                self.speak(f"Speech recognition service error: {e}")
                return None