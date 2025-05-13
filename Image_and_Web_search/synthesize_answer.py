import logging
import json
import os
from typing import Optional, Dict, Any
from langchain_core.tools import tool, ToolException
from langchain_core.runnables import RunnableConfig
import time
import requests
import numpy as np
import cv2
from pydantic import BaseModel, Field
from dotenv import load_dotenv

try:
    from jarves_test import Jarvis
except ImportError:
    print("Warning: Could not import helper modules (Scanner, jarves). Using dummy functions.")
    def capture_image_from_camera(): return None
    class Jarvis:
        def speak(self, text): print(f"Mock Speak: {text}")

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


def synthesize_answer_with_gemini(original_query: str, search_results_data: Optional[Dict], image_analysis_text: Optional[str] = None) -> Dict[str, Any]:
    if not genai or not google_api_key:
        return {"error": "Synthesis Error: Google API Key or GenAI module not configured."}
    if not search_results_data and not image_analysis_text:
         return {"error": "Synthesis Error: No search results or image analysis provided."}

    search_context = "No web search results available or search failed."
    tavily_answer = None
    search_snippets = []
    if search_results_data and "search_results" in search_results_data:
         tavily_results = search_results_data["search_results"]
         tavily_answer = tavily_results.get("answer")
         if tavily_results.get("results"):
             search_snippets = [f"Source: {res.get('title', 'N/A')}\nContent: {res.get('content', 'N/A')}" for res in tavily_results["results"]]
             search_context = "\n\n".join(search_snippets)
             if tavily_answer: search_context = f"Direct Answer from Search: {tavily_answer}\n\nSupporting Snippets:\n{search_context}"
         elif tavily_answer: search_context = f"Direct Answer from Search: {tavily_answer}"

    prompt_lines = ["You are Jarvis, synthesizing information to answer a user's query.", f"Original User Query: {original_query}"]
    if image_analysis_text: prompt_lines.append(f"\nAnalysis of Provided Image: {image_analysis_text}")
    prompt_lines.append("\nWeb Search Results Context:"); prompt_lines.append(search_context)
    prompt_lines.append("\nTask: Based *only* on the provided image analysis (if any) and the web search results context, provide a concise, helpful, and direct answer to the original user query.")
    prompt_lines.append("Do not mention your sources unless directly asked. Synthesize the information into a natural language response.")
    prompt_lines.append("If the provided context does not adequately answer the query, state that you couldn't find a definitive answer based on the search.")
    full_prompt = "\n".join(prompt_lines)
    logger.info("🧠 Synthesizing final answer using Gemini Text...")

    try:
        text_model = genai.GenerativeModel(os.getenv("GOOGLE_LLM_MODEL", "gemini-1.0-pro"))
        generation_config = genai.types.GenerationConfig(temperature=0.3)
        response = text_model.generate_content(full_prompt, generation_config=generation_config)
        response.resolve()
        if response.candidates and response.candidates[0].finish_reason.name == "STOP":
            final_answer = response.text
            logger.info("🧠✅ Final answer synthesis successful.")
            return {"answer": final_answer}
        else:
            error_msg = "🧠❌ Synthesis LLM generation failed or was stopped."
            return {"error": error_msg, "details": str(response)}
    except Exception as e:
        logger.error(f"🧠❌ Error calling Gemini Text API for synthesis: {e}", exc_info=True)
        return {"error": f"Synthesis LLM Error: {str(e)}"}