import sys
import os
import logging
import logging.config
from typing import Optional, List, Dict, Any
import pprint
import asyncio
import json
import uuid 

try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from tools import (
        open_app_tool, open_website_tool, amazon_web_scrapper,
        google_hotel_scrapper, google_flight_scrapper,
        jarves_ocr_scanner, code_agent,
        web_and_image_searcher, visual_object_finder,
        email_manager,
        resume_analyzer
    )
except ImportError as e:
    project_root = "."
    sys.path.append(os.path.abspath(project_root))
    try:
        from tools import (
            open_app_tool, open_website_tool, amazon_web_scrapper,
            google_hotel_scrapper, google_flight_scrapper,
            jarves_ocr_scanner, code_agent,
            web_and_image_searcher, visual_object_finder,
            email_manager ,
            resume_analyzer
        )
    except ImportError as e_inner:
        print(f"Error importing tools from fallback path: {e_inner}. Check path and tool definitions.")
        sys.exit(1)

logging_config = {
    'version': 1,
    'formatters': {'simple': {'format': '[%(levelname)s] %(message)s',},},
    'handlers': {'console': {'class': 'logging.StreamHandler','formatter': 'simple','level': 'INFO',},},
    'root': {'level': 'INFO','handlers': ['console'],},
    'loggers': {
        'ToolsModule': {'handlers': ['console'],'level': 'INFO','propagate': False},
        'JarvesScannerTool': {'handlers': ['console'],'level': 'INFO','propagate': False},
        'CodeAgentTool': {'handlers': ['console'],'level': 'INFO','propagate': False},
        'VisualObjectFinder': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'EmailManagerTool': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}, # Added logger
        'DirectToolTestRunner': {'handlers': ['console'],'level': 'INFO','propagate': False}
        }
}
logging.config.dictConfig(logging_config)
logger = logging.getLogger("DirectToolTestRunner")

def print_tool_result(tool_name: str, result: Any, is_json_string: bool = False):
    print(f"\n--- Testing: {tool_name} ---")
    print("✅ Result:")
    if is_json_string and isinstance(result, str):
        try:
            parsed_result = json.loads(result)
            pprint.pprint(parsed_result)
            if isinstance(parsed_result, dict) and \
               (parsed_result.get("status") != "success" or "error" in parsed_result):
                 print(f"⚠️ Note: Tool reported status '{parsed_result.get('status', 'N/A')}' or error in JSON response.")
        except json.JSONDecodeError:
            print("Raw string (JSON parsing failed):")
            print(result)
            print("⚠️ Note: Tool returned a string that is not valid JSON.")
    else:
        pprint.pprint(result)
    print(f"--- Finished: {tool_name} ---")

class TestTool:
    def __init__(self):
        logger.info("TestTool instance created.")

    def test_open_app(self):
        logger.info("--> Running test_open_app (Sync)")
        app_to_open = "notepad"
        try:
            result_app = open_app_tool.invoke({"app_name": app_to_open})
            print_tool_result("open_app_tool", result_app, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during open_app_tool call: {e}")
        logger.info("<-- Finished test_open_app")

    def test_open_website(self):
        logger.info("--> Running test_open_website (Sync)")
        site_to_open = "google.com"
        try:
            result_site = open_website_tool.invoke({"web_site_name": site_to_open})
            print_tool_result("open_website_tool", result_site, is_json_string=True)
        except Exception as e:
             print(f"❌ ERROR during open_website_tool call: {e}")
        logger.info("<-- Finished test_open_website")

    def test_amazon_scraper(self):
        logger.info("--> Running test_amazon_scraper (Sync)")
        product_query = "wireless mouse"
        prefs_amazon = {"rating_min": 4.0}
        try:
            result_amazon = amazon_web_scrapper.invoke({
                "product_name": product_query,
                "user_preferences": prefs_amazon
            })
            print_tool_result("amazon_web_scrapper", result_amazon, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during amazon_web_scrapper call: {e}")
        logger.info("<-- Finished test_amazon_scraper")

    def test_hotel_scraper(self):
        logger.info("--> Running test_hotel_scraper (Sync)")
        hotel_location = "New York, USA"
        hotel_check_in = "2025-10-01"
        hotel_check_out = "2025-10-05"
        prefs_hotel = {"price_max": 500, "rating_min": 4.5}
        try:
            result_hotel = google_hotel_scrapper.invoke({
                "location": hotel_location,
                "check_in_date": hotel_check_in,
                "check_out_date": hotel_check_out,
                "user_preferences": prefs_hotel
            })
            print_tool_result("google_hotel_scrapper", result_hotel, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during google_hotel_scrapper call: {e}")
        logger.info("<-- Finished test_hotel_scraper")

    def test_flight_scraper(self):
        logger.info("--> Running test_flight_scraper (Sync)")
        flight_from = "SFO"
        flight_to = "JFK"
        flight_dep_date = "2025-11-10"
        flight_ret_date = "2025-11-17"
        prefs_flight = {"num_passengers": 1, "max_stops": 1}
        try:
            result_flight = google_flight_scrapper.invoke({
                "from_place": flight_from,
                "to_place": flight_to,
                "departure_date": flight_dep_date,
                "returned_date": flight_ret_date,
                "user_preferences": prefs_flight
            })
            print_tool_result("google_flight_scrapper", result_flight, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during google_flight_scrapper call: {e}")
        logger.info("<-- Finished test_flight_scraper")

    def test_jarves_scanner(self):
        logger.info("--> Running test_jarves_scanner (Sync - Requires User Interaction)")
        print("\n📷 Jarves Scanner Test: Please interact with the camera window that appears.")
        try:
            result_scan_id = jarves_ocr_scanner.invoke({
                "document_type":"receipt",
                "custom_instructions":"Extract the total amount and the name of the store."
            })
            print_tool_result("jarves_ocr_scanner (Receipt)", result_scan_id, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during jarves_ocr_scanner call: {e}")
        logger.info("<-- Finished test_jarves_scanner")

    def test_code_agent(self):
        logger.info("--> Running test_code_agent (Sync - Requires User Input)")
        print("\n🤖 Code Agent Test: This tool will open a portal for code input.")
        print("   You will need to paste or type code, then type 'ENDCODE' on a new line.")
        input("   Press Enter when ready to start Code Agent test...")
        try:
            result_code = code_agent.invoke({"end_keyword": "ENDCODE"})
            print_tool_result("code_agent", result_code, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during code_agent call: {e}")
        logger.info("<-- Finished test_code_agent")

    def test_web_image_searcher(self):
        logger.info("--> Running test_web_image_searcher (Sync / User Interaction)")
        print("\n   Test 1: Text-only web search.")
        text_query = "What are the latest developments in AI ethics?"
        input(f"   Press Enter to search for: '{text_query}'...")
        try:
            result_text_search = web_and_image_searcher.invoke({
                "query": text_query,
                "include_image": False
            })
            print_tool_result("web_and_image_searcher (Text Only)", result_text_search, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during web_and_image_searcher (Text Only) call: {e}")

        print("\n   Test 2: Image-based web search.")
        print("   Prepare an image to show to the camera.")
        image_query = "What is this object?"
        input(f"   Press Enter to start image search for query: '{image_query}'...")
        try:
            result_image_search = web_and_image_searcher.invoke({
                "query": image_query,
                "include_image": True
            })
            print_tool_result("web_and_image_searcher (With Image)", result_image_search, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during web_and_image_searcher (With Image) call: {e}")
        logger.info("<-- Finished test_web_image_searcher")

    def test_visual_object_finder(self):
        logger.info("--> Running test_visual_object_finder (Sync - Requires User Interaction)")
        print("\n👀 Visual Object Finder Test: Please interact with the camera window.")
        object_to_find = "keyboard"
        print(f"\n   Test 1: Find '{object_to_find}'.")
        input(f"   Press Enter to start searching for '{object_to_find}'...")
        try:
            result_find = visual_object_finder.invoke({
                "object_name": object_to_find,
                "confidence_threshold": 0.4
            })
            print_tool_result(f"visual_object_finder (Find {object_to_find})", result_find, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during visual_object_finder (Find {object_to_find}) call: {e}")
        logger.info("<-- Finished test_visual_object_finder")

    def test_email_manager(self):
        logger.info("--> Running test_email_manager (Sync - Requires User Interaction for OAuth)")
        print("\n📧 Email Manager Test: This tool will interact with your Gmail.")
        print("   The FIRST time, a browser window will open for Google OAuth. Complete this flow.")
        print("   Ensure 'credentials.json' is where 'email_tool_logic.py' expects it.")

        print("\n   Test 1: Checking for new emails (up to 2).")
        input("   Press Enter to start Test 1 (Check New Emails)...")
        try:
            result_check_new = email_manager.invoke({
                "action": "check_new",
                "max_emails_to_check": 2
            })
            print_tool_result("email_manager (Check New)", result_check_new, is_json_string=True)
            
            if isinstance(result_check_new, str):
                try:
                    check_new_data = json.loads(result_check_new)
                    if check_new_data.get("status") == "success" and check_new_data.get("processed_emails"):
                        first_email_to_reply = None
                        for email_info in check_new_data["processed_emails"]:
                            if email_info.get("requires_action") and email_info.get("suggested_draft_reply"):
                                first_email_to_reply = email_info
                                break
                        if first_email_to_reply:
                            orig_email = first_email_to_reply["original_email"]
                            draft = first_email_to_reply["suggested_draft_reply"]
                            print(f"\n   Found email from '{orig_email.get('sender_email')}' subject '{orig_email.get('subject')}'.")
                            print(f"   Suggested draft: \"{draft[:100]}...\"")
                            confirm_send = input("   Test sending this draft? (yes/no): ").lower()
                            if confirm_send == 'yes':
                                print("\n   Test 1b: Sending approved draft...")
                                send_input = {
                                    "action": "send_draft",
                                    "recipient_email": orig_email.get("sender_email"),
                                    "subject": f"Re: {orig_email.get('subject')}",
                                    "body": draft,
                                    "original_message_id": orig_email.get("id"),
                                    "original_thread_id": orig_email.get("threadId"),
                                    "original_sender": orig_email.get("sender_email"),
                                    "original_subject": orig_email.get("subject"),
                                    "original_body_snippet": orig_email.get("body", "")[:100]
                                }
                                result_send_draft = email_manager.invoke(send_input)
                                print_tool_result("email_manager (Send Draft)", result_send_draft, is_json_string=True)
                except json.JSONDecodeError:
                    print("   Could not parse 'check_new' result for sending test.")
        except Exception as e:
            print(f"❌ ERROR during email_manager (Check New) call: {e}")
            logger.error("Error in test_email_manager - check_new", exc_info=True)

        print("\n   Test 2: Sending a new test email TO YOURSELF.")
        your_email_for_test = "majeedebajyoti2004@gmail.com"
        input(f"   Press Enter to send a new test email to '{your_email_for_test}'...")
        try:
            test_subject = f"Jarvis Email Tool Test - {uuid.uuid4()}"
            test_body = "This is an automated test email from the Jarvis Email Manager tool."
            result_send_new = email_manager.invoke({
                "action": "send_draft",
                "recipient_email": your_email_for_test,
                "subject": test_subject,
                "body": test_body
            })
            print_tool_result("email_manager (Send New Email)", result_send_new, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during email_manager (Send New Email) call: {e}")
            logger.error("Error in test_email_manager - send_new", exc_info=True)
        logger.info("<-- Finished test_email_manager")

    def test_resume_analyzer(self):
        logger.info("--> Running test_resume_analyzer (Sync - Requires User Input)")
        print("\n📄 Resume Analyzer Test: This tool will open a portal for job description input.")
        print("   Ensure 'YOUR_RESUME_PDF_PATH' is set in your .env file, or this will fail.")
        print("   You will need to paste a job description, then type 'END_JD' (or your chosen keyword).")
        
        if not os.getenv("RESUME_PDF_PATH"):
            print("⚠️ WARNING: YOUR_RESUME_PDF_PATH environment variable not set. Skipping resume analyzer test.")
            logger.warning("Skipping test_resume_analyzer: YOUR_RESUME_PDF_PATH not set.")
            return

        input("   Press Enter when ready to start Resume Analyzer test...")
        try:
            result_analysis = resume_analyzer.invoke({"job_description_end_keyword":"Ctrl+Z"}) 
            print_tool_result("resume_analyzer", result_analysis, is_json_string=True)
        except Exception as e:
            print(f"❌ ERROR during resume_analyzer call: {e}")
            logger.error("Error in test_resume_analyzer", exc_info=True)
        
        logger.info("<-- Finished test_resume_analyzer")

def main_sync_tests():
    print("--- Starting Direct Tool Tests (All Synchronous from Runner's Perspective) ---")
    tester = TestTool()
    
    tester.test_open_app()
    tester.test_open_website()
    tester.test_amazon_scraper()
    tester.test_hotel_scraper()
    tester.test_flight_scraper()
    tester.test_jarves_scanner()
    tester.test_code_agent()
    tester.test_visual_object_finder()
    tester.test_web_image_searcher()
    tester.test_email_manager()
    tester.test_resume_analyzer()

    print("\n--- All Selected Direct Tool Tests Completed ---")

if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"): print("⚠️ WARNING: GOOGLE_API_KEY not found.")
    if not os.getenv("COHERE_API_KEY"): print("⚠️ WARNING: COHERE_API_KEY not found.") # If used by structuring
    if not os.getenv("TAVILY_API_KEY"): print("⚠️ WARNING: TAVILY_API_KEY not found.") # If used by web_search
    if not os.path.exists("credentials.json"): print("⚠️ WARNING: 'credentials.json' for Gmail API not found.")
        
    main_sync_tests()