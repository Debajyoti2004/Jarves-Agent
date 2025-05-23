# 🎙️ Jarvis - Your Conversational AI Assistant 🚀

Welcome to **Jarvis**, a sophisticated, voice-activated AI assistant designed to streamline your daily tasks, provide information, and manage complex workflows through a natural language interface and an interactive visual UI. This project is under active development.

---

## ✨ Features

Jarvis is equipped with a growing suite of capabilities, managed by a powerful ReAct agent architecture:

- **👤 User Recognition (Conceptual):**
  - **Face Detection:**
  - (Planned/Conceptual) For identifying the current user to personalize responses and access user-specific data.
  - Using DeepFace as a model to verify master accessing the agent or anyone else.
- **🗣️ Voice Interaction:**
  - Wake-word activation ("Hey Jarvis").
  - Natural language command understanding.
  - Voice responses for feedback and results using Windows SAPI TTS.
- **🖥️ Interactive UI (Flask-based):**
  - Visual orb that changes color (Red: Deactivated/Listening for Wake Word, Blue: Active, Animated: Speaking) and animates based on Jarvis's state.
  - Real-time display of spoken text and status updates via Server-Sent Events.
- **🛠️ Core System Tools:**
  - 📱 **Application Launcher:** Opens desktop applications (e.g., "Jarvis, open Notepad").
  - 🌐 **Website Opener:** Launches websites in your default browser (e.g., "Jarvis, open Wikipedia").
- **🔍 Information Retrieval & Web Interaction:**
  - 🛒 **Amazon Product Scraper:** Searches Amazon.in for products, with optional filtering (e.g., "Jarvis, find wireless earbuds on Amazon with a rating above 4 stars"). Data structured using Cohere (optional).
  - 🏨 **Google Hotel Scraper:** Finds hotel accommodations based on location, dates, and preferences (e.g., "Jarvis, look for hotels in London from July 1st to July 5th under $200 a night"). Data structured using Cohere (optional).
  - ✈️ **Google Flight Scraper:** Retrieves round-trip flight details from Google Flights (e.g., "Jarvis, find flights from JFK to LAX next Monday, returning Friday"). Data structured using Cohere (optional).
  - 🧠 **Web & Image Searcher:** Answers general knowledge questions by searching the web (Tavily). Can also analyze images provided via camera (using local Ollama vision models like Llama 3.2 Vision/Llava) to answer visual queries (e.g., "Jarvis, what is this flower?" while showing it).
- **📄 Document & Code Interaction:**
  - 📸 **OCR Scanner (Jarves OCR Scanner):** Scans physical documents using the camera, extracts text via Tesseract OCR, and structures the information using Google Gemini (e.g., "Jarvis, scan this receipt and tell me the total").
  - 💻 **Code Agent (E2B Sandbox):**
    - Accepts Python code input via an interactive console portal.
    - Executes code in a secure E2B cloud sandbox environment.
    - Debugs code, suggests fixes, identifies missing modules (and can attempt installation within the sandbox).
    - Can read, write, and list files within the E2B sandbox.
    - Provides explanations of code execution and fixes using Google Gemini.
  - 📄 **Resume Analyzer:** Compares your resume (from a local PDF) against a job description (pasted by user) using Google Gemini. Provides:
    - Qualitative match assessment.
    - Key strengths aligned with the job.
    - Actionable areas for resume improvement.
- **👀 Visual Object Finder:**
  - Activates the camera to visually search for common objects (from COCO dataset, e.g., "keys", "bottle", "laptop") in the real-time feed using a YOLOv8n object detection model.
  - Provides on-screen bounding boxes and spoken feedback on object location.
  - Includes user controls for brightness/contrast and early quitting during live search.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Windows Operating System (primarily for SAPI TTS and `win32com` for application control). Some tools might be adaptable for other OS.
- An NVIDIA GPU (recommended for local Ollama vision models and YOLO, e.g., RTX 3050m or better).
- Webcam (for Face Detection, Visual Object Finder, OCR Scanner, Web/Image Searcher image input).
- Ollama installed and running (if using local vision models).
- Tesseract OCR Engine installed and configured in your system's PATH.
- Google Cloud Platform Account for:
  - Google Gemini API (for LLM functionalities for agent, OCR structuring, resume analysis, etc.).
- API Keys for:
  - E2B Sandbox (for the Code Agent).
  - (Optional) Cohere (if used for structuring scraped data from Amazon, Hotels, Flights).
  - (Optional) Tavily (for the `web_and_image_searcher` tool).

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/Debajyoti2004/Jarves-Agent.git
    cd Jarves-Agent
    ```

2.  **Create and activate a virtual environment (recommended):**

    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    _(Ensure `requirements.txt` is up-to-date with all necessary packages, including libraries for face detection like `opencv-python` and potentially `face_recognition` or `mediapipe` if you implement it)._

4.  **Environment Variables:**
    Create a `.env` file in the project root (you can copy `.env.example` if provided) and populate it with your API keys and configurations:

    ```dotenv
    # Core Google API Key (for Gemini LLM used by Agent, OCR, Resume, etc.)
    GOOGLE_API_KEY="your_google_gemini_api_key"

    # Langchain Agent Configuration
    AGENT_LLM_MODEL="gemini-1.5-pro-latest" # Or your preferred Google model for the agent

    # E2B Sandbox API Key (for Code Agent)
    E2B_API_KEY="your_e2b_api_key"

    # Optional: Cohere API Key (for structuring web scraper output)
    COHERE_API_KEY="your_cohere_api_key"

    # Optional: Tavily API Key (for Web & Image Searcher tool)
    TAVILY_API_KEY="tvly-..."

    # Ollama Vision Model (for Web & Image Searcher's image analysis)
    OLLAMA_VISION_MODEL="llava:latest" # e.g., llama3.2-vision:latest, llava:llama3

    # Resume Analyzer Configuration
    YOUR_RESUME_PDF_PATH="DRIVE:/path/to/your/resume.pdf" # Use forward slashes

    # Flask UI URL (Jarvis backend sends notifications here)
    FLASK_UI_URL="http://127.0.0.1:5000"

    # If you use a different model name for the main agent LLM via GOOGLE_LLM_MODEL
    # GOOGLE_LLM_MODEL="gemini-1.5-pro-latest"
    ```

5.  **Pull Ollama Vision Model (if using for `web_and_image_searcher`):**
    ```bash
    ollama pull your_ollama_vision_model_tag # e.g., ollama pull llava:llama3.2
    ```
    Ensure the tag matches `OLLAMA_VISION_MODEL` in your `.env`.

### Running Jarvis

1.  **Start the Flask UI (for visual feedback):**
    Open a terminal, navigate to the directory containing `app.py` (e.g., `App/`), and run:

    ```bash
    python app.py
    ```

    Open `http://127.0.0.1:5000` in your browser.

2.  **Start Jarvis Core Logic (with the Agent):**
    Open another terminal, navigate to the project root (or where your main script like `main_app.py` or `jarves.py` is located), and run:

    ```bash
    python main_app.py
    ```

    _(Or `python jarves.py` if you're running it directly and it's set up to initialize the agent)._

3.  **Interact:**
    - Wait for Jarvis to announce it's "online" and "listening for wake word."
    - Say your wake word (e.g., "Hey Jarvis").
    - Once Jarvis responds (e.g., "Yes Sir?"), give your command.

---

## 🛠️ Tool Overview

A brief look at the integrated tools:

- **`open_app_tool`**: Launches desktop applications.
- **`open_website_tool`**: Opens URLs in the default browser.
- **`amazon_web_scrapper`**: Fetches product listings from Amazon.
- **`google_hotel_scrapper`**: Finds hotel accommodations via Google Hotels.
- **`google_flight_scrapper`**: Retrieves flight information from Google Flights.
- **`jarves_ocr_scanner`**: Scans documents via camera, performs OCR, and structures text using Google Gemini.
- **`code_agent`**: Interactive portal for Python code input; debugs, explains, or improves code using an E2B sandbox and Google Gemini.
- **`web_and_image_searcher`**: Answers general queries using web search (Tavily) and can analyze camera images (Ollama Vision) for context.
- **`visual_object_finder`**: Locates common objects in the live camera feed using YOLOv8n.
- **(Conceptual) `face_recognition_tool`**: Identifies known users via camera.

## 🔮 Future Enhancements.

- More sophisticated and persistent memory system (e.g., vector database).
- Deeper integration with specific desktop or web applications.
- Advanced UI/UX features and customization.
- Support for a wider range of LLMs and local models.
- Refined multi-turn conversation handling and context management.
- More robust error handling and user feedback mechanisms.

## ⚠️ Disclaimer

This project interacts with external APIs and your local system. Use with caution and ensure you understand the permissions you grant and the security implications of API keys. This software is provided "as-is" without any warranty.

---
