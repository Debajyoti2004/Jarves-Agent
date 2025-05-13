import logging
import uuid
import json
import sys
import os
from typing import Optional, List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException, BaseTool
import time

try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)
    from .tools import (
        open_app_tool, open_website_tool, amazon_web_scrapper,
        google_hotel_scrapper, google_flight_scrapper, jarves_ocr_scanner,
        code_agent, web_and_image_searcher, visual_object_finder
    )
except ImportError as e_inner:
    print(f"AGENT FATAL: Could not import tools. Error: {e_inner}. Ensure 'tools.py' exists and is accessible.")
    raise

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from .jarves_prompt import REACT_PROMPT_TEMPLATE
from dotenv import load_dotenv

agent_logger = logging.getLogger("react_agent")
if not agent_logger.hasHandlers():
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    agent_logger.addHandler(handler)
    agent_logger.setLevel(logging.INFO)

load_dotenv()
GOOGLE_API_KEY = os.getenv("MAINAGENT_API_KEY")
if not GOOGLE_API_KEY:
    agent_logger.critical("Google API key not found (GOOGLE_API_KEY).")
    raise ValueError("Missing Google API Key. Set GOOGLE_API_KEY in .env file.")

LLM_MODEL = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-pro-latest")

class  Agent:
    def __init__(self):
        agent_logger.info(f"Initializing ReAct Agent with model {LLM_MODEL}...")
        
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True
        )
        
        self.tools: List[BaseTool] = [
            open_app_tool, open_website_tool, amazon_web_scrapper,
            google_hotel_scrapper, google_flight_scrapper,
            jarves_ocr_scanner, code_agent,web_and_image_searcher,
            visual_object_finder
        ]
        agent_logger.info(f"Tools Loaded: {[t.name for t in self.tools]}")
        base_prompt = ChatPromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
        react_agent_runnable = create_react_agent(
            self.llm,
            self.tools, 
            base_prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=react_agent_runnable,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )
        agent_logger.info("ReAct Agent Executor created.")

    def handle_command(self, command: str, config: Optional[RunnableConfig] = None) -> str:
        agent_logger.info(f"Agent received: '{command}'. Invoking ReAct Agent (Sync)...")
        run_config = config or RunnableConfig(run_name="JarvisReActRunSync", run_id=str(uuid.uuid4()))
        final_response_str: str
       
        try:
            agent_input = {"input": command}
            response_dict = self.agent_executor.invoke(agent_input, config=run_config)
            final_response_obj = response_dict.get('output')

            if final_response_obj is None:
                final_response_str = "Processing complete, but no specific output was generated."
            elif isinstance(final_response_obj, str):
                final_response_str = final_response_obj
            else:
                final_response_str = str(final_response_obj)
            agent_logger.info(f"Agent final response: '{final_response_str}'")
            return final_response_str
        
        except ToolException as e_tool:
            agent_logger.error(f"ToolException: {e_tool}", exc_info=False) # Less verbose for ToolException
            return f"A tool encountered an issue: {e_tool}"
        
        except Exception as e_generic: 
            agent_logger.error(f"Unexpected error during agent invocation: {e_generic}", exc_info=True)
            return f"An unexpected internal error occurred while I was processing that."

# def main_agent_test():
#     print("--- Testing Agent Initialization and Handling (Sync) ---")
#     agent_instance = None
#     try:
#         agent_instance = Agent()
#         print("✅ Agent initialized successfully.")
#         test_commands = [
#             "Hello Jarvis",
#             "Can you open applications?",
#             "open calculator",
#             "Search Amazon for 'ergonomic keyboard'",
#         ]
#         for cmd in test_commands:
#             print(f"\n>>> Testing command: '{cmd}'")
#             if agent_instance:
#                 interactive_keywords = ["scan ", "find my ", "debug this", "what kind of", "where is my"]
#                 if any(keyword in cmd.lower() for keyword in interactive_keywords):
#                     print("    (Skipping execution of tool requiring direct user/camera/code input in this automated test loop)")
#                     continue
#                 final_answer = agent_instance.handle_command(cmd)
#                 print(f"<<< Agent Response: {final_answer}")
#             else:
#                 print("Agent instance not available for command handling.")
#             print("-" * 30)
#             time.sleep(1)
#     except Exception as e: 
#         print(f"💥 An error occurred during agent testing: {e}")
#         agent_logger.exception("Error during agent testing in test block")
#     finally:
#         print("\n--- Agent Testing Finished ---")

# if __name__ == "__main__":
#     if not GOOGLE_API_KEY:
#         print("⚠️ WARNING: GOOGLE_API_KEY not found in .env. LLM calls will fail.")
#     try:
#         _ = REACT_PROMPT_TEMPLATE 
#     except NameError:
#         print("CRITICAL ERROR: REACT_PROMPT_TEMPLATE not found. Ensure 'jarves_prompt.py' (or similar) exists and defines it.")
#         sys.exit(1)
#     main_agent_test()