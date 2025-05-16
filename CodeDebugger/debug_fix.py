import os
import re
import logging
from dotenv import load_dotenv
from typing import Tuple, Optional, List
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent, AgentExecutor 
from langchain_core.prompts import ChatPromptTemplate

from .execution_tools import (
    executor,
    extract_missing_modules,
    file_read,
    file_write,
    list_files,
    close_sandbox
)
from .code_prompt_task import AGENT_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

API_KEY_GOOGLE = os.getenv("GOOGLE_API_KEY")
llm_model_name_from_env = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash-latest")

llm = None
if API_KEY_GOOGLE:
    try:
        llm = ChatGoogleGenerativeAI(
            model=llm_model_name_from_env,
            google_api_key=API_KEY_GOOGLE,
            temperature=0.1,
            convert_system_message_to_human=True
        )
        logger.info(f"Google Gemini LLM '{llm_model_name_from_env}' initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Google Gemini LLM '{llm_model_name_from_env}': {e}")
else:
    logger.error("No GOOGLE_API_KEY found. Cannot initialize LLM.")

tools: List[BaseTool] = [
    executor,
    extract_missing_modules,
    file_read,
    file_write,
    list_files,
    close_sandbox
]

custom_agent_executor = None
if llm:
    try:
        prompt = ChatPromptTemplate.from_template(AGENT_PROMPT)
        agent_core_runnable = create_react_agent(
            llm,
            tools,
            prompt
        )
        logger.info("Custom Langchain ReAct agent core runnable created successfully.")

        custom_agent_executor = AgentExecutor(
            agent=agent_core_runnable,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=15
        )
        logger.info("Custom Langchain AgentExecutor created successfully.")
    except Exception as e:
        logger.error(f"Failed to create Langchain ReAct agent components: {e}", exc_info=True)
else:
    logger.warning("LLM not initialized, AgentExecutor cannot be created.")

def custom_code_agent(task_input: str, config: Optional[RunnableConfig] = None) -> Tuple[str, Optional[str]]:
    if not custom_agent_executor:
        error_msg = "AgentExecutor is not initialized."
        logger.error(error_msg)
        return error_msg, None

    logger.info(f"Running Agent (via Executor) for input: {task_input[:150].replace(os.linesep, ' ')}...")
    explanation: str = "Agent did not produce a standard explanation."
    fixed_code: Optional[str] = None

    try:
        response = custom_agent_executor.invoke({"input": task_input}, config=config)
        final_answer = response.get("output") if isinstance(response, dict) else str(response)

        if final_answer:
            logger.info("AgentExecutor completed.")
            explanation_marker = "## Explanation:"
            code_marker = "## Fixed Code:"
            python_code_block_pattern = r"```python\n(.*?)\n```"

            exp_start = final_answer.find(explanation_marker)
            code_start = final_answer.find(code_marker)

            if exp_start != -1:
                end_of_explanation = code_start if code_start != -1 and code_start > exp_start else len(final_answer)
                explanation = final_answer[exp_start + len(explanation_marker):end_of_explanation].strip()
            else:
                explanation = f"No '## Explanation:' in agent output. Raw: {final_answer[:500]}..."
                logger.warning(explanation)

            if code_start != -1:
                code_section = final_answer[code_start + len(code_marker):]
                match = re.search(python_code_block_pattern, code_section, re.DOTALL)
                if match:
                    fixed_code = match.group(1).strip()
                else:
                    potential_code = code_section.strip()
                    if potential_code and not potential_code.startswith("##") and len(potential_code) > 10:
                        fixed_code = potential_code
                        logger.warning("No ```python block in '## Fixed Code:'. Using raw content as potential code.")
                    else:
                        fixed_code = None
                        logger.warning("Marker '## Fixed Code:' found, but no valid code block or content seemed like code.")
            else:
                logger.info("No '## Fixed Code:' marker found in agent output.")
            
            return explanation, fixed_code
        else:
            logger.error("AgentExecutor returned no 'output'. Full response: %s", response)
            return "AgentExecutor returned no 'output'.", None
    except Exception as e:
        logger.error(f"Error running agent executor: {e}", exc_info=True)
        return f"Critical error during agent execution: {type(e).__name__} - {str(e)}", None

if __name__ == "__main__":
    try:
       if custom_agent_executor:
           task = (
               "The following Python code has a bug. "
               "Please identify the bug, explain it, and provide the corrected code.\n\n"
               "Code:\n"
               "```python\n"
               "def add_numbers(a, b):\n"
               "    result = a + b\n"
               "    print(f\"The sum is: {result}\"\n" 
               "    return result\n\n"
               "add_numbers(5, '10')\n"
               "```"
           )
           explanation, fixed_code_result = custom_code_agent(task_input=task)
           print("\n--- Agent Output (AgentExecutor) ---")
           print(f"Explanation:\n{explanation}")
           if fixed_code_result:
               print(f"\nFixed Code:\n```python\n{fixed_code_result}\n```")
           else:
               print("\nFixed Code: Not provided or found.")
       else:
           print("AgentExecutor not initialized. Cannot run the test.")
    except Exception as e:
        print(f"An error occurred in the main block: {e}")
        logger.error("Error in __main__ block", exc_info=True)