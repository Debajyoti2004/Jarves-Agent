
import google.generativeai as genai

class MessageAgentLLM:
    def __init__(self, speaker, history_manager, google_api_key=None):
        self.speaker = speaker
        self.history_manager = history_manager
        self.google_api_key = google_api_key
        self.model = None
        if self.google_api_key:
            try:
                genai.configure(api_key=self.google_api_key)
                self.model = genai.GenerativeModel('gemini-pro')
            except:
                self.model = None

    def _format_history_for_prompt(self, history_list):
        if not history_list:
            return "No recent messages in history."
        return "\n".join([
            f"{'You' if msg.get('sender') == 'user' else msg.get('sender', 'Unknown')}: {msg.get('message', '')}"
            for msg in history_list
        ])

    def _get_prompt(self, contact_name, history_text, user_msg):
        return f"""You are an expert WhatsApp communication assistant. Your goal is to refine the user's raw message to make it more appropriate, clear, polite, and contextually aware for sending to '{contact_name}'.

Follow these guidelines:
- Maintain the user's original intent and core meaning.
- If the user's message is already perfect, return it as is or with very minor touch-ups.
- Consider the provided conversation history for tone and context.
- Ensure the refined message sounds natural for a WhatsApp chat.
- Avoid overly formal language unless implied by the context or user.
- For very short inputs (e.g., "ok", "yes"), make them slightly more conversational.
- Ensure questions remain questions.
- Convey emotions like gratitude or apologies appropriately.

Conversation History with {contact_name} (most recent messages first):
{history_text}

User's raw message to send to {contact_name}:
"{user_msg}"

Based on all the above, provide ONLY the refined message suitable for sending:"""

    def _call_llm_api(self, prompt_text):
        try:
            response = self.model.generate_content(prompt_text)
            parts = [part.text for part in response.parts if hasattr(part, 'text')]
            msg = "".join(parts).strip() if parts else response.text.strip()
            return msg.split(":", 1)[1].strip() if msg.lower().startswith("refined message:") else msg
        except Exception as e:
            return print(f"Error occured in calling llm api in MessageAgentLLM:{e}")

    def generate_refined_message(self, contact_name, user_raw_message):
        history = self.history_manager.get_contact_history(contact_name, num_messages=5) if self.history_manager else []
        history_text = self._format_history_for_prompt(history)

        prompt = self._get_prompt(contact_name, history_text, user_raw_message)
        msg = self._call_llm_api(prompt)
        return msg.strip() if msg else user_raw_message.strip()
