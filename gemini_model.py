import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables.")
else:
    try:
        genai.configure(api_key=API_KEY)

        print("Available models you can access with your API key:")
        print("-" * 30)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"Model Name: {m.name}")
                print(f"  Display Name: {m.display_name}")
                print(f"  Description: {m.description}")
                print(f"  Supported Generation Methods: {m.supported_generation_methods}")
                print(f"  Input Token Limit: {m.input_token_limit}")
                print(f"  Output Token Limit: {m.output_token_limit}")
                print("-" * 20)

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure your API key is valid and has the necessary permissions.")