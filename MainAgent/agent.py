import logging
import uuid
import sys
import time
import os
from typing import Optional, List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import ToolException, BaseTool
from langchain.agents import create_react_agent, AgentExecutor
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

LLM_MODEL = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash-latest")

try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.append(project_root)

    from MainAgent.tools import (
        open_app_tool, open_website_tool, amazon_web_scrapper,
        google_hotel_scrapper, google_flight_scrapper, jarves_ocr_scanner,
        code_agent, web_and_image_searcher, visual_object_finder,email_manager,resume_analyzer
    )
    from MainAgent.jarves_prompt import REACT_PROMPT_TEMPLATE
except ImportError as e_inner:
    agent_logger.critical(f"Failed to import tools or prompt: {e_inner}. Check paths and ensure MainAgent is a package or in PYTHONPATH.")
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
            visual_object_finder,
            email_manager,
            resume_analyzer
        ]
        agent_logger.info(f"Loaded tools: {[tool.name for tool in self.tools]}")

        try:
            prompt = ChatPromptTemplate.from_template(REACT_PROMPT_TEMPLATE)
        except Exception as e_prompt:
            agent_logger.critical(f"Error creating ChatPromptTemplate: {e_prompt}. Ensure REACT_PROMPT_TEMPLATE is valid.")
            raise

        react_agent_runnable = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )

        self.agent_executor = AgentExecutor(
            agent=react_agent_runnable,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10,
        )
        agent_logger.info("AgentExecutor initialized successfully.")

    def handle_command(self, command: str, config: Optional[RunnableConfig] = None) -> str:
        agent_logger.info(f"Processing command: {command}")
        run_config = config or RunnableConfig(
            run_name="JarvisReActAgent",
            run_id=str(uuid.uuid4()),
        )

        try:
            input_dict = {"input": command}
            result = self.agent_executor.invoke(input_dict, config=run_config)
            
            agent_logger.debug(f"Raw AgentExecutor result: {result}")

            output = result.get("output")
            if output is None:
                agent_logger.warning(f"AgentExecutor result did not contain 'output' key. Full result: {result}")
                final_response = f"Agent did not produce a standard output. Full response: {str(result)}"
            else:
                final_response = str(output)

            agent_logger.info(f"Agent response: {final_response}")
            return final_response
        except ToolException as e_tool:
            agent_logger.warning(f"Tool exception occurred: {e_tool}")
            return f"A tool encountered an issue: {e_tool}"
        except Exception as e:
            agent_logger.error(f"Unexpected error while running the agent: {repr(e)}", exc_info=True)
            return "An internal error occurred while processing your command. Please check logs."
        
def main_agent_test():
    print("--- Testing Agent Initialization and Handling (AgentExecutor) ---")
    agent_instance = None
    try:
        agent_instance = Agent()
        print("✅ Agent initialized successfully.")
        test_commands = [
            "Hello Jarvis",
            "Can you open applications?",
            "open calculator",
            "Search Amazon for 'ergonomic keyboard'",
            "what is the capital of France?",
            "Can you scan a document for me?",
            # "check my new emails", # Uncomment if email_manager_tool is added
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
        agent_logger.error("Error during agent testing in test block", exc_info=True)
    finally:
        print("\n--- Agent Testing Finished ---")

if __name__ == "__main__":
    if not GOOGLE_API_KEY:
        print("⚠️ WARNING: GOOGLE_API_KEY not found in .env. LLM calls will fail.")
    
    try:
        if not REACT_PROMPT_TEMPLATE or not isinstance(REACT_PROMPT_TEMPLATE, str):
            print("CRITICAL ERROR: REACT_PROMPT_TEMPLATE is not a valid string or is empty.")
            sys.exit(1)
        if not all(ph in REACT_PROMPT_TEMPLATE for ph in ["{tools}", "{tool_names}", "{input}", "{agent_scratchpad}"]):
            print("CRITICAL ERROR: REACT_PROMPT_TEMPLATE is missing one or more essential placeholders: {tools}, {tool_names}, {input}, {agent_scratchpad}")
            sys.exit(1)
    except NameError:
        print("CRITICAL ERROR: REACT_PROMPT_TEMPLATE not found. Ensure 'MainAgent/jarves_prompt.py' (or similar) exists and defines it.")
        sys.exit(1)
    except Exception as e_template_check:
        print(f"CRITICAL ERROR during REACT_PROMPT_TEMPLATE check: {e_template_check}")
        sys.exit(1)
        
    main_agent_test()