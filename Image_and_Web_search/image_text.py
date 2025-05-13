import logging
import os
from typing import Dict, Any
from langchain_ollama.chat_models import ChatOllama
from langchain_core.messages import HumanMessage
import base64
from dotenv import load_dotenv
import cv2
from typing import Dict,Optional,List,Any
import numpy as np
import pprint

load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")

genai = None
if google_api_key:
    import google.generativeai as genai
    try:
        genai.configure(api_key=google_api_key)
    except Exception as e:
        print(f"Error configuring Google GenAI: {e}")
        genai = None 

tavily_client = None
if tavily_api_key:
    try:
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key=tavily_api_key)
    except ImportError:
        print("Warning: TavilyClient not found. Please install tavily-python.")
    except Exception as e:
        print(f"Error initializing TavilyClient: {e}")
        tavily_client = None

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler(); handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(handler); logger.setLevel(logging.INFO)

def analyze_image_with_langchain_ollama(image_data: bytes, query: str) -> Dict[str, Any]:
    ollama_model_name = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")

    if not image_data:
        logger.error("Langchain Ollama Vision Error: No image data provided.")
        return {"error": "Vision Error: No image data provided."}

    try:
        llm = ChatOllama(
            model=ollama_model_name,
            num_gpu=1
        )
        logger.info("ChatOllama initialized.")

        base64_image = base64.b64encode(image_data).decode('utf-8')

        mime_type = "image/jpeg"
        if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
             mime_type = "image/png"
        elif image_data.startswith(b'RIFF') and image_data[8:12] == b'WEBP':
             mime_type = "image/webp"
        data_uri = f"data:{mime_type};base64,{base64_image}"
        logger.info(f"Image encoded as {mime_type}.")

        message = HumanMessage(
            content=[
                {"type": "text", "text": query},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]
        )
        logger.info("Message created. Invoking LLM...")

        response = llm.invoke([message])
        logger.info("LLM invocation complete.")

        if response and hasattr(response, 'content') and isinstance(response.content, str):
            analysis_text = response.content
            logger.info(f"Langchain Ollama Vision analysis successful.")
            return {"analysis": analysis_text.strip()}
        else:
            logger.error(f"Ollama Vision returned unexpected format: {type(response)} - {str(response)[:500]}...")
            return {"error": "Ollama Vision Error: Unexpected response format from Langchain Ollama.", "details": str(response)}

    except Exception as e:
        logger.error(f"Error during Langchain Ollama Vision interaction ({ollama_model_name}): {e}", exc_info=True)
        error_msg = f"Ollama Vision Error via Langchain: {str(e)}. Check Ollama service, model name ('{ollama_model_name}'), and input data."
        return {"error": error_msg}
    

def perform_web_search(search_query: str) -> Dict[str, Any]:
    if not tavily_client:
        logger.error("🕸️❌ Tavily client not initialized (API key missing?).")
        return {"error": "Search Error: Search client not configured."}
    try:
        logger.info(f"🕸️ Performing Tavily web search for: '{search_query}'")
        response = tavily_client.search(query=search_query, search_depth="basic", include_answer=True, max_results=5, include_raw_content=False)
        logger.info("🕸️✅ Tavily search successful.")
        return {"search_results": response}
    except Exception as e:
        logger.error(f"🕸️❌ Error during Tavily search: {e}", exc_info=True)
        return {"error": f"Search API Error: {str(e)}"}
    
