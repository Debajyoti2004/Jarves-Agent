
import logging

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def open_code_input_portal(
    prompt_message: str = "▶️ Please paste or type your code below.",
    end_keyword: str = "Ctrl+Z"
) -> str:
    logger.info(f"⌨️ Opening code input portal. End keyword: '{end_keyword}'")
    print(f"\n{prompt_message}")
    print(f"   Type '{end_keyword}' on a new line and press Enter when you are finished.")
    print("-" * 40)

    code_lines = []
    while True:
        try:
            line_prompt = f"{len(code_lines):>3}: " if code_lines else "  1: "
            line = input(line_prompt)

            if line.strip().upper() == end_keyword.upper():
                logger.info("Code input portal finished by end keyword.")
                print("-" * 40)
                print("✅ Code input received.")
                break
            else:
                code_lines.append(line)
        except EOFError:
            logger.info("Code input portal finished by EOF signal.")
            print("\n" + "-" * 40)
            print("✅ Code input received (EOF signal).")
            break
        except KeyboardInterrupt:
            logger.warning("Code input portal interrupted by user (Ctrl+C).")
            print("\n" + "-" * 40)
            print("🛑 Code input cancelled by user.")
            return ""

    full_code = "\n".join(code_lines)
    logger.info(f"Collected {len(code_lines)} lines of code ({len(full_code)} characters).")
    return full_code
