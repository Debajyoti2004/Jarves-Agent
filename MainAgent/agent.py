import logging
import uuid
import json
import sys
import time
import os
from typing import Optional, List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException, BaseTool
from langchain_core.runnables.base import Runnable
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
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
    agent_logger.critical("Google API key not found (MAINAGENT_API_KEY).")
    raise ValueError("Missing Google API Key. Set MAINAGENT_API_KEY in .env file.")

LLM_MODEL = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-pro-latest")

try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)

    from .tools import (
        open_app_tool, open_website_tool, amazon_web_scrapper,
        google_hotel_scrapper, google_flight_scrapper, jarves_ocr_scanner,
        code_agent, web_and_image_searcher, visual_object_finder
    )
    from .jarves_prompt import REACT_PROMPT_TEMPLATE
except ImportError as e_inner:
    agent_logger.critical(f"Failed to import tools or prompt: {e_inner}")
    raise

class Agent:
    def __init__(self):
        agent_logger.info(f"Initializing ReAct Agent using LLM: {LLM_MODEL}...")
        
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            google_api_key=GOOGLE_API_KEY,
            temperature=0.1,
            convert_system_message_to_human=True
        )
        
        self.tools: List[BaseTool] = [
            open_app_tool,
            open_website_tool,
            amazon_web_scrapper,
            google_hotel_scrapper,
            google_flight_scrapper,
            jarves_ocr_scanner,
            code_agent,
            web_and_image_searcher,
            visual_object_finder
        ]
        agent_logger.info(f"Loaded tools: {[tool.name for tool in self.tools]}")

        prompt = ChatPromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

        self.react_agent: Runnable = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

    def handle_command(self, command: str, config: Optional[RunnableConfig] = None) -> str:
        agent_logger.info(f"Processing command: {command}")
        run_config = config or RunnableConfig(run_name="JarvisReActAgent", run_id=str(uuid.uuid4()))

        try:
            result = self.react_agent.invoke({"input": command}, config=run_config)
            output = result.get("output") if isinstance(result, dict) else result
            final_response = output if isinstance(output, str) else str(output)
            agent_logger.info(f"Agent response: {final_response}")
            return final_response
        except ToolException as e_tool:
            agent_logger.warning(f"Tool exception occurred: {e_tool}")
            return f"A tool encountered an issue: {e_tool}"
        except Exception as e:
            agent_logger.exception("Unexpected error while running the agent.")
            return "An internal error occurred while processing your command."
        

def main_agent_test():
    print("--- Testing Agent Initialization and Handling (Sync - Manual Loop) ---")
    agent_instance = None
    try:
        agent_instance = Agent()
        print("✅ Agent initialized successfully.")
        test_commands = [
            "Hello Jarvis",
            "Can you open applications?",
            "open calculator",
            "Search Amazon for 'ergonomic keyboard'",
            "what is the capital of France?"
        ]
        for cmd in test_commands:
            print(f"\n>>> Testing command: '{cmd}'")
            if agent_instance:
                final_answer = agent_instance.handle_command(cmd)
                print(f"<<< Agent Response: {final_answer}")
            else:
                print("Agent instance not available for command handling.")
            print("-" * 30)
            if "CI_TEST" not in os.environ:
                time.sleep(2) 
    except Exception as e: 
        print(f"💥 An error occurred during agent testing: {e}")
        agent_logger.exception("Error during agent testing in test block")
    finally:
        print("\n--- Agent Testing Finished ---")

if __name__ == "__main__":
    if not GOOGLE_API_KEY:
        print("⚠️ WARNING: GOOGLE_API_KEY not found in .env. LLM calls will fail.")
    try:
        _ = REACT_PROMPT_TEMPLATE 
    except NameError:
        print("CRITICAL ERROR: REACT_PROMPT_TEMPLATE not found. Ensure 'jarves_prompt.py' (or similar) exists and defines it.")
        sys.exit(1)
    main_agent_test()