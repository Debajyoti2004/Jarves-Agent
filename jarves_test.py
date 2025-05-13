import logging
import speech_recognition as sr
import time
import win32com.client
from typing import Any, Dict, List, Optional, Tuple
import re
import requests
import threading
import os
from dotenv import load_dotenv

from MainAgent import Agent
print(f"Agent imnported successfully")
AGENT_AVAILABLE=True


from JarvesVoice import Jarvis

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("jarvis_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.info("Starting Jarvis application directly (jarves.py)...")
    agent_to_pass = None
    if AGENT_AVAILABLE:
        try:
            agent_to_pass = Agent()
            logging.info("Langchain Agent initialized for Jarvis direct run.")
        except Exception as agent_init_err:
            logging.error(f"Failed to initialize Langchain Agent: {agent_init_err}", exc_info=True)
    else:
        logging.warning("Agent module not available for Jarvis direct run.")
    
    if agent_to_pass is None:
        class MockSyncAgent:
            def handle_command(self, command_text: str) -> str:
                logger.info(f"MockSyncAgentHandler received: {command_text}")
                if "hello" in command_text: return "Hello from mock sync handler!"
                return f"Mock sync handler received: '{command_text}'."
        agent_to_pass = MockSyncAgent()
        logging.info("Using Sync Mock Agent Handler for Jarvis direct run.")

    jarvis_bot = Jarvis(wakeup_word="jarvis")
    jarvis_bot.run(agent_instance=agent_to_pass)
    logging.info("Jarvis application (jarves.py __main__) finished.")