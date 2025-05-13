import subprocess
import sys
from difflib import get_close_matches
from typing import Optional,List,Tuple,Any
import os
from dotenv import load_dotenv
import json
load_dotenv()

APP_COMMANDS = json.loads(os.getenv("APP_COMMANDS","{}"))

def suggest_apps(
    query:Optional[str]
    )->Optional[List[str]] | Optional[List[Tuple[str]]]:
    matches = get_close_matches(query, APP_COMMANDS.keys(), n=3, cutoff=0.5)
    if matches:
        print(f"💡 Did you mean: {', '.join(matches)}?")
        return matches
    else:
        print("ℹ️ No similar applications found.")
        return None


def open_app(
    app_name: str
    ) -> bool:

    app_key = app_name.lower().strip()
    command = APP_COMMANDS.get(app_key)

    if not command:
        suggestions = suggest_apps(app_key)
        if suggestions:
            corrected = suggestions[0]
            print(f"🔄 '{app_name}' not found. Using closest match: '{corrected}'")
            command = APP_COMMANDS[corrected]
        else:
            print(f"⚠️ Error: Application '{app_name}' not found and no similar matches.")
            return False

    try:
        subprocess.Popen(command, shell=True,
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        print(f"✅ Launching: {command}")
        return True
    except FileNotFoundError:
        print(f"❌ Error: '{command}' not found. Check if the program is installed and in PATH.")
    except Exception as e:
        print(f"❌ Error: Failed to start '{command}'. ({type(e).__name__}: {e})")
    return False

if __name__ == "__main__":
    test_apps = [
        "Notepad", "VS Code", "Calculatr",
        "nonexistent app", "Crome", "bad command app",
        "whatsapp","sptify"
    ]

    APP_COMMANDS["bad command app"] = "nonexistent_program_12345"

    print("🔧 --- Application Launch Test ---")

    for app in test_apps:
        print(f"\n🟡 Requesting: {app}")
        success = open_app(app)
        if success:
            print(f"➡️ Launch command sent for '{app}'.")
        else:
            print(f"⬅️ Could not launch '{app}'.")

    print("\n✅ --- Test Complete ---")
