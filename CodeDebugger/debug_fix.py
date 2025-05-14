import os
import re
import logging
from dotenv import load_dotenv
from typing import Tuple, Optional, List
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools.render import render_text_description

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
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

API_KEY_GOOGLE = os.getenv("GOOGLE_API_KEY")
llm_model_name_from_env = os.getenv("GOOGLE_LLM_MODEL", "gemini-pro") 

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

custom_langchain_code_agent_runnable = None
if llm:
    try:
        prompt = ChatPromptTemplate.from_template(AGENT_PROMPT)
        prompt_with_tools = prompt.partial(
            tools=render_text_description(tools),
            tool_names=", ".join([t.name for t in tools]),
        )
        custom_langchain_code_agent_runnable = create_react_agent(llm, tools, prompt_with_tools)
        logger.info("Custom Langchain ReAct Code Agent Runnable created successfully.")
    except Exception as e:
        logger.error(f"Failed to create Langchain ReAct agent components: {e}", exc_info=True)
else:
    logger.warning("LLM not initialized, Agent cannot be created.")


def custom_code_agent(task_input: str, config: Optional[RunnableConfig] = None) -> Tuple[str, Optional[str]]:
    if not custom_langchain_code_agent_runnable:
        error_msg = "Agent is not initialized."
        logger.error(error_msg)
        return error_msg, None

    logger.info(f"Running Agent for input: {task_input[:150].replace(os.linesep, ' ')}...")
    explanation: str = "Agent did not produce a standard explanation."
    fixed_code: Optional[str] = None

    try:
        response = custom_langchain_code_agent_runnable.invoke({"input": task_input}, config=config)
        final_answer = response.get("output") if isinstance(response, dict) else str(response)

        if final_answer:
            logger.info("Agent completed.")
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
                    if potential_code and not potential_code.startswith("##"):
                        fixed_code = potential_code
                        logger.warning("No ```python block in '## Fixed Code:'. Using raw content.")
                    else:
                        fixed_code = "Marker '## Fixed Code:' found, but no valid code block."
                        logger.warning(fixed_code)
            else:
                if explanation and "Raw output" not in explanation and "No '## Explanation:'" not in explanation : 
                    explanation += "\nNote: '## Fixed Code:' marker was not found."
                logger.info("No '## Fixed Code:' marker found in agent output.")
            
            return explanation, fixed_code
        else:
            logger.error("Agent returned no 'output'.")
            return "Agent returned no 'output'.", None
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        return f"Critical error during agent execution: {type(e).__name__} - {str(e)}", None
