import webbrowser
import sys
from difflib import get_close_matches
from typing import Optional,List,Tuple,Any
import os 
import json
from dotenv import load_dotenv
load_dotenv()

sites_map = json.loads(os.getenv("WEB_SITES_COMMAND", "{}"))

def suggest_websites(
    query:Optional[str]
    )->Optional[List[str]] | Optional[List[Tuple[str]]]:
    matches = get_close_matches(query, sites_map.keys(), n=3, cutoff=0.5)
    if matches:
        print(f"💡 Did you mean: {', '.join(matches)}?")
        return matches
    else:
        print("ℹ️ No similar web site found.")
        return None

def open_website(
    site_name:str
    ) -> bool:
    site_name_lower = site_name.lower()
    url = sites_map.get(site_name_lower)

    if not url:
        suggestions = suggest_websites(site_name)
        if suggestions:
            best_match = suggestions[0]
            print(f"Did you mean '{best_match}'? Opening that for you.")
            url = sites_map[best_match]
        else:
            print(f"❌ Website alias '{site_name}' not found.", file=sys.stderr)
            available = ", ".join(sorted(sites_map.keys()))
            print(f"Available sites: {available}", file=sys.stderr)
            return False

    try:
        print(f"🌐 Opening '{url}' ...")
        was_opened = webbrowser.open_new_tab(url)
        if not was_opened:
            print(f"⚠️ Could not confirm if browser launched successfully.", file=sys.stderr)
        return True
    except Exception as e:
        print(f"💥 Error while opening site '{site_name}': {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    open_website("youtub")   
    open_website("Gmail")   
    open_website("insta")   
    open_website("yahoo") 
    open_website("whatapp")  
