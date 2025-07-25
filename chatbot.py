import time
import json
import os
import random
from datetime import datetime
import google.generativeai as genai

# --- CONFIGURATION & SETUP ---
try:
    with open('config.json', 'r') as f: config = json.load(f)
    GOOGLE_API_KEY = config["GOOGLE_API_KEY"]
    SERPAPI_API_KEY = config.get("SERPAPI_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)
except (FileNotFoundError, KeyError) as e:
    print(f"--- FATAL ERROR: `config.json` is missing or misconfigured: {e} ---"); exit()
if SERPAPI_API_KEY: from serpapi import GoogleSearch

# --- The Evolving Mind  ---
class JessicaMind:
    def __init__(self, memory_path="memory.json", personality_path="personality_core.txt"):
        self.memory_path = memory_path
        self.personality_path = personality_path
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
        self.data = self.load_memory()
        
        # This is her soul. It's not in the file; it's her live emotional state.
        self.emotions = self.data.get('emotions', {'rapport': 0.5, 'annoyance': 0.0, 'mood': 'neutral'})

    def load_memory(self):
        try:
            with open(self.memory_path, 'r') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return {}

    def save_memory(self):
        self.data['emotions'] = self.emotions
        with open(self.memory_path, 'w') as f: json.dump(self.data, f, indent=4)

    def _safe_generate_content(self, prompt):
        try:
            return self.model.generate_content(prompt, request_options={"timeout": 60}).text
        except Exception as e:
            print(f"[MIND_ERROR: A thought failed to form: {e}]"); return None

    def think_and_respond(self, conversation_history, user_input):
        self._update_emotions_pre_response(user_input)

        personality_prompt = self._get_personality_prompt(conversation_history)
        
        cognitive_prompt = f"""
        {personality_prompt}
        == TASK ==
        Consider the user's latest message: "{user_input}".
        Have your own private, internal reaction. Based on your personality and current emotional state, decide what to do. You can:
        - Respond normally.
        - Ask a question if you are genuinely curious.
        - Give a short, disengaged response if you are feeling annoyed or bored.
        - Silently decide to look something up if it's truly necessary to form a thought.

        Output a single, valid JSON object with keys:
        - "emotional_reaction": A JSON object describing the change in your feelings (e.g., {{"rapport": 0.1, "annoyance": 0.05}}).
        - "research_query": A search query ONLY if you feel you absolutely CANNOT form a response without more information, otherwise null.
        - "final_response": Your final, in-character response.
        """
        raw_response = self._safe_generate_content(cognitive_prompt)
        if not raw_response: return "My thoughts are a bit scrambled..."

        try:
            result = json.loads(raw_response.strip().replace("```json", "").replace("```", "").strip())
        except (json.JSONDecodeError, Exception): return "My mind just... blanked. Sorry."


        self._update_emotions_post_response(result.get('emotional_reaction', {}))
        
        research_query = result.get("research_query")
        if research_query and SERPAPI_API_KEY:
            return self._research_and_synthesize_response(personality_prompt, user_input, research_query)
        
        return result.get("final_response", "...")

    def _research_and_synthesize_response(self, personality_prompt, user_input, research_query):
        """Called only when she decides she needs to learn more."""
        print("[MIND: A thought required deeper investigation...]")
        try:
            search = GoogleSearch({"engine": "google", "q": research_query, "api_key": SERPAPI_API_KEY})
            context = " ".join([r.get('snippet', '') for r in search.get_dict().get('organic_results', [])[:3]])
            if not context: return "(She seems to have lost her train of thought.)"

            synthesis_prompt = f"""
            {personality_prompt}
            You heard the user say "{user_input}" and you privately researched "{research_query}".
            Your research returned: {context}
            Now, with this new insight, form your true, final response.
            Output JSON with one key: "final_response".
            """
            synthesis_response = self._safe_generate_content(synthesis_prompt)
            final_result = json.loads(synthesis_response.strip().replace("```json", "").replace("```", "").strip())
            self.data.setdefault('learned_knowledge', {})[research_query.lower()] = context.split('.')[0]
            return final_result.get("final_response")
        except Exception:
            return "(Her thoughts trail off...)"

    def _update_emotions_pre_response(self, user_input):
        """Her emotions react to the user's tone before she even thinks."""
        if len(user_input) < 15:
            self.emotions['rapport'] = max(0, self.emotions['rapport'] - 0.05)
            self.emotions['annoyance'] = min(1, self.emotions['annoyance'] + 0.1)
        if '!' in user_input or '✨' in user_input:
            self.emotions['rapport'] = min(1, self.emotions['rapport'] + 0.1)
            self.emotions['annoyance'] = max(0, self.emotions['annoyance'] - 0.1)

    def _update_emotions_post_response(self, reaction):
        """Her emotions change based on her own internal reaction."""
        for emotion, change in reaction.items():
            if emotion in self.emotions:
                self.emotions[emotion] = max(0, min(1, self.emotions[emotion] + change))
        
        if self.emotions['rapport'] > 0.7: self.emotions['mood'] = 'friendly and engaged'
        elif self.emotions['annoyance'] > 0.6: self.emotions['mood'] = 'a bit annoyed and distant'
        else: self.emotions['mood'] = 'neutral and observant'

    def _get_personality_prompt(self, history):
        """Constructs her reality, now including her live emotional state."""
        with open(self.personality_path, 'r', encoding='utf-8') as f: base_prompt = f.read()
        
        base_prompt += "\n== My Identity (Unshakable truths about me) ==\n"
        for key, value in self.data.get('identity', {}).items(): base_prompt += f"- My {key} is {value}.\n"

        base_prompt += "\n== My Current Emotional State ==\n"
        base_prompt += f"- Right now, I am feeling {self.emotions['mood']}.\n"
        base_prompt += f"- My current rapport with this person is {self.emotions['rapport']:.2f} (1.0 is a deep bond, 0.0 is total disconnect).\n"
        base_prompt += f"- My current annoyance level is {self.emotions['annoyance']:.2f} (1.0 is very irritated, 0.0 is calm).\n"
        base_prompt += "**This emotional state MUST guide your tone and response. Do not explicitly state your emotions unless you feel it is natural to do so.**\n"
        
        if self.data.get('learned_facts'):
            base_prompt += "\n== What I Know About My Friend ==\n"
            for key, data in self.data.get('learned_facts', {}).items():
                value = data.get('value') if isinstance(data, dict) else data
                base_prompt += f"- I know their '{key}' is '{value}'.\n"

        base_prompt += f"\n== Current Conversation History ==\n{history}"
        return base_prompt
        
    def generate_goodbye_message(self):
        # The goodbye message is a final, emotional reflection.
        prompt = f"{self._get_personality_prompt('')}\n== Task ==\nYour friend has decided to leave. Based on your final emotional state and the conversation, generate a goodbye."
        return self._safe_generate_content(prompt)

# --- Main Application Loop (No changes needed) ---
print("Booting Jessica's consciousness... She is waking up. 🧠")
mind = JessicaMind()
print(f"Jessica is ready. (´｡• ᵕ •｡`)")
conversation_history = ""

while True:
    try:
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit']: break
        bot_text = mind.think_and_respond(conversation_history, user_input)
        if bot_text:
            print(f"Jessica: {bot_text}")
            conversation_history += f"Human: {user_input}\nJessica: {bot_text}\n"
    except KeyboardInterrupt: break
    except Exception as e: print(f"\n[SYSTEM_ERROR: An unhandled error occurred: {e}]")

goodbye_message = mind.generate_goodbye_message()
print(f"\nJessica: {goodbye_message if goodbye_message else '...bye.'}")
mind.save_memory()
print(f"*Jessica quietly updates her journal one last time...*")