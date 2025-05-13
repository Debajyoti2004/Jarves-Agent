import logging
import speech_recognition as sr
import time
import win32com.client
from typing import Any, Dict, List, Optional, Tuple, Callable
import re
import requests
import threading
import os
import sys
from dotenv import load_dotenv
from Authentication import run_jarvis_vision_deepface

load_dotenv()
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.FileHandler("jarvis_main.log"), logging.StreamHandler(sys.stdout)]
    )

WAKE_WORD_VARIATIONS: Tuple[str, ...] = ("hey jarves", "hey jarvis", "jarvis")
EXIT_COMMANDS: Tuple[str, ...] = ("goodbye", "stop", "quit", "exit", "shut down", "that's all")

class Jarvis:
    def __init__(self,
                 wakeup_word: str = "hey jarvis",
                 flask_ui_url: Optional[str] = None,
                 energy_threshold: int = 350,
                 pause_threshold: float = 0.8
                ):
        self.wakeup_word = wakeup_word.lower()
        self.all_wake_words = {self.wakeup_word} | set(WAKE_WORD_VARIATIONS)
        logging.info(f"Initializing Jarvis. Primary wake word: '{self.wakeup_word.title()}'. All variations: {self.all_wake_words}")
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.speaker = self._initialize_speaker()
        self.recognizer.pause_threshold = pause_threshold
        self.recognizer.energy_threshold = energy_threshold
        self.flask_ui_url = flask_ui_url or os.getenv("FLASK_UI_URL", "http://127.0.0.1:5000")
        if self.flask_ui_url:
            self._notify_ui("jarvis_status", text="Jarvis Initializing")
        self.agent = None

    def _initialize_speaker(self) -> Optional[win32com.client.Dispatch]:
        try:
            speaker_obj = win32com.client.Dispatch("SAPI.SpVoice")
            speaker_obj.Volume = 100
            speaker_obj.Rate = 0
            logging.info("SAPI Speaker initialized successfully.")
            return speaker_obj
        except Exception as e:
            logging.error(f"Failed to initialize SAPI speaker: {e}. Text-to-speech will be unavailable.", exc_info=False)
            return None

    def _sanitize_for_speech(self, text: str) -> str:
        if not isinstance(text, str): text = str(text)
        text = re.sub(r'(\*\*|__)(.*?)(\1)', r'\2', text)
        text = re.sub(r'(\*|_)(.*?)(\1)', r'\2', text)
        text = re.sub(r'```[a-zA-Z]*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'`(.*?)`', r'\1', text)
        text = re.sub(r'^\s*#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[\*\-\+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.replace("...", ". ")
        return text.strip()

    def _notify_ui(self, event_type: str, text: Optional[str] = None):
        if not self.flask_ui_url: return
        payload = {"event": event_type}
        if text: payload["text"] = text
        def send_request_thread():
            try:
                requests.post(f"{self.flask_ui_url}/ui_event", json=payload, timeout=0.5)
            except requests.exceptions.RequestException as e_req:
                logging.debug(f"UI notification failed for event '{event_type}': {e_req}")
                pass
        threading.Thread(target=send_request_thread, daemon=True).start()

    def speak(self, data: Any):
        text_to_speak_orig = str(data)
        self._notify_ui("display_text", text=text_to_speak_orig)
        if not self.speaker:
            print(f"Jarvis (TTS unavailable): {text_to_speak_orig[:150]}...")
            return
        try:
            sanitized_text = self._sanitize_for_speech(text_to_speak_orig)
            if not sanitized_text.strip():
                self._notify_ui("speaking_end")
                return
            print(f"Jarvis says: {sanitized_text}")
            self._notify_ui("speaking_start", text=sanitized_text)
            self.speaker.Speak(sanitized_text)
        except Exception as e:
            logging.error(f"Speech error. Original text (start): '{text_to_speak_orig[:50]}'. Sanitized text (start): '{sanitized_text[:50]}'. Error: {e}", exc_info=False)
        finally:
            self._notify_ui("speaking_end")

    def listen_for_wake_word(self) -> bool:
        with self.microphone as source:
            while True:
                print("\n👂 Listening for wake word...")
                self._notify_ui("listening_wake_word", text="Listening for wake word...")
                try:
                    audio = self.recognizer.listen(source, phrase_time_limit=3, timeout=5)
                    query = self.recognizer.recognize_google(audio, language='en-US').lower()
                    logging.info(f"Heard (wake attempt): '{query}'")
                    if any(word in query for word in self.all_wake_words):
                        self._notify_ui("wake_word_detected", text=f"Heard: '{query}'")
                        self.speak("Yes Sir?")
                        return True
                    logging.info(f"Audio recognized ('{query}') but not a wake word. Proceeding to visual check.")
                except sr.WaitTimeoutError:
                    logging.debug("Audio listen timed out (no speech detected or too short). Proceeding to visual check.")
                except sr.UnknownValueError:
                    logging.debug("Could not understand audio. Proceeding to visual check.")
                except sr.RequestError as e_req:
                    logging.warning(f"Speech service connection issue for wake word: {e_req}. Proceeding to visual check.")
                    self.speak("Speech service seems to be having an issue.")
                    time.sleep(2)
                except Exception as e_audio:
                    logging.error(f"Unexpected error during audio listening for wake word: {e_audio}", exc_info=True)
                    time.sleep(1)

                self._notify_ui("visual_check_start", text="Attempting visual master detection...")
                logging.info("Attempting visual master detection...")
                try:
                    if run_jarvis_vision_deepface():
                        print("Jarvis is Online. Master Face detected visually.")
                        self._notify_ui("visual_wake_detected", text="Master detected visually.")
                        return True
                    else:
                        logging.info("Visual master detection did not result in activation. Looping back to listen for wake word.")
                except Exception as e_visual:
                    logging.error(f"Error during visual master detection call: {e_visual}", exc_info=True)
                    self.speak("There was an issue with the visual detection system.")

    def process_command(self) -> Optional[bool]:
        with self.microphone as source:
            self._notify_ui("listening_command", text="Awaiting your command...")
            self.speak("I'm listening.")
            print("🎤 Listening for command...")
            try:
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
                command = self.recognizer.recognize_google(audio, language='en-US').lower()
                logging.info(f"Command received: '{command}'")
                self._notify_ui("command_recognised", text=f"You said: {command}")
                if any(trigger in command for trigger in EXIT_COMMANDS):
                    self.speak("Understood. Standing by.")
                    self._notify_ui("idle", text="Jarvis Idle.")
                    return True
                if self.agent:
                    self._notify_ui("processing_command", text=f"Processing: {command}")
                    agent_response = self.agent.handle_command(command)
                    if agent_response:
                        self.speak(agent_response)
                    else:
                        logging.info("Agent processed command without a specific verbal response to speak.")
                    self._notify_ui("command_processed", text="Processing complete.")
                else:
                    self.speak(f"I understood your command as: {command}. However, no agent is currently assigned to handle it.")
                return None
            except sr.WaitTimeoutError:
                self.speak("I didn't hear a command in time.")
                return None
            except sr.UnknownValueError:
                self.speak("My apologies, I didn't quite catch that command.")
                return None
            except sr.RequestError as e_req:
                logging.warning(f"Speech service issue for commands: {e_req}")
                self.speak("I'm having trouble reaching the speech service for command processing.")
                return None
            except Exception as e:
                logging.error(f"Error processing command: {e}", exc_info=True)
                self.speak("An internal error occurred while I was processing your command.")
                return None

    def run(self, agent_instance = None):
        self.agent = agent_instance
        if self.agent:
            logging.info("Jarvis run method received an agent instance.")
        else:
            logging.warning("Jarvis run method did NOT receive an agent instance. Command processing will be limited.")
        try:
            self._notify_ui("jarvis_status", text="Jarvis Systems Online")
            self.speak("Jarvis systems online.")
            while True:
                if self.listen_for_wake_word():
                    self._notify_ui("active_listening", text="Jarvis Active!")
                    while True:
                        should_go_idle = self.process_command()
                        if should_go_idle is True:
                            break
                else:
                    logging.warning("listen_for_wake_word returned False, which is unexpected. Restarting listen cycle.")
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\nJarvis shutting down due to KeyboardInterrupt...")
            if self.speaker:
                 try: self.speak("Shutting down systems. Goodbye, sir.")
                 except Exception: pass
            self._notify_ui("jarvis_status", text="Jarvis Offline (Interrupted)")
        except Exception as e:
            logging.critical(f"Jarvis encountered a critical error: {e}", exc_info=True)
            if self.speaker:
                try: self.speak("A critical system error has occurred. I need to shut down.")
                except Exception: pass
            self._notify_ui("jarvis_status", text=f"Jarvis Critical Error: {str(e)[:50]}")
        finally:
            logging.info("Jarvis application finished.")
            self._notify_ui("jarvis_status", text="Jarvis Offline")
