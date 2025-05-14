import logging.config
import uuid
import json
import sys
import os
from typing import Optional, List, Dict, Any, Tuple
from langchain_core.tools import tool, BaseTool
from langchain.schema import Document
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException
import time
import requests
import numpy as np
import cv2
from ultralytics import YOLO
from pydantic import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
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

try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path: sys.path.append(project_root)
    from utils import (
        open_app, 
        open_website
    )
    from WebScrappingAgent import (
        get_amazon_search_url, 
        extract_amazon_info, 
        generate_travel_search_url, 
        extract_hotel_info, 
        generate_search_url, 
        extract_flight_info
    )
    from StructuredOutput import (
        structure_products_with_cohere, 
        structure_hotels_with_cohere, 
        structure_flight_list_with_cohere
    )
    from Scanner import (
        capture_image_from_camera, 
        process_captured_image_with_gemini,
        apply_brightness_contrast,
        put_text_with_bg
    )
    from Image_and_Web_search import (
        synthesize_answer_with_gemini,
        perform_web_search,
        analyze_image_with_langchain_ollama
    )
    from JarvesVoice import Jarvis
   
    from CodeDebugger import (
        custom_code_agent,
        open_code_input_portal
    )
    try:
        from EmailAccessAgent import (
            get_unread_emails, draft_reply_with_llm, send_email,
            get_conversation_history, add_to_memory, mark_email_as_read, get_gmail_service
        )
        EMAIL_TOOL_AVAILABLE = True
    except ImportError as e:
        print(f"Could not import email_tool_logic: {e}. Email tool will be disabled.")
        EMAIL_TOOL_AVAILABLE = False 

    from ResumeAnalyser import extract_text_from_pdf,analyze_resume_with_llm
except ImportError as e:
    print(f"FATAL: Could not import required project modules: {e}. Check paths and file locations.")
    raise ImportError(f"Failed to import project modules: {e}") from e

try:
    speaker = Jarvis()
except Exception as speaker_err:
    print(f"ERROR initializing Jarvis speaker: {speaker_err}. Speech output will be limited.")
    

logging_config = {
    'version': 1,
    'formatters': {'simple': {'format': '[%(levelname)s] %(message)s',}},
    'handlers': {'console': {'class': 'logging.StreamHandler','formatter': 'simple','level': 'INFO',},},
    'root': {'level': 'INFO','handlers': ['console'],},
    'loggers': {
        'JarvesScannerTool': {'handlers': ['console'],'level': 'INFO','propagate': False},
        'CodeAgentTool': {'handlers': ['console'],'level': 'INFO','propagate': False},
        __name__: {'handlers': ['console'],'level': 'INFO','propagate': False}
        }
}
logging.config.dictConfig(logging_config)
logger = logging.getLogger(__name__)

class OpenAppInput(BaseModel):
    app_name: str = Field(description="Name of the application to open (e.g., 'notepad', 'calculator', 'chrome').")

class OpenWebsiteInput(BaseModel):
    web_site_name: str = Field(description="Name of the website to open (e.g., 'google', 'wikipedia').")

class AmazonScraperInput(BaseModel):
    product_name: str = Field(description="Name of the product to search.")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="Optional dictionary of filters like {'rating': 'above 4.0', 'price': 'under 5000', 'prime_eligible': True}.")

class GoogleHotelInput(BaseModel):
    location: str = Field(description="Destination city and country (e.g., 'London, UK', 'Paris, France').")
    check_in_date: str = Field(description="Check-in date in YYYY-MM-DD format.")
    check_out_date: str = Field(description="Check-out date in YYYY-MM-DD format.")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="Optional dictionary of hotel filters like {'price_max': 300, 'rating_min': 4.0, 'amenities': ['Free Breakfast', 'Pool']}.")

class GoogleFlightInput(BaseModel):
    to_place: str = Field(description="Arrival location (e.g., 'LAX', 'London').")
    departure_date: str = Field(description="Outbound flight date in YYYY-MM-DD format.")
    returned_date: str = Field(description="Return flight date in YYYY-MM-DD format.")
    from_place: Optional[str] = Field(default=None, description="Optional: Departure location (e.g., 'JFK', 'New York'). Highly recommended.")
    user_preferences: Optional[Dict[str, Any]] = Field(default=None, description="Optional dictionary of flight filters like {'num_passengers': 1, 'max_stops': 0, 'preferred_airline': 'Delta'}.")

class JarvesScannerInput(BaseModel):
    document_type: str = Field(default="general document", description="Optional: Type of document being scanned (e.g., 'ID card', 'receipt', 'note', 'invoice'). Helps guide extraction.")
    custom_instructions: str = Field(default="Extract all key information relevant to the document type.", description="Optional: Specific instructions for the LLM on what information to extract or how.")

class CodeAgentInput(BaseModel):
    end_keyword: str = Field(default="ENDCODE", description="Optional: The keyword the user types on a new line to signal the end of their code input. Case-insensitive.")
    
class WebImageSearchInput(BaseModel):
    query: str = Field(description="The user's question or search query. If an image is involved, phrase the query in relation to the image (e.g., 'What type of bird is this?', 'Summarize the text in this document image').")
    include_image: bool = Field(default=False, description="Set to True if the query requires capturing and analyzing an image from the camera along with the text query.")

class VisualObjectFinderInput(BaseModel):
    object_name: str = Field(description="The name of the object the user wants to find visually (e.g., 'keys', 'bottle', 'laptop', 'backpack', 'person').")
    confidence_threshold: float = Field(default=0.4, description="Minimum confidence score (0.0 to 1.0) for detecting the object. Lower values detect more but might be less accurate. Default is 0.4.")
    camera_index: int = Field(default=0, description="Index of the camera to use (usually 0 for the default webcam).")
    search_duration_seconds: int = Field(default=30, description="Maximum time in seconds to keep the camera feed open while searching. Default 30.")

class EmailToolInput(BaseModel):
    action: str = Field(description="Action: 'check_new' or 'send_draft'.")
    max_emails_to_check: int = Field(default=3, description="For 'check_new'.")
    recipient_email: Optional[str] = Field(default=None, description="For 'send_draft'.")
    subject: Optional[str] = Field(default=None, description="For 'send_draft'.")
    body: Optional[str] = Field(default=None, description="For 'send_draft'.")
    original_message_id: Optional[str] = Field(default=None, description="For replies (send_draft).")
    original_thread_id: Optional[str] = Field(default=None, description="For replies (send_draft).")
    original_sender: Optional[str] = Field(default=None, description="Original sender for memory.")
    original_subject: Optional[str] = Field(default=None, description="Original subject for memory.")
    original_body_snippet: Optional[str] = Field(default=None, description="Original body for memory.")

class ResumeAnalyzerInput(BaseModel):
    job_description_end_keyword: str = Field(default="END_JD", description="Keyword to end job description input.")
    resume_pdf_path: Optional[str] = Field(default=None, description="Optional path to resume PDF. Uses env var if None.")


@tool(args_schema=OpenAppInput)
def open_app_tool(app_name: str) -> str:
    """
    ✅ Use this tool to open an app on the laptop. Args defined in schema.
    """
    # if app_name.startswith("{"):
    #     app_name = json.loads(app_name).get("app_name","chrome")

    logger.info(f"Attempting to open app: {app_name}")
    speaker.speak(f"Certainly.Attempting to open {app_name} for you.")
    time.sleep(0.5)
    try:
        success = open_app(app_name=app_name)
        if success:
            logger.info(f"✅ App '{app_name}' opened successfully.")
            speaker.speak(f"{app_name} has been opened successfully,Boss.")
            return f"✅ Successfully opened app: {app_name}"
        else:
            logger.warning(f"⚠️ Failed to open app '{app_name}'.")
            speaker.speak(f"I was unable to open {app_name}. It might not be installed or found.")
            return f"⚠️ Could not open app: {app_name}. It might not be installed or found."
    except Exception as e:
        logger.error(f"❌ Unexpected error opening app '{app_name}': {e}", exc_info=True)
        speaker.speak(f"An unexpected error occurred while trying to open {app_name}.")
        return f"❌ Error opening app: {app_name}. Reason: {e}"

@tool(args_schema=OpenWebsiteInput)
def open_website_tool(web_site_name: str) -> str:
    """
    ✅ Use this tool to open a website. Args defined in schema.
    """
    # if web_site_name.startswith("{"):
    #     web_site_name = json.loads(web_site_name).get("web_site_name","google")

    logger.info(f"Attempting to open website: '{web_site_name}'")
    speaker.speak(f"Accessing the web. Opening {web_site_name} now.")
    time.sleep(0.5)
    try:
        success = open_website(site_name=web_site_name)
        if success:
            logger.info(f"✅ Website '{web_site_name}' opened successfully.")
            speaker.speak(f"The website {web_site_name} is now openned successfully, Boss")
            return f"✅ Website {web_site_name} opened successfully"
        else:
            logger.warning(f"⚠️ Failed to open website '{web_site_name}'.")
            speaker.speak(f"I encountered an issue opening {web_site_name}.Please check the URL or your network connection.")
            return f"⚠️ Could not open website: {web_site_name}. Check the URL or network."
    except Exception as e:
        logger.error(f"❌ Unexpected error opening website '{web_site_name}': {e}", exc_info=True)
        speaker.speak(f"An unexpected error occurred with the website request for {web_site_name}.")
        return f"❌ Error opening website: {web_site_name}. Reason: {e}"

@tool(args_schema=AmazonScraperInput)
def amazon_web_scrapper(
    product_name: str,
    user_preferences: Optional[Dict[str, Any]] = None,
    config: Optional[RunnableConfig] = None
) -> str:
    """
    🛒 Searches for products on Amazon based on a product name and optional user preferences.
    Use this tool when the user asks to find or search for items for sale on Amazon.
    The 'product_name' is what the user is looking for (e.g., "wireless headphones", "laptop stand").
    'user_preferences' is an optional dictionary for filters like:
    {"rating_min": 4.0, "price_max": 5000, "prime_eligible": true}.
    Returns a JSON string containing a list of product details or an error message.
    """
    # if product_name.startswith("{"):
    #     try:
    #         input_data = json.loads(product_name)
    #         product_name = input_data.get("product_name", "ASUS Gaming Laptop")
    #         user_preferences = input_data.get("user_preferences", user_preferences if user_preferences is not None else {"rating_min": 3})
        
    #     except json.JSONDecodeError as e:
    #         logger.error(f"Error parsing tool_input as JSON for Amazon: {e}")
    #         return json.dumps({"status": "error", "message": "Invalid JSON input format for product_name field."})

    prefs_str = f" with preferences {user_preferences}" if user_preferences else ""
    logger.info(f"Tool: Starting Amazon search for '{product_name}'{prefs_str}")
    speaker.speak(f"Initiating search on Amazon for {product_name}{prefs_str}. One moment Sir.")
    try:
        search_url = get_amazon_search_url(query=product_name, domain="in", use_brightdata=False)
        speaker.speak("I have the search parameters. Accessing Amazon now.")
        time.sleep(0.5)
        raw_product_data = extract_amazon_info(search_url=search_url, user_preferences=user_preferences)
        if raw_product_data is None:
            raw_product_data = []
        logger.info(f"Extracted {len(raw_product_data)} raw Amazon entries.")
        speaker.speak(f"I've gathered {len(raw_product_data)} initial product listings. Now structuring the data.")
        
        if not raw_product_data:
            speaker.speak(f"I couldn't find any initial listings for {product_name} on Amazon, sir.")
            return json.dumps({"status": "not_found", "message": f"No product listings found for {product_name}."})
        
        if not COHERE_API_KEY:
            return json.dumps({"status": "error_configuration", "message": "Cohere API key missing for structuring."})
        
        product_list = structure_products_with_cohere(raw_product_data_text=raw_product_data, max_input_chars=100000)
        if not product_list:
            speaker.speak(f"After processing, I couldn't identify suitable products for {product_name} matching your criteria.")
            return json.dumps({"status": "not_found_structured", "message": "Could not structure product data.", "raw_data": raw_product_data}, indent=2)
        
        logger.info(f"✅ Successfully retrieved {len(product_list)} product(s) for: '{product_name}'")
        speaker.speak(f"Search complete. I found {len(product_list)} product options for {product_name}.")
        return json.dumps({"status": "success", "data": product_list}, indent=2)
    
    except requests.exceptions.RequestException as e:
         logger.error(f"❌ Network error (Amazon): {e}")
         speaker.speak("I'm experiencing a network issue while trying to reach Amazon.")
         return json.dumps({"status": "error", "message": "Network error during Amazon search."})
    
    except Exception as e:
         logger.error(f"❌ Unexpected error (Amazon): {e}", exc_info=True)
         speaker.speak("An unexpected error occurred during the Amazon search.")
         return json.dumps({"status": "error", "message": f"Amazon search failed: {str(e)}"})

@tool(args_schema=GoogleHotelInput)
def google_hotel_scrapper(
    location: str,
    check_in_date: str,
    check_out_date: str,
    user_preferences: Optional[Dict[str, Any]] = None
) -> str:
    """
    🏨 Finds hotels in a specified location for given check-in and check-out dates.
    Use this tool when the user asks to find hotels, accommodations, or places to stay.
    'location' is the destination (e.g., "Paris, France").
    'check_in_date' and 'check_out_date' must be in YYYY-MM-DD format.
    'user_preferences' is an optional dictionary for filters like:
    {"price_max": 300, "rating_min": 4.0, "amenities": ["Pool", "Free WiFi"]}.
    Returns a JSON string with a list of hotel details or an error/status message.
    """
    # if location.startswith("{"):
    #     try:
    #         input_data = json.loads(location)
    #         location = input_data.get("location", "Kolkata")
    #         check_in_date = input_data.get("check_in_date", "2025-09-11")
    #         check_out_date = input_data.get("check_out_date", "2025-09-18")
    #         user_preferences = input_data.get("user_preferences", user_preferences)
        
    #     except json.JSONDecodeError as e:
    #         logger.error(f"Error parsing tool_input as JSON for Hotel: {e}")
    #         return json.dumps({"status": "error", "message": "Invalid JSON input format for location field."})

    prefs = user_preferences or {}
    prefs_str = f" with preferences {prefs}" if prefs else ""
    logger.info(f"Tool: Google Hotel search for '{location}' ({check_in_date} to {check_out_date}){prefs_str}")
    speaker.speak(f"Searching for hotels in {location} from {check_in_date} to {check_out_date}{prefs_str}. Please wait...")
    
    try:
        search_url = generate_travel_search_url(user_proxy=False, location=location, check_in_date=check_in_date, check_out_date=check_out_date)
        speaker.speak("I'm now accessing Google Hotels with the search parameters.")
        time.sleep(0.5)
        raw_hotel_data = extract_hotel_info(search_url=search_url, user_preferences=prefs)
        
        if raw_hotel_data is None: 
            raw_hotel_data = []
        logger.info(f"Extracted {len(raw_hotel_data)} raw hotel entries.")
        speaker.speak(f"I've retrieved {len(raw_hotel_data)} initial hotel listings. Processing this information now.")
        
        if not raw_hotel_data:
            speaker.speak(f"I was unable to find any hotel listings for {location} on those dates.")
            return json.dumps({"status": "not_found", "message": f"No hotel listings found for {location}."})
        
        if not COHERE_API_KEY:
            return json.dumps({"status": "error_configuration", "message": "Cohere API key missing for structuring."})
        hotel_list = structure_hotels_with_cohere(raw_hotel_data_input=raw_hotel_data, max_input_chars=100000)
        
        if not hotel_list:
            speaker.speak(f"I couldn't structure the hotel data as expected for {location}.")
            return json.dumps({"status": "not_found_structured", "message": "Could not structure hotel data.", "raw_data": raw_hotel_data}, indent=2)
        
        logger.info(f"✅ Successfully retrieved {len(hotel_list)} hotel(s) for: '{location}'")
        speaker.speak(f"Hotel search complete. I found {len(hotel_list)} options in {location}.")
        return json.dumps({"status": "success", "data": hotel_list}, indent=2)
    
    except ToolException as te:
        logger.error(f"❌ Tool Input Error (Hotels): {te}", exc_info=True)
        speaker.speak(f"There was an input error for the hotel search: {te}")
        return json.dumps({"status": "error", "message": f"Hotel search input error: {te}"})
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error (Hotels): {e}")
        speaker.speak("A network problem occurred while searching for hotels.")
        return json.dumps({"status": "error", "message": "Network error during hotel search."})
    
    except Exception as e:
        logger.error(f"❌ Unexpected error (Hotels): {e}", exc_info=True)
        speaker.speak("An unexpected error occurred while searching for hotels.")
        return json.dumps({"status": "error", "message": f"Hotel search failed: {str(e)}"})

@tool(args_schema=GoogleFlightInput)
def google_flight_scrapper(
    to_place: str,
    departure_date: str,
    returned_date: str,
    from_place: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
    config: Optional[RunnableConfig] = None
) -> str:
    """
    ✈️ Retrieves round-trip flight details based on origin, destination, and dates.
    Use this tool when the user asks to find flights.
    'to_place' is the arrival city/airport.
    'departure_date' and 'returned_date' must be in YYYY-MM-DD format.
    'from_place' is the departure city/airport (optional but recommended).
    'user_preferences' is an optional dictionary for filters like:
    {"num_passengers": 1, "max_stops": 0, "preferred_airline": "AirlineName"}.
    Returns a JSON string with a list of flight options or an error/status message.
    """
    # if to_place.startswith("{"):
    #     try:
    #         input_data = json.loads(to_place)
    #         to_place = input_data.get("to_place", "Delhi")
    #         departure_date = input_data.get("departure_date", "2025-09-15")
    #         returned_date = input_data.get("returned_date", "2025-09-17")
    #         from_place = input_data.get("from_place", from_place if from_place is not None else "Kolkata")
    #         user_preferences = input_data.get("user_preferences", user_preferences if user_preferences is not None else {"rating_min":3})
        
    #     except json.JSONDecodeError as e:
    #         logger.error(f"Error parsing tool_input as JSON for Flight: {e}")
    #         return json.dumps({"status": "error", "message": "Invalid JSON input format for to_place field."})

    from_loc = from_place or "your current location"
    prefs = user_preferences or {}
    prefs_str = f" with preferences {prefs}" if prefs else ""
    logger.info(f"Tool: Google Flight search: {from_loc} -> {to_place} ({departure_date} to {returned_date}){prefs_str}")
    speaker.speak(f"Searching for flights from {from_loc} to {to_place}, departing {departure_date} and returning {returned_date}{prefs_str}.")
    
    if not from_place: 
        speaker.speak("Departure location not specified, results might be broad.")
    try:
        search_url = generate_search_url(from_airport=from_place, to_airport=to_place, depart_on=departure_date, return_on=returned_date)
        speaker.speak("Accessing Google Flights...")
        time.sleep(0.5)
        raw_flight_data = extract_flight_info(search_url=search_url, user_preferences=prefs)
        
        if raw_flight_data is None: 
            raw_flight_data = []
        logger.info(f"Extracted {len(raw_flight_data)} raw flight entries.")
        speaker.speak(f"I've found {len(raw_flight_data)} potential flight itineraries. Now structuring this data.")
        
        if not raw_flight_data:
            speaker.speak(f"No flight information found for {from_loc} to {to_place} on those dates.")
            return json.dumps({"status": "not_found", "message": f"No flights found for {from_loc} -> {to_place}."})
        
        if not COHERE_API_KEY:
            return json.dumps({"status": "error_configuration", "message": "Cohere API key missing for structuring."})
        flight_group_list = structure_flight_list_with_cohere(raw_flight_list_input=raw_flight_data, max_input_chars=100000)
        
        if not flight_group_list:
            speaker.speak(f"Unable to structure flight data for this route.")
            return json.dumps({"status": "not_found_structured", "message": "No suitable flights found after structuring.", "raw_data": raw_flight_data}, indent=2)
        
        logger.info(f"✅ Successfully found {len(flight_group_list)} round-trip flight option(s).")
        speaker.speak(f"Flight search complete. I have {len(flight_group_list)} round-trip options for you.")
        return json.dumps({"status": "success", "data": flight_group_list}, indent=2)
    
    except ToolException as te:
        logger.error(f"❌ Tool Input Error (Flights): {te}", exc_info=True)
        speaker.speak(f"There was an input error for the flight search: {te}")
        return json.dumps({"status": "error", "message": f"Flight search input error: {te}"})
    
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error (Flights): {e}")
        speaker.speak("I'm encountering a network issue while searching for flights.")
        return json.dumps({"status": "error", "message": "Network error during flight search."})
    
    except Exception as e:
        logger.error(f"❌ Unexpected error (Flights): {e}", exc_info=True)
        speaker.speak("An unexpected error occurred during the flight search.")
        return json.dumps({"status": "error", "message": f"Flight search failed: {str(e)}"})
    

@tool(args_schema=JarvesScannerInput)
def jarves_ocr_scanner(
    document_type: str = "general document",
    custom_instructions: str = "Extract all key information. If it's an ID, get name, ID number, phone number. If a receipt, get store, total, date, items. For notes, summarize key points."
) -> str:
    """
    📸 Scans a physical document using the camera. Args defined in schema. Returns JSON string with structured data or error.
    """
    # if document_type.startswith("{"):
    #     input = json.loads(document_type)
    #     document_type = input.get("document_type","general document")
    #     custom_instructions = input.get("custom_instructions","Extract all key information. If it's an ID, get name, ID number, DOB, expiry. If a receipt, get store, total, date, items. For notes, summarize key points.")


    logger.info(f"🛠️✨ Jarves Scanner: '{document_type}'")
    speaker.speak(f"Initializing scanner for a {document_type}.Please prepare the document.")
    captured_image: np.ndarray = None
    try:
        time.sleep(0.5)
        speaker.speak("Activating visual input. Camera module is now live. Please position the document.")
        captured_image = capture_image_from_camera()
        if captured_image is not None and captured_image.size > 0:
            logger.info("📸✅ Image captured.")
            speaker.speak("Image acquired successfully.")
        else:
            logger.warning("📸⚠️ No image captured or scan cancelled.")
            speaker.speak("It appears the scan was cancelled or no image was acquired. Aborting scan.")
            return json.dumps({"status": "cancelled", "message": "Image capture cancelled or failed by user."}, indent=2)
    except Exception as e:
        logger.error(f"📸💥 Capture error: {e}", exc_info=True)
        speaker.speak(f"I've encountered a critical error during image capture: {str(e)}. Unable to proceed.")
        return json.dumps({"status": "error", "message": f"Critical error during image capture: {str(e)}"}, indent=2)

    if captured_image is not None and captured_image.size > 0 :
        time.sleep(0.5)
        speaker.speak("Processing the captured image.This may take a few moments.")
        structured_output_dict = process_captured_image_with_gemini(
            image_frame=captured_image,
            document_type=document_type,
            custom_instructions=custom_instructions
        )
        if "error" in structured_output_dict:
            logger.error(f"⚠️ Processing error: {structured_output_dict.get('error')}")
            error_detail = structured_output_dict.get('error', 'an unspecified issue')
            if "OCR" in error_detail: speaker.speak(f"I had trouble reading the text from the image. The specific issue was: {error_detail}")
            elif "LLM" in error_detail or "Gemini" in error_detail: speaker.speak(f"I encountered a problem while structuring the data. The error was: {error_detail}")
            else: speaker.speak(f"There was a problem processing the image: {error_detail}")
            if "status" not in structured_output_dict: structured_output_dict["status"] = "error_processing"
            return json.dumps(structured_output_dict, indent=2)
        else:
            logger.info("📄🧠✅ Scan and structuring complete!")
            speaker.speak("Processing complete.I have structured the information from the document.")
            return json.dumps({"status": "success", "data": structured_output_dict}, indent=2)
    else:
        logger.error("🤔 Internal issue: captured_image is None/empty post-capture.")
        speaker.speak("There was an unexpected internal issue, and the captured image is unavailable.")
        return json.dumps({"status": "error", "message": "Internal error: Captured image is unexpectedly unavailable."}, indent=2)

@tool(args_schema=CodeAgentInput)
def code_agent(
    end_keyword: str = "Ctrl+Z",
    language: str = "python",
    task: str = "debug",    
    config: Optional[RunnableConfig] = None
) -> str:
    """
    🤖 Analyzes code provided via an input portal. Args defined in schema. Returns JSON string with analysis results or error.
    """
    # if end_keyword.startswith("{"):
    #     input = json.loads(end_keyword)
    #     end_keyword = input.get("end_keyword","Ctrl+Z")
    #     language = input.get("language","python")
    #     task = input.get("task","debug")

    logger.info(f"🛠️🤖 Code Agent Tool Activated. Task: '{task}', Lang: '{language}', End keyword: '{end_keyword}'")
    speaker.speak(f"Activating the Code Agent for {language} to perform task: {task}.")
    time.sleep(0.5)

    user_code_input: str = ""
    explanation: Optional[str] = None
    fixed_code: Optional[str] = None

    try:
        speaker.speak(f"Please paste or type your {language} code now. Type '{end_keyword}' on a new line when you are finished.")
        user_code_input = open_code_input_portal(end_keyword=end_keyword)

        if not user_code_input:
            logger.warning("⌨️⚠️ Code input was cancelled or empty.")
            speaker.speak("Code input was cancelled or no code was provided. Aborting Code Agent.")
            return json.dumps({"status": "cancelled", "message": "Code input cancelled or empty."}, indent=2)

        logger.info("⌨️✅ Code input received.")
        speaker.speak("Thank you. I have received the code.")
        time.sleep(0.5)

        logger.info("🧠 Calling custom code agent for analysis...")
        speaker.speak("Analyzing the code snippet now. This might take a moment, please wait.")

        agent_task_string = f"# Language: {language}\n# Task: {task}\n# Code:\n{user_code_input}"

        explanation_result, fixed_code_result = custom_code_agent(
            task_input=agent_task_string,
            config=config
        )

        if isinstance(explanation_result, str) and ("error" in explanation_result.lower() or "failed" in explanation_result.lower()):
             logger.error(f"🧠❌ Agent analysis indicated failure. Explanation: {explanation_result}")
             speaker.speak(f"error occured in code analysis.")
             return json.dumps({"status": "error", "message": f"Agent analysis failed: {explanation_result}", "fixed_code": fixed_code_result}, indent=2)

        explanation = explanation_result
        fixed_code = fixed_code_result

        logger.info("🧠✅ Code analysis complete.")
        speaker.speak("Analysis complete. I have prepared an explanation and any necessary code corrections.")
        time.sleep(0.2)

        if explanation:
            summary = explanation.split('.')[0]
            speaker.speak(f"Here's a summary: {summary}.")
        if fixed_code:
             speaker.speak("I have also prepared a corrected version of the code.")

        return json.dumps({
            "status": "success",
            "explanation": explanation,
            "fixed_code": fixed_code
        }, indent=2)

    except Exception as e:
        logger.error(f"💥 UNEXPECTED ERROR in Code Agent Tool: {e}", exc_info=True)
        speaker.speak(f"An unexpected error occurred while running the Code Agent: {str(e)}")
        return json.dumps({"status": "error", "message": f"Unexpected error in Code Agent: {str(e)}"}, indent=2)
    

@tool(args_schema=WebImageSearchInput)
def web_and_image_searcher(query: str, include_image: bool = False) -> str:
    """
    🔎 Performs web searches to answer user questions. Can optionally capture and analyze an image
    from the camera if the question relates to something visual ('include_image' must be true).
    Synthesizes information from search results and image analysis (if applicable) into a final answer.
    Use this for general knowledge questions, asking about things in images, or finding information online.
    """
    # if query.startswith("{"):
    #     input = json.loads(query)
    #     query = input.get("query","What is that thing?")
    #     include_image = input.get("include_image",False)

    logger.info(f"🛠️🔎 Web/Image Search Tool Activated. Query: '{query}', Include Image: {include_image}")
    speaker.speak(f"Searching the web for information regarding: {query}.")
    time.sleep(0.5)
    image_analysis_text: Optional[str] = None
    search_query = query
    if include_image:
        captured_image: Optional[np.ndarray] = None
        try:
            speaker.speak("Please show the relevant image to the camera.")
            captured_image = capture_image_from_camera()
            if captured_image is None or captured_image.size == 0:
                logger.warning("📸⚠️ Image capture cancelled or failed for search.")
                speaker.speak("Image capture was cancelled or failed. Proceeding with text query only.")
            else:
                logger.info("📸✅ Image captured for search query.")
                speaker.speak("Image captured. Analyzing it now in relation to your query...")
                time.sleep(0.5)
                is_success, buffer = cv2.imencode(".jpg", captured_image)
                if not is_success: raise ValueError("Failed to encode image to JPEG.")
                image_bytes = buffer.tobytes()
                vision_result = analyze_image_with_langchain_ollama(image_bytes, query)
                if "error" in vision_result:
                    logger.error(f"Image analysis failed: {vision_result['error']}")
                    speaker.speak(f"I had trouble analyzing the image: {vision_result['error']}. I will try searching based on the text query alone.")
                else:
                    image_analysis_text = vision_result.get("analysis")
                    logger.info(f"Image analysis result: {image_analysis_text[:100]}...")
                    speaker.speak("Image analysis complete.")
        except Exception as img_err:
            logger.error(f"📸💥 Error during image handling for search: {img_err}", exc_info=True)
            speaker.speak(f"An error occurred during image capture or processing:. Searching based on text query only.")
            image_analysis_text = None

    search_results_data = None
    if tavily_client:
        speaker.speak(f"Performing web search for: {search_query}")
        search_results_data = perform_web_search(search_query)
        if "error" in search_results_data:
            logger.error(f"Web search failed: {search_results_data['error']}")
            speaker.speak(f"Web search encountered an error")
    else:
        logger.error("Web search skipped: Tavily client not available.")
        speaker.speak("Web search is currently unavailable.")
        if not image_analysis_text:
             return json.dumps({"status": "error", "message": "Web search unavailable and no image provided/analyzed."}, indent=2)

    speaker.speak("Synthesizing the findings...")
    time.sleep(0.5)
    final_result = synthesize_answer_with_gemini(
        original_query=query,
        search_results_data=search_results_data,
        image_analysis_text=image_analysis_text
    )

    if "error" in final_result:
        logger.error(f"Answer synthesis failed: {final_result['error']}")
        speaker.speak(f"I found some information but encountered an issue formulating the final answer")
        return json.dumps({"status": "error", "message": final_result.get("error", "Synthesis failed.")}, indent=2)
    else:
        final_answer = final_result.get("answer", "Sorry, I couldn't determine a final answer.")
        logger.info("✅ Web/Image search and synthesis complete.")
        speaker.speak("Web/Image search and synthesis complete.")
        return json.dumps({"status": "success", "answer": final_answer}, indent=2)

@tool(args_schema=VisualObjectFinderInput)
def visual_object_finder(
    object_name: str,
    confidence_threshold: float = 0.4,
    camera_index: int = 0,
    search_duration_seconds: int = 30
) -> str:
    """
    👀 Activates the camera to visually search for a specific object in the real-time feed using YOLO object detection.
    Shows a live view with brightness/contrast controls and detected objects boxed.
    Use this when the user asks "where is my [object]?" or asks you to "find my [object]" visually.

    Args defined in schema.
    Returns JSON string indicating if the object was found ('status': 'found'/'not_found'/'error'/'cancelled'),
    its detected name, confidence, and approximate location in the view if found.
    """
    # if object_name.startswith("{"):
    #     input = json.loads(object_name)
    #     object_name = input.get("object_name","pen")
    #     confidence_threshold = input.get("confidence_threshold",0.5)
    #     camera_index = input.get("camera_index",0)
    #     search_duration_seconds = input.get("search_duration_seconds",30)
        
    logger.info(f"🛠️👀 Visual Object Finder Activated. Searching for: '{object_name}'")
    speaker.speak(f"Activating visual search. Looking for a {object_name}. Use W/X for brightness, A/D for contrast. Press Q to quit.")
    time.sleep(0.5)

    model_name = 'yolov8n.pt'
    target_object_lower = object_name.lower()
    window_name = "Jarvis - Visual Object Finder"

    COLOR_BOX_OTHER = (255, 178, 50); COLOR_BOX_TARGET = (0, 255, 0)
    COLOR_TEXT = (255, 255, 255); COLOR_BG_TEXT = (50, 50, 50)
    COLOR_INFO_TEXT = (0, 255, 255)

    found_object_details = None
    start_time = time.time()
    brightness, contrast = 0, 0
    user_quit = False
    cap = None

    try:
        logger.info(f"Loading YOLO model: {model_name}")
        model = YOLO(model_name)
        logger.info("YOLO model loaded successfully.")

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise IOError(f"Could not open camera index {camera_index}.")

        logger.info(f"📷 Camera {camera_index} opened. Starting detection loop (max {search_duration_seconds}s).")
        print(f"👀 Live View Active: Searching for '{object_name}'. Controls: [W/X] Brightness | [A/D] Contrast | [Q] Quit")
        
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > search_duration_seconds:
                logger.info(f"⏰ Search duration ({search_duration_seconds}s) exceeded.")
                speaker.speak("Search time limit reached.")
                break

            ret, frame = cap.read()
            if not ret:
                logger.warning("⚠️ Camera frame read error."); time.sleep(0.1); continue

            display_frame = frame.copy()
            if brightness != 0 or contrast != 0:
                display_frame = apply_brightness_contrast(display_frame, brightness, contrast)

            frame_h, frame_w = display_frame.shape[:2]
            results = model(display_frame, stream=False, verbose=False, conf=confidence_threshold)

            object_found_in_frame = False
            current_highest_conf = 0.0
            temp_found_details = None

            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = model.names[cls_id]
                    is_target = target_object_lower in label.lower()

                    box_color = COLOR_BOX_TARGET if is_target else COLOR_BOX_OTHER
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, 2)
                    text = f"{label}: {conf:.2f}"
                    text_org_y = y1 - 10 if y1 > 20 else y1 + 20
                    put_text_with_bg(display_frame, text, (x1, text_org_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, COLOR_BG_TEXT, padding=3)

                    if is_target and conf > current_highest_conf:
                        object_found_in_frame = True
                        current_highest_conf = conf
                        center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
                        loc_desc = ""
                        if center_y < frame_h / 3: loc_desc += "Top "
                        elif center_y > frame_h * 2 / 3: loc_desc += "Bottom "
                        else: loc_desc += "Center "
                        if center_x < frame_w / 3: loc_desc += "Left"
                        elif center_x > frame_w * 2 / 3: loc_desc += "Right"
                        elif loc_desc == "Center ": loc_desc = "Center"
                        else: loc_desc = loc_desc.strip()
                        temp_found_details = {
                            "status": "found", "object_name": object_name,
                            "detected_name": label, "confidence": round(conf, 3),
                            "location_description": loc_desc,
                            "bounding_box": [x1, y1, x2, y2]
                        }

            if temp_found_details:
                if found_object_details is None or temp_found_details['confidence'] > found_object_details.get('confidence', 0.0):
                    found_object_details = temp_found_details

            remaining_time = max(0, int(search_duration_seconds - elapsed_time))
            status_text = f"Searching: {object_name} | T Left: {remaining_time}s | B:{brightness} C:{contrast} | Q:Quit"
            if found_object_details and temp_found_details and found_object_details['bounding_box'] == temp_found_details['bounding_box']: # Show live best match
                 status_text += f" | Found: {found_object_details['detected_name']} ({found_object_details['confidence']:.2f}) at {found_object_details['location_description']}"

            put_text_with_bg(display_frame, status_text,(10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_INFO_TEXT, COLOR_BG_TEXT, 1)
            cv2.imshow(window_name, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                logger.info("🛑 User quit visual search early via 'Q' key.")
                speaker.speak("Stopping visual search as requested.")
                user_quit = True
                break
            elif key == ord('w'): brightness = min(255, brightness + 10)
            elif key == ord('x'): brightness = max(-255, brightness - 10)
            elif key == ord('a'): contrast = max(-127, contrast - 10)
            elif key == ord('d'): contrast = min(127, contrast + 10)

    except ImportError:
        logger.critical("💥 Ultralytics YOLO library not found. Please run 'pip install ultralytics'")
        speaker.speak("I cannot perform visual search as the required library is missing.")
        return json.dumps({"status": "error", "message": "YOLO library not installed."}, indent=2)
    except IOError as e: 
         logger.error(f"📸💥 Camera Error: {e}", exc_info=True)
         speaker.speak(f"I encountered an error accessing the camera")
         return json.dumps({"status": "error", "message": f"Camera access error: {e}"}, indent=2)
    except Exception as e:
        logger.error(f"💥 UNEXPECTED ERROR in Visual Object Finder: {e}", exc_info=True)
        speaker.speak(f"An unexpected error occurred during the visual search")
        return json.dumps({"status": "error", "message": f"Unexpected error during visual search: {str(e)}"}, indent=2)
    finally:
        if cap and cap.isOpened(): cap.release()
        cv2.destroyAllWindows()
        logger.info("Camera feed closed.")

    if user_quit:
         return json.dumps({"status": "cancelled", "message": "User quit the visual search."}, indent=2)
    elif found_object_details:
         logger.info(f"✅ Object '{object_name}' found as '{found_object_details['detected_name']}'.")
         loc = found_object_details['location_description'].lower()
         det_name = found_object_details['detected_name']
         conf = found_object_details['confidence']
         speaker.speak(f"Search complete. I located the {det_name} in the {loc} area of the view with {conf:.0%} confidence.")
         return json.dumps(found_object_details, indent=2)
    else:
         logger.warning(f"🚫 Object '{object_name}' not found within time/confidence limit.")
         speaker.speak(f"Search complete. I did not visually locate the {object_name}.")
         return json.dumps({"status": "not_found", "object_name": object_name, "message": "Object not detected in the video feed within time/confidence limits."}, indent=2)
    

@tool(args_schema=EmailToolInput)
def email_manager(
    action: str, max_emails_to_check: int = 3, recipient_email: Optional[str] = None,
    subject: Optional[str] = None, body: Optional[str] = None, original_message_id: Optional[str] = None,
    original_thread_id: Optional[str] = None, original_sender: Optional[str] = None,
    original_subject: Optional[str] = None, original_body_snippet: Optional[str] = None,
    config: Optional[RunnableConfig] = None
) -> str:
    """
    📧 Manages emails: checks new unread, drafts replies with AI & history, sends pre-approved drafts.
    Requires user Google OAuth on first run. Use 'check_new' for unread. Use 'send_draft' to send.
    """
    # if action.startswith("{"):
    #     parsed_data_dict = json.loads(action)
    #     action = parsed_data_dict.get("action")
    #     max_emails_to_check = parsed_data_dict.get("max_emails_to_check", 3)
    #     recipient_email = parsed_data_dict.get("recipient_email") 
    #     subject = parsed_data_dict.get("subject")
    #     body = parsed_data_dict.get("body")
    #     original_message_id = parsed_data_dict.get("original_message_id")
    #     original_thread_id = parsed_data_dict.get("original_thread_id")
    #     original_sender = parsed_data_dict.get("original_sender")
    #     original_subject = parsed_data_dict.get("original_subject")
    #     original_body_snippet = parsed_data_dict.get("original_body_snippet")

    if not EMAIL_TOOL_AVAILABLE:
        return json.dumps({"status": "error", "message": "Email tool logic unavailable."})
    logger.info(f"🛠️📧 Email Manager: Action '{action}'")
    speaker.speak(f"Accessing email systems for action: {action}.")
    time.sleep(0.5)
    service = None
    try:
        service = get_gmail_service()
        if not service: return json.dumps({"status": "error_authentication", "message": "Gmail auth/service failed."})
    except FileNotFoundError as e: return json.dumps({"status": "error_configuration", "message": str(e)})
    except Exception as e: return json.dumps({"status": "error_authentication", "message": f"Auth error: {str(e)}"})

    if action == "check_new":
        speaker.speak(f"Checking for up to {max_emails_to_check} new unread emails.")
        unread_emails = get_unread_emails(max_results=max_emails_to_check)
        if not unread_emails:
            speaker.speak("No new unread emails found.")
            return json.dumps({"status": "success", "message": "No new unread emails."})
        processed_emails = []
        for email_data in unread_emails:
            speaker.speak(f"Processing email from {email_data['sender_email']} about {email_data['subject'][:30]}.")
            history = get_conversation_history(email_data['sender_email'], email_data['subject'].split())
            draft_reply = draft_reply_with_llm(email_data['body'], email_data['sender_email'], email_data['subject'], history)
            processed_emails.append({"original_email": email_data, "suggested_draft_reply": draft_reply, "requires_action": not ("no reply needed" in draft_reply.lower() or "mark as read" in draft_reply.lower())})
            if "mark as read" in draft_reply.lower() or "no reply needed" in draft_reply.lower():
                 mark_email_as_read(service, email_data['id'])
                 speaker.speak(f"Email regarding '{email_data['subject'][:30]}' marked as read.")
        num_actionable = sum(1 for e in processed_emails if e["requires_action"])
        speaker.speak(f"Checked emails. Found {len(unread_emails)} new. {num_actionable} may require a reply.")
        return json.dumps({"status": "success", "processed_emails": processed_emails}, indent=2)
    elif action == "send_draft":
        if not all([recipient_email, subject, body]):
            return json.dumps({"status": "error_input", "message": "Recipient, subject, and body required for send_draft."})
        speaker.speak(f"Preparing to send email to {recipient_email} with subject {subject[:30]}.")
        success, message = send_email(service, recipient_email, subject, body, original_thread_id)
        if success:
            speaker.speak("Email sent successfully.")
            if all([original_sender, original_subject, original_body_snippet]):
                 add_to_memory(original_sender, original_subject, original_body_snippet, body)
            if original_message_id: mark_email_as_read(service, original_message_id)
        else: speaker.speak(f"Failed to send email: {message}")
        return json.dumps({"status": "success" if success else "error_send", "message": message}, indent=2)
    else:
        return json.dumps({"status": "error_action", "message": f"Unknown action: {action}."}, indent=2)


@tool(args_schema=ResumeAnalyzerInput)
def resume_analyzer(
    job_description_end_keyword: str = "END_JD",
    config: Optional[RunnableConfig] = None
) -> str:
    """
    📄 Analyzes your resume against a provided job description.
    Prompts for job description, reads resume PDF, uses LLM for comparison.
    Returns match assessment, strengths, and improvement areas.
    """
    if job_description_end_keyword.startswith("{"):
        job_description_end_keyword = json.loads(job_description_end_keyword).get("job_description_end_keyword","END_JOB")

    resume_pdf_path = "C:/Users/Debajyoti/OneDrive/Desktop/Jarves full agent/ResumeAnalyser/resume.pdf"
    logger.info(f"🛠️📄 Resume Analyzer Tool Activated.")
    speaker.speak("Activating Resume Analyzer. I'll need the job description first.")
    time.sleep(0.5)

    speaker.speak(f"Please paste or type the job description. Type '{job_description_end_keyword}' on a new line when finished.")
    job_description_text = open_code_input_portal(
        prompt_message="▶️ Enter Job Description:",
        end_keyword=job_description_end_keyword
    )
    if not job_description_text:
        speaker.speak("No job description provided. Aborting resume analysis.")
        return json.dumps({"status": "cancelled", "message": "Job description input cancelled or empty."}, indent=2)
    speaker.speak("Job description received.")
    time.sleep(0.2)

    actual_resume_path = resume_pdf_path or os.getenv("RESUME_PDF_PATH")
    if not actual_resume_path:
        msg = "Path to your resume PDF not configured. Set YOUR_RESUME_PDF_PATH or provide 'resume_pdf_path'."
        speaker.speak(msg); return json.dumps({"status": "error_configuration", "message": msg})

    speaker.speak(f"Reading your resume...")
    resume_text = extract_text_from_pdf(actual_resume_path)
    if not resume_text:
        msg = f"Could not extract text from your resume PDF at {actual_resume_path}."
        speaker.speak(msg)
        return json.dumps({"status": "error_resume_read", "message": msg})
    
    speaker.speak("Resume content extracted.")
    time.sleep(0.2)

    speaker.speak("Comparing your resume against the job description. This might take a moment...")
    analysis_result = analyze_resume_with_llm(resume_text, job_description_text)

    if "error" in analysis_result:
        speaker.speak(f"Issue during analysis: {analysis_result.get('error')}")
        return json.dumps({"status": "error_analysis", **analysis_result}, indent=2)
    else:
        speaker.speak("Resume analysis complete. I have the results.")
        return json.dumps({"status": "success", "analysis": analysis_result}, indent=2)
