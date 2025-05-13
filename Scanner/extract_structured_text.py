import pytesseract
import google.generativeai as genai
import os
import json
import cv2
import numpy as np
import sys 
from dotenv import load_dotenv
import logging.config

logging_config = {
    'version': 1,
    'formatters': {
        'simple': {
            'format': '[%(levelname)s] %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
}

logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)
else:
    pass 


def ocr_image(image_array: np.ndarray):
    if image_array is None or image_array.size == 0:
        logger.warning("📄 OCR: Image is not captured or empty.")
        return "Image is not captured"
    try:
        text = pytesseract.image_to_string(image_array)
        logger.info(f"📄✅ OCR successful. Extracted ~{len(text)} chars.")
        return text
    except Exception as e:
        logger.error(f"📄❌ ERROR in extracting text from image: {e}")
        return f"ERROR in extracting text from image:{e}"

def structure_text_with_gemini_llm(text: str, document_type: str = "general document", custom_instructions: str = ""):
    if not text.strip() or text.startswith("ERROR in extracting text") or text == "Image is not captured":
        logger.warning(f"🧠📄 LLM: No valid text provided for structuring. Received: '{text[:50]}...'")
        return {"error": "No valid text extracted from image to structure."}
    if not google_api_key:
        logger.error("🧠🔑 LLM: Google API key not configured.")
        return {"error": "Google API key not configured."}
    model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.0-pro")
    logger.info(f"🧠 Requesting LLM ({model_name}) for doc_type: '{document_type}'")
    prompt = f"""
    Context: You are an AI assistant that extracts structured information from OCR text.
    Document Type: '{document_type}'. 
    OCR Text:\n---\n{text}\n---\n
    Instructions: {custom_instructions}\n
    Your output MUST be a single, valid JSON object. Do not include any other explanatory text or markdown.
    If information is missing or unclear, use null or an empty string for the corresponding JSON field.
    """
    try:
        model = genai.GenerativeModel(model_name)
        generation_config = genai.types.GenerationConfig(temperature=0.1, response_mime_type="application/json")
        response = model.generate_content(prompt, generation_config=generation_config)
        if response.candidates and response.candidates[0].finish_reason.name == "STOP":
            structured_data_str = response.text
            logger.info("🧠✅ LLM structuring successful.")
            try: return json.loads(structured_data_str)
            except json.JSONDecodeError as e:
                logger.error(f"🧠❌ LLM output not valid JSON: {e}. Output: {structured_data_str[:200]}...")
                return {"error": "Gemini LLM output was not valid JSON", "raw_output": structured_data_str}
        else:
            error_message = "🧠❌ Gemini LLM generation failed/stopped."
            if response.candidates and response.candidates[0].finish_reason: error_message += f" Reason: {response.candidates[0].finish_reason.name}"
            if response.prompt_feedback and response.prompt_feedback.block_reason: error_message += f" Blocked: {response.prompt_feedback.block_reason.name}"
            logger.error(error_message)
            return {"error": error_message, "details": str(response)}
    except Exception as e:
        logger.error(f"🧠❌ Google Gemini API call failed: {str(e)}")
        return {"error": f"Google Gemini API call failed: {str(e)}"}

def process_captured_image_with_gemini(image_frame: np.ndarray, document_type: str = "general document", custom_instructions: str = "Extract key information relevant."):
    if image_frame is None or image_frame.size == 0:
        return {"error": "No image frame provided for processing."}
    logger.info("⚙️ Processing captured image (OCR & LLM)...")
    raw_text = ocr_image(image_frame)
    if raw_text:
        print(f"✅OCR text extract successfully{raw_text}")
    else:
        print(f"❌OCR text extract failed in process_captured_image_with_gemini_function")

    print(f"📄Structuring the extract text from image")
    structured_info = structure_text_with_gemini_llm(raw_text, document_type, custom_instructions)
    return structured_info

