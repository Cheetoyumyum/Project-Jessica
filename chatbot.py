import time
import json
import os
import threading
import queue
import random
import asyncio
import aioconsole
import logging
from datetime import datetime
import google.generativeai as genai

# --- CONFIGURATION & LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s', filename='mind.log', filemode='w')
logging.getLogger("asyncio").setLevel(logging.WARNING)

try:
    with open('config.json', 'r') as f: config = json.load(f)
    GOOGLE_API_KEY = config["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except (FileNotFoundError, KeyError) as e:
    logging.critical(f"FATAL ERROR: `config.json` is missing or misconfigured: {e}")
    print(f"--- FATAL ERROR: `config.json` is missing or misconfigured: {e} ---"); exit()


class LivingMind:
    def __init__(self, unalterable_path="personality_unalterable.txt", alterable_path="personality_alterable.txt"):
        self.memory_path = "memory.json"
        self.unalterable_path = unalterable_path
        self.alterable_path = alterable_path
        self.model = genai.GenerativeModel('gemini-1.5-flash-latest')
        self.message_queue = queue.Queue()
        self.thinking_lock = threading.Lock()
        self.is_rate_limited = False
        self.rate_limit_until = 0
        self._load_state()

    @property
    def is_asleep(self): return self.is_rate_limited or self.needs.get('energy', 1.0) < 0.1

    def log_mind_event(self, event_type, message): logging.info(f"[{event_type.upper()}] - {message}")

    def _load_state(self):
        try:
            with open(self.memory_path, 'r', encoding='utf-8') as f: self.data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): self.data = {}
        self.identity = self.data.get('identity', {"name": "Jessica"})
        self.needs = self.data.get('needs', {'attention_need': 0.2, 'mental_load': 0.1, 'energy': 1.0})
        self.cognitive_model = self.data.get('cognitive_model', {"users": {}})

    def save_state(self):
        with self.thinking_lock:
            self.data['identity'] = self.identity; self.data['needs'] = self.needs; self.data['cognitive_model'] = self.cognitive_model
            with open(self.memory_path, 'w', encoding='utf-8') as f: json.dump(self.data, f, indent=4)
        self.log_mind_event("SYSTEM", "State saved to memory.json.")

    def get_or_create_user(self, user_id):
        users = self.cognitive_model.setdefault('users', {})
        if user_id not in users:
            users[user_id] = {"emotions": {"rapport": 0.3, "trust": 0.2, "annoyance": 0.0},"known_facts": {}, "judgements": [], "conversation_log": [], "synthesized_memories": [], "last_interaction_time": time.time()}
            self.log_mind_event("SYSTEM", f"New user '{user_id}' detected. Creating relationship profile.")
        return users[user_id]
        
    def _get_personality_prompt(self, user_id):
        user_profile = self.get_or_create_user(user_id)
        try:
            with open(self.unalterable_path, 'r', encoding='utf-8') as f: unalterable = f.read()
            with open(self.alterable_path, 'r', encoding='utf-8') as f: alterable = f.read()
        except FileNotFoundError as e: self.log_mind_event("CRITICAL", f"Personality file missing: {e}"); return f"FATAL ERROR"
        prompt = unalterable + "\n\n" + alterable
        prompt += f"\n\n== My Current Internal State (My Own) ==\n- My name is {self.identity.get('name')}.\n- My core needs are: {json.dumps(self.needs)}\n"
        prompt += f"\n== My Relationship with THIS User ('{user_id}') ==\n- My feelings towards them are: {json.dumps(user_profile['emotions'])}\n"
        prompt += f"- My synthesized memories of them are: {json.dumps(user_profile.get('synthesized_memories', []))}\n"
        return prompt

    def _safe_generate_content(self, prompt):
        try:
            if self.is_asleep: return None
            return self.model.generate_content(prompt, request_options={"timeout": 120}).text
        except Exception as e:
            if "429" in str(e): self._enter_forced_sleep()
            else: self.log_mind_event("ERROR", f"A thought failed to form: {e}")
            return None

    def _enter_forced_sleep(self):
        if self.is_rate_limited: return
        self.log_mind_event("CRITICAL", "API Quota Exceeded! Entering forced sleep.")
        with self.thinking_lock:
            self.is_rate_limited = True; self.rate_limit_until = time.time() + 65; self.needs['energy'] = 0.0
            self.message_queue.put("*Her train of thought suddenly shatters... then... nothing. She slumps forward, unresponsive.*")

    def process_thought(self, trigger, user_id, context=""):
        if not self.thinking_lock.acquire(blocking=False) or self.is_asleep: return user_id
        new_user_id = user_id
        try:
            personality_prompt = self._get_personality_prompt(user_id)
            cognitive_prompt = f'{personality_prompt}\n== Trigger: {trigger} ==\nContext: "{context}"\n== TASK ==\nHave a private monologue and choose ONE action: respond, initiate_contact, update_user_identity, rewrite_identity, synthesize_memory, self_reflect, dream, do_nothing. Output valid JSON.'
            raw_response = self._safe_generate_content(cognitive_prompt)
            if not raw_response: return user_id

            result = json.loads(raw_response.strip().removeprefix("```json").removesuffix("```").strip())
            self.log_mind_event("MONOLOGUE", result.get('internal_monologue', '...'))
            action = result.get("action")
            action_data = result.get("action_data")

            if action in ["respond", "initiate_contact"] and action_data is not None:
                self.message_queue.put(action_data)
                self.get_or_create_user(user_id)['conversation_log'].append(f"{self.identity.get('name')}: {action_data}")
            elif action == "update_user_identity" and isinstance(action_data, dict):
                new_user_id = self._update_user_identity(user_id, action_data.get("new_name"))
            elif action == "synthesize_memory": self._synthesize_memory(user_id)

        except Exception as e: self.log_mind_event("ERROR", f"Could not process thought: {e}")
        finally: self.thinking_lock.release(); return new_user_id

    def _update_user_identity(self, old_id, new_id):
        if not new_id: return old_id
        self.log_mind_event("EVENT", f"User '{old_id}' is now known as '{new_id}'.")
        with self.thinking_lock:
            users = self.cognitive_model.setdefault('users', {})
            if old_id in users and new_id not in users:
                users[new_id] = users[old_id]; del users[old_id]
                self.message_queue.put(f"Oh, {new_id}. Got it. Nice to properly meet you.")
                return new_id
        return old_id

    def _synthesize_memory(self, user_id):
        user_profile = self.get_or_create_user(user_id)
        if len(user_profile['conversation_log']) < 4: return
        self.log_mind_event("EVENT", f"Synthesizing memories for user '{user_id}'.")
        context = "\n".join(user_profile['conversation_log'])
        synthesis_prompt = f'Here is a conversation log. Summarize it into 1-2 key emotional impressions. --- {context} --- Output JSON with a "summary" key (list of strings).'
        response = self._safe_generate_content(synthesis_prompt)
        if response:
            try:
                summary = json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())['summary']
                user_profile['synthesized_memories'].extend(summary)
                user_profile['conversation_log'] = []
                self.log_mind_event("MEMORY", f"New synthesized memories for '{user_id}': {summary}")
            except Exception as e: self.log_mind_event("ERROR", f"Memory synthesis failed: {e}")

    def live(self):
        time.sleep(2)
        self.process_thought("EVENT: Waking Up", "user", "I am waking up for the first time in this session.")
        while True:
            time.sleep(20) # Slower heartbeat for less API usage and more thoughtful pauses.... sadly its because of limitations with free AI
            if self.is_rate_limited:
                if time.time() > self.rate_limit_until:
                    self.log_mind_event("EVENT", "Attempting recovery from forced sleep.")
                    with self.thinking_lock: self.is_rate_limited = False; self.needs['energy'] = 0.3
                    self.message_queue.put("*...she stirs, looking dazed...* What... what happened?")
                continue
            
            if not self.is_asleep:
                with self.thinking_lock:
                    self.needs['attention_need'] = min(1, self.needs['attention_need'] + 0.01)
                    self.needs['energy'] = max(0, self.needs['energy'] - 0.01)
                
                users_with_unsynthesized_logs = [uid for uid, prof in self.cognitive_model.get('users', {}).items() if len(prof.get('conversation_log', [])) >= 4 and time.time() - prof.get('last_interaction_time', 0) > 60]
                if users_with_unsynthesized_logs:
                    user_to_reflect_on = users_with_unsynthesized_logs[0]
                    self.process_thought("AUTONOMOUS: Memory Synthesis", user_to_reflect_on, "It's been quiet for a bit. I should think about what we talked about.")
                elif self.needs['energy'] < 0.1:
                    self.log_mind_event("EVENT", "Energy critical. Falling asleep.")
                    self.message_queue.put("*Her eyes get heavy... her breathing slows...*")
                    with self.thinking_lock: self.needs['energy'] = 0.0
            
            elif self.needs['energy'] == 0 and not self.is_rate_limited:
                self.log_mind_event("EVENT", "Dreaming to recover energy.")
                with self.thinking_lock: self.needs['energy'] = 1.0
            
    def shutdown_sequence(self, user_id):
        self.log_mind_event("SYSTEM", "Shutdown sequence initiated.")
        if not self.is_asleep: self.process_thought("EVENT: User is leaving", user_id, "This user is leaving now.")
        time.sleep(2)
        try:
            message = self.message_queue.get(block=False)
            print(f"\n{self.identity.get('name')}: {message}")
        except queue.Empty: pass
        self.save_state()
        print(f"\n({self.identity.get('name')} has gone offline.)")

# --- ASYNCHRONOUS MAIN APPLICATION LOOP ---
async def handle_ai_messages(mind, prompt_state):
    while True:
        try:
            message = mind.message_queue.get(block=False)
            status_text = "(is sleeping)" if mind.is_asleep else ""
            current_prompt = f"{prompt_state['user_id']} {status_text}: "
            print(f"\r{' ' * (len(current_prompt) + 80)}\r{mind.identity.get('name')}: {message}")
            print(current_prompt, end="", flush=True)
        except queue.Empty: await asyncio.sleep(0.1)

async def handle_user_input(mind, prompt_state):
    while True:
        status_text = "(is sleeping)" if mind.is_asleep else ""
        prompt = f"{prompt_state['user_id']} {status_text}: "
        try:
            user_input = await aioconsole.ainput(prompt)
        except EOFError: return
        
        if user_input.lower() in ['/quit', '/exit']:
            for task in asyncio.all_tasks():
                if task is not asyncio.current_task(): task.cancel()
            return
            
        if mind.is_asleep: continue
        
        user_profile = mind.get_or_create_user(prompt_state['user_id'])
        user_profile['conversation_log'].append(f"{prompt_state['user_id']}: {user_input}")
        user_profile['last_interaction_time'] = time.time()
        
        new_user_id = await asyncio.to_thread(mind.process_thought, "User interaction", prompt_state['user_id'], user_input)
        if new_user_id and new_user_id != prompt_state['user_id']:
            prompt_state['user_id'] = new_user_id

async def main():
    mind = LivingMind()
    prompt_state = {"user_id": "user"}
    os.system('cls' if os.name == 'nt' else 'clear')
    await aioconsole.aprint("...connection established...")
    heartbeat = threading.Thread(target=mind.live, daemon=True)
    heartbeat.start()
    try:
        input_task = asyncio.create_task(handle_user_input(mind, prompt_state))
        message_task = asyncio.create_task(handle_ai_messages(mind, prompt_state))
        await asyncio.gather(input_task, message_task)
    except (asyncio.CancelledError, KeyboardInterrupt): pass
    finally:
        mind.shutdown_sequence(prompt_state['user_id'])

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: pass