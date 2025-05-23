import os
import json
from datetime import datetime

class ConversationHistoryManager:
    def __init__(self, history_file_path="conversations.json"):
        self.history_file_path = history_file_path
        self.conversations = self._load_history()

    def _load_history(self):
        try:
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r') as f: 
                    return json.load(f)
            return {}
        except Exception as e: 
            print(f"Hist Load Err: {e}")
            return {}

    def _save_history(self):
        try:
            with open(self.history_file_path, 'w') as f: 
                json.dump(self.conversations, f, indent=4)
        except Exception as e: 
            print(f"Hist Save Err: {e}")

    def get_contact_history(self, contact_name, num_messages=5):
        history = self.conversations.get(contact_name, [])
        return history[-num_messages:]

    def add_message_to_history(self, contact_name, sender, message):
        if contact_name not in self.conversations: 
            self.conversations[contact_name] = []

        self.conversations[contact_name].append({
            "sender": sender, "message": message, "timestamp": datetime.now().isoformat()
        })
        self._save_history()