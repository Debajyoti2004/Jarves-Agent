
import os
import platform

TESSERACT_CMD_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
WHATSAPP_EXE_PATH = r"C:\Users\YourUsername\AppData\Local\WhatsApp\WhatsApp.exe" 

IMAGE_PATH_BASE = "images/"
NEW_CHAT_BUTTON_IMG = os.path.join(IMAGE_PATH_BASE, "new_chat_button.png")
SEARCH_BAR_IMG = os.path.join(IMAGE_PATH_BASE, "search_bar.png")
CHAT_INPUT_BAR_IMG = os.path.join(IMAGE_PATH_BASE, "chat_input_bar.png")
SEND_BUTTON_IMG = os.path.join(IMAGE_PATH_BASE, "send_button.png") 

CONTACT_LIST_REGION = (50, 180, 350, 700)
CHAT_HISTORY_SNIPPET_REGION = (370, 100, 1160, 840) 

PYAUTOGUI_FAILSAFE = True
PYAUTOGUI_PAUSE = 0.3 

CONVERSATION_MEMORY_PATH = "C:/Users/Debajyoti/OneDrive/Desktop/Jarves full agent/WhatsAppAssistant/conversation.json"
SPEECH_TIMEOUT_SECONDS = 10
SPEECH_PHRASE_LIMIT_SECONDS = 7
GOOGLE_API_KEY="AIzaSyD7qCCozQZnv3CnXKSNizZmYwCiIiapoEk"