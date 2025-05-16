import os
import re
import logging
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox, TimeoutException
from e2b import SandboxException
from concurrent.futures import ThreadPoolExecutor
from langchain.tools import tool
import json

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("E2BExecutorAgent")

E2B_API_KEY = os.getenv("E2B_API_KEY")

sandbox_instance = None

def initialize_sandbox():
    global sandbox_instance
    if not E2B_API_KEY:
        logger.error("E2B_API_KEY not found in environment variables.")
        raise ValueError("E2B_API_KEY is required.")
    try:
        logger.info("Initializing E2B Sandbox...")
        sandbox_instance = Sandbox(api_key=E2B_API_KEY)
        logger.info("E2B Sandbox initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize E2B Sandbox: {e}", exc_info=True)
        sandbox_instance = None
        raise

def get_sandbox():
    global sandbox_instance
    if sandbox_instance is None:
        initialize_sandbox()
    if sandbox_instance is None:
        raise RuntimeError("E2B Sandbox could not be initialized.")
    return sandbox_instance

@tool
def extract_missing_modules(error_traceback: str) -> list:
    """Extracts missing module names from ImportError/ModuleNotFoundError tracebacks.
    Args:
        error_traceback (str): The traceback string containing the error message.
    Returns:
        list: A list of unique missing module names found.
    """
    if error_traceback.startswith("{"):
        error_traceback=json.loads(error_traceback)["error_traceback"]

    pattern = r"(?:ModuleNotFoundError|ImportError): No module named ['\"]([^'\"]+)['\"]"
    matches = re.findall(pattern, error_traceback)
    missing = list(set(matches))

    if not missing:
        pattern_cannot_import = r"ImportError: cannot import name ['\"]([^'\"]+)['\"]"
        matches_cannot_import = re.findall(pattern_cannot_import, error_traceback)
        missing.extend(list(set(matches_cannot_import)))

    missing = list(set(missing))

    if missing:
        logger.info(f"Detected potential missing imports from traceback: {missing}")
    else:
        logger.warning(f"Could not extract specific module names from traceback:\n{error_traceback}")
    return missing

@tool
def executor(code: str) -> str:
    """
    Executes Python code using the E2B Code Interpreter sandbox.
    Args:
        command (str): The Python code string to execute.
    Returns:
        str: A message indicating success (✅) or failure (❌), with output or error details.
    """
    print(f"Input:{code}")
    try:
        sandbox = get_sandbox()
    except Exception as e:
        return f"❌ Critical Error: Failed to get E2B sandbox: {e}"

    logger.info(f"Executing command:\n```python\n{code}\n```")
    if code.startswith("{"):
        code = json.loads(code)
        if code["code"].strip() is None:
            return "No code given by user"
    code = code["code"]

    try:
        execution = sandbox.run_code(code, timeout=120)

        if execution.error:
            logger.warning(f"Execution failed: {execution.error.name} - {execution.error.value}")
            logger.debug(f"Traceback:\n{execution.error.traceback}")

            return (
                f"❌ Execution failed with `{execution.error.name}`: {execution.error.value}\n"
                f"Traceback:\n{''.join(execution.error.traceback)}"
            )
        result_str = f"✅ Code executed successfully:\n```python\n{code}\n```\n"
        
        if execution.results:
            text_outputs = [res.text for res in execution.results if res.is_main_result and hasattr(res, 'text')]
            if text_outputs:
                result_str += f"Result:\n{''.join(text_outputs)}\n"

            plot_outputs = [res for res in execution.results if res.png]
            if plot_outputs:
                result_str += f"📊 Generated {len(plot_outputs)} plot(s)/image(s)."

        elif execution.logs:
            result_str += f"Logs:\nStdout:\n{execution.logs.stdout}\nStderr:\n{execution.logs.stderr}"
        else:
            result_str += "Result: (No explicit output)"
        return result_str

    except TimeoutException:
        logger.error(f"Execution timed out for command: {code}")
        return f"⏱️ Execution timed out after 120 seconds."
    except SandboxException as e:
        logger.error(f"Sandbox execution error: {e}", exc_info=True)
        return f"❌ Sandbox Execution Error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error during execution: {e}", exc_info=True)
        return f"❌ Unexpected Error: {type(e).__name__} — {e}"


def install_package(package: str, sandbox: Sandbox) -> bool:
    try:
        logger.info(f"Attempting to install package: {package}")
        pip_command = f"pip install {package}"
        sandbox.run_code(pip_command, timeout=120)
        logger.info(f"Successfully installed package: {package}")
        return True
    except Exception as e:
        logger.error(f"Failed to install package {package}: {e}", exc_info=True)
        return False

@tool
def file_read(path: str) -> str:
    """
    Reads the content of a file from the E2B sandbox filesystem.
    Args:
        path (str): The path to the file within the sandbox.
    Returns:
        str: The content of the file or an error message.
    """

    if path.startswith("{"):
        path = json.loads(path)["path"]
    try:
        sandbox = get_sandbox()
        logger.info(f"Reading file from sandbox: {path}")
        content = sandbox.files.read(path)
        logger.info(f"Successfully read {len(content)} bytes from {path}")
        return f"✅ Content of '{path}':\n```\n{content}\n```"
    except FileNotFoundError:
        logger.warning(f"File not found in sandbox: {path}")
        return f"❌ Error: File not found at path '{path}' in the sandbox."
    except Exception as e:
        logger.error(f"Error reading file '{path}' from sandbox: {e}", exc_info=True)
        return f"❌ Error reading file '{path}': {type(e).__name__} - {e}"

@tool
def file_write(path: str, content: str) -> str:
    """
    Writes content to a file in the E2B sandbox filesystem. Creates directories if needed.
    Args:
        path (str): The path where the file should be written within the sandbox.
        content (str): The content to write to the file.
    Returns:
        str: A message indicating success or failure.
    """
    if path.startswith("{"):
        path = json.loads(path)["path"]
        content = json.loads(path)["content"]

    try:
        sandbox = get_sandbox()
        logger.info(f"Writing {len(content)} bytes to sandbox file: {path}")
        dir_path = os.path.dirname(path)
        if dir_path and dir_path != '.':
            try:
                sandbox.files.make_dir(dir_path)
                logger.info(f"Ensured directory exists or created: {dir_path}")
            except Exception as dir_err:
                logger.warning(f"Note: Could not explicitly create directory {dir_path} (may already exist): {dir_err}")

        sandbox.files.write(path, content)
        logger.info(f"Successfully wrote to {path}")
        return f"✅ Successfully wrote content to '{path}' in the sandbox."
    except Exception as e:
        logger.error(f"Error writing file '{path}' to sandbox: {e}", exc_info=True)
        return f"❌ Error writing file '{path}': {type(e).__name__} - {e}"

@tool
def list_files(path: str = '.') -> str:
    """
    Lists files and directories at the specified path in the E2B sandbox.
    Args:
        path (str): The directory path to list within the sandbox (default is '/').
    Returns:
        str: A list of files/directories or an error message.
    """ 
    if path.startswith("{"):
        path = json.loads(path)["path"]
    try:
        sandbox = get_sandbox()
        logger.info(f"Listing files in sandbox path: {path}")
        files = sandbox.files.list(path)
        file_list_str = "\n".join([f"{'d' if f.__dir__ else '-'} {f.name}" for f in files])
        logger.info(f"Found {len(files)} items in {path}")
        return f"✅ Files/Directories in '{path}':\n{file_list_str}"
    except FileNotFoundError:
        logger.warning(f"Directory/Path not found in sandbox for listing: {path}")
        return f"❌ Error: Directory/Path not found at path '{path}' in the sandbox."
    except Exception as e:
        logger.error(f"Error listing files in path '{path}' from sandbox: {e}", exc_info=True)
        return f"❌ Error listing files in '{path}': {type(e).__name__} - {e}"

@tool
def close_sandbox() -> str:
    """
    Gracefully closes the current E2B sandbox session.
    Returns:
        str: A message indicating success or error.
    """
    global sandbox_instance
    if sandbox_instance is None:
        return "⚠️ No sandbox session is currently active."
    try:
        sandbox_instance.kill()
        logger.info("Sandbox session closed successfully.")
        sandbox_instance = None
        return "✅ E2B sandbox session closed successfully."
    except Exception as e:
        logger.error(f"Error closing sandbox session: {e}", exc_info=True)
        return f"❌ Error closing sandbox session: {type(e).__name__} - {e}"

