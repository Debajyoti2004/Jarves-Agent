import os
import base64
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_MODEL = "llava:latest"
OLLAMA_MODEL_NAME = os.getenv("OLLAMA_VISION_MODEL", DEFAULT_OLLAMA_MODEL)
TEST_IMAGE_PATH = "test_image.png"
TEST_QUERY = "What objects are prominent in this image?"

try:
    from langchain_community.chat_models import ChatOllama
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    logger.error("langchain-community not found. Please run 'pip install langchain-community'")
    LANGCHAIN_AVAILABLE = False

def run_vision_test():
    if not LANGCHAIN_AVAILABLE:
        logger.critical("Cannot run test without langchain-community.")
        return

    if not os.path.exists(TEST_IMAGE_PATH):
        logger.error(f"Test image not found at path: {TEST_IMAGE_PATH}")
        print(f"❌ ERROR: Test image '{TEST_IMAGE_PATH}' not found. Please create it or update the path.")
        return

    logger.info(f"Attempting to test Ollama vision model '{OLLAMA_MODEL_NAME}' with image '{TEST_IMAGE_PATH}'.")
    logger.info(f"Query: '{TEST_QUERY}'")

    try:
        with open(TEST_IMAGE_PATH, "rb") as image_file:
            image_bytes = image_file.read()
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        mime_type = "image/jpeg"
        if TEST_IMAGE_PATH.lower().endswith(".png"): mime_type = "image/png"
        elif TEST_IMAGE_PATH.lower().endswith(".webp"): mime_type = "image/webp"
        data_uri = f"data:{mime_type};base64,{base64_image}"
        logger.info("Image read and encoded successfully.")
    except Exception as e:
        logger.error(f"Failed to read or encode image: {e}", exc_info=True)
        print(f"❌ ERROR: Could not read or encode the image file: {e}")
        return

    try:
        logger.info("Initializing ChatOllama...")
        llm = ChatOllama(
            model=OLLAMA_MODEL_NAME,
            num_gpu=1)
        logger.info(f"ChatOllama initialized with model: {OLLAMA_MODEL_NAME}")

        message = HumanMessage(
            content=[
                {"type": "text", "text": TEST_QUERY},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]
        )
        logger.info("Message payload created. Invoking model...")

        response = llm.invoke([message])
        logger.info("Model invocation complete.")

        if response and hasattr(response, 'content') and isinstance(response.content, str):
            analysis_text = response.content.strip()
            logger.info("✅ Ollama Vision test successful.")
            print("\n--- Ollama Vision Response ---")
            print(analysis_text)
            print("----------------------------")
        else:
            logger.error(f"Ollama Vision response was empty or in unexpected format: {type(response)}")
            print("\n❌ ERROR: Received an empty or unexpected response from Ollama.")
            print(f"   Raw response type: {type(response)}")
            if response: print(f"   Raw response snippet: {str(response)[:500]}...")

    except Exception as e:
        logger.error(f"Error during Ollama interaction: {e}", exc_info=True)
        print(f"\n❌ ERROR: An error occurred while interacting with Ollama.")
        print(f"   Details: {e}")
        print(f"   Possible causes:")
        print(f"     - Is the Ollama service running?")
        print(f"     - Did you pull the correct model name ('{OLLAMA_MODEL_NAME}')?")
        print(f"     - Is the OLLAMA_VISION_MODEL in your .env file correct?")
        print(f"     - Is the network connection to Ollama ok (if not running on localhost)?")

if __name__ == "__main__":
    run_vision_test()