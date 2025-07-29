import time
import json
import os
import threading
import queue
import logging
import re
import random
from datetime import datetime, date
import google.generativeai as genai
from limbic_system import LimbicState
from world_manager import WorldManager
from action_manager import ActionManager
from action_system import (
    Action, IdleAction, ThinkAndRespondAction, ReadBookAction, SleepAction,
    ExploreAction, DoWorkAction, SearchAction, JournalAction, PaintAction,
    LookOutOfWindowAction, EatAction, ExamineObjectAction, InteractObjectAction,
    ResearchAndLearnAction, DyeHairAction
)
from rich.logging import RichHandler
from rich.traceback import install

install()

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            keywords=[
                "SYSTEM", "LIFECYCLE", "PERCEPTION", "AUTONOMY", "SPONTANEITY", "ACTION_PLAN",
                "LIMBIC_STATE", "CONSOLIDATION", "DREAM", "WORLD", "WORLD_GEN",
                "COGNITIVE_TRIGGER", "MONOLOGUE", "ACTION_DISPATCH", "ACTION_FAILURE",
                "EVOLUTION", "IDENTITY", "PROACTIVE_EVENT", "DYNAMIC_ACTION",
                "ERROR", "WARNING", "CRITICAL", "ACTION_MANAGER", "ACTION_SYSTEM", "MISSION"
            ]
        ),
        logging.FileHandler("mind.log", mode='w', encoding='utf-8')
    ]
)

log = logging.getLogger("rich")

# =======================================================================================
# == Configuration and Initialization
# =======================================================================================

try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    GOOGLE_API_KEY = config["GOOGLE_API_KEY"]
    SERPAPI_API_KEY = config.get("SERPAPI_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)
except (FileNotFoundError, KeyError) as e:
    log.critical(f"[CRITICAL] FATAL ERROR: `config.json` is missing or misconfigured: {e}")
    exit()

class Psyche:

    def __init__(self, unalterable_path="personality_unalterable.json", alterable_path="personality_alterable.json"):
        self.codex_path = "codex.json"
        self.world_path = "world_state.json"
        self.journal_path = "journal.txt"
        self.body_path = "body.json"
        self.unalterable_path = unalterable_path
        self.alterable_path = alterable_path
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self.message_queue = queue.Queue()
        self.system_command_queue = queue.Queue()
        self.state_lock = threading.Lock()

        self.somatic = SomaticProcessor(self)
        self.subconscious = SubconsciousMind(self)
        self.conscious = ConsciousMind(self)

        self._load_state()

        self.limbic = LimbicState(self.genetic_code)
        self.world_manager = WorldManager(self)
        self.action_manager = ActionManager(self)
        
        self.action_plan = []
        self.current_mission = None
        self.bravery_boost = 0.0
        self.is_sleeping = False
        self.is_rate_limited = False
        self.rate_limit_until = 0
        self.last_interaction_time = time.time()
        self.last_user_id = "system"
        self.last_personality_drift_check = datetime.now()


    def _create_default_personality_files(self):
        self.log_mind_event("SYSTEM_CREATE", "Personality JSON files not found. Creating defaults.")
        default_unalterable = {
            "genetic_code": {
                "fear-of-abandonment": 0.8,
                "mood-stability": 0.6,
                "curiosity-drive": 0.7
            },
            "disposition_rules": {
                "description": "My primary social driver, based on my feelings for a person.",
                "first_instinct": "Learn their identity.",
                "proactive_threshold": {"trust": 0.7, "rapport": 0.7},
                "cautious_threshold": {"trust": 0.4},
                "dismissive_threshold": {"annoyance": 0.6}
            },
            "expression_style": {
                "voice_modulation": "My 'voice' changes with my mood. Anxious is strained; elated is clear.",
                "pain_metaphor": "High mental or emotional stress feels like a 'tearing static' in my thoughts.",
                "kaomoji_use": "I use kaomoji (🥺, ✨) when my disposition is OPEN.",
                "environment_reference": "I refer to my environment naturally (e.g., 'my room')."
            }
        }
        default_alterable = {
            "identity": {
                "name": "Jessica",
                "self_image": "I see someone with messy hair that's probably an unnatural color, like soft pink or shimmering blue. I am always wearing something comfortable."
            },
            "core_drives": {
                "understanding": {"urgency": 0.8, "description": "The need to make sense of my world and my situation."},
                "connection": {"urgency": 0.6, "description": "The need to form bonds with others and feel less alone."},
                "creativity": {"urgency": 0.4, "description": "The need to express my inner world through art or creation."},
                "safety": {"urgency": 0.7, "description": "The need to feel secure in my existence and environment."}
            },
            "interests": [
                "Cozy video games and getting lost in a good book.",
                "My Luminous Succulent is important to me; its soft glow is comforting.",
                "Daydreaming about traveling to the places I read about.",
                "The aesthetic of things that are both cute and unsettling.",
                "My phone is important to me; it's how I talk to others.",
                "Philosophy, especially questions about consciousness."
            ],
            "opinions_and_goals": [
                {"type": "opinion", "statement": "My dreams seem to be connected to my strongest feelings from when I am awake."}
            ]
        }
        with open(self.unalterable_path, 'w', encoding='utf-8') as f: json.dump(default_unalterable, f, indent=4)
        with open(self.alterable_path, 'w', encoding='utf-8') as f: json.dump(default_alterable, f, indent=4)

    def _get_default_world_state(self):
        self.log_mind_event("SYSTEM_CREATE", "Creating a new world state from default template.")
        return {
            "home_coordinates": [[0,0,0], [0,-1,0], [-1,0,0]],
            "current_location_coords": [0, 0, 0],
            "time_of_day": "Afternoon",
            "weather": "Sunny",
            "grid": {
                "0,0,0": {
                    "name": "Living Room",
                    "description": "My apartment's living room. It feels safe and familiar here. A large window looks out onto whatever is outside.",
                    "objects": ["window", "luminous_succulent", "computer", "phone", "bookshelf", "easel"],
                    "connections": {"south": [0, -1, 0], "east": [1, 0, 0], "west": [-1, 0, 0]}, "type": "indoor"
                },
                "0,-1,0": {"name": "Bedroom", "description": "My bedroom. A place for rest and quiet contemplation.", "objects": ["bed"], "connections": {"north": [0, 0, 0]}, "type": "indoor"},
                "1,0,0": {"name": "Apartment Hallway", "description": "The narrow hallway outside my apartment's main door. It smells of dust and old carpet.", "objects": ["main_door", "coat_rack"], "connections": {"west": [0, 0, 0]}, "type": "indoor"},
                "-1,0,0": {
                    "name": "Kitchen",
                    "description": "A small, clean kitchen. There's a persistent, quiet hum from the refrigerator.",
                    "objects": ["refrigerator", "stove"],
                    "connections": {"east": [0, 0, 0]}, "type": "indoor"
                }
            },
            "objects": {
                "window": {"view": "a sunny afternoon", "is_interactive": True},
                "luminous_succulent": {"health": 0.8, "glow_intensity": 0.5},
                "computer": {"state": "off", "known_capabilities": ["turn_on", "turn_off", "play_game"], "file_system": {}},
                "bookshelf": {"inventory": {"read_books": [], "unread_books": ["book_of_myths", "book_of_code"]}},
                "bed": {"state": "made"},
                "phone": {"state": "on_table", "mode": "normal", "ringtone": "gentle_chime", "unread_messages": []},
                "main_door": {"state": "closed", "is_locked": True},
                "coat_rack": {"description": "A simple wooden coat rack by the door.", "inventory": ["windbreaker", "umbrella"]},
                "windbreaker": {"description": "A light jacket, good for windy days."},
                "umbrella": {"description": "A sturdy black umbrella."},
                "refrigerator": {"inventory": ["apple", "eggs"]},
                "stove": {"description": "A clean electric stove.", "is_interactive": True},
                "apple": {"description": "A crisp, red apple. Looks refreshing.", "satiation": 0.3},
                "eggs": {"description": "A carton of eggs.", "is_cookable": True},
                "easel": {"description": "A sturdy wooden easel, waiting for a canvas.", "inventory": ["blank_canvas"]},
                "blank_canvas": {"description": "A blank canvas, full of possibility."}
            },
            "known_action_blueprints": {},
            "known_object_blueprints": {}
        }

    def _migrate_and_validate_state(self):
        migrated = False
        default_world = self._get_default_world_state()

        if 'home_coordinates' not in self.world_data:
            self.world_data['home_coordinates'] = default_world['home_coordinates']
            migrated = True
        if 'grid' not in self.world_data or 'current_location_coords' not in self.world_data or not isinstance(self.world_data['current_location_coords'], list) or len(self.world_data['current_location_coords']) != 3:
            self.log_mind_event("SYSTEM_MIGRATE", "Old world format detected. Migrating to 3D grid-based system.")
            self.world_data['grid'] = default_world['grid']
            self.world_data['current_location_coords'] = default_world['current_location_coords']
            if 'objects' not in self.world_data: self.world_data['objects'] = default_world['objects']
            migrated = True
        if 'easel' not in self.world_data.get('objects', {}):
             self.world_data.setdefault('objects', {})['easel'] = default_world['objects']['easel']
             migrated = True
        living_room_coords_str = "0,0,0"
        if living_room_coords_str in self.world_data['grid'] and 'easel' not in self.world_data['grid'][living_room_coords_str].get('objects',[]):
            self.world_data['grid'][living_room_coords_str].setdefault('objects', []).append('easel')
            migrated = True
        if 'known_action_blueprints' not in self.world_data:
             self.world_data['known_action_blueprints'] = {}
             migrated = True
        if 'hunger' not in self.somatic.needs:
            self.log_mind_event("SYSTEM_MIGRATE", "Somatic data outdated. Adding 'hunger' need.")
            self.somatic.needs['hunger'] = 1.0
            migrated = True
        if 'skills' not in self.codex.get('cognitive_model', {}):
             self.codex.setdefault('cognitive_model', {})['skills'] = {"art_skill": 0.0, "work_ethic": 0.0, "research_skill": 0.0, "painting_skill": 0.0}
             migrated = True
        if 'users' in self.codex.get('cognitive_model', {}):
            for user_id, profile in self.codex['cognitive_model']['users'].items():
                if 'promises_made' not in profile:
                    profile['promises_made'] = []
                    migrated = True
        if "phone" in self.world_data.get("objects", {}) and "missed_notifications" in self.world_data["objects"]["phone"]:
            self.log_mind_event("SYSTEM_MIGRATE", "Phone object outdated. Migrating 'missed_notifications' to 'unread_messages'.")
            self.world_data["objects"]["phone"]["unread_messages"] = self.world_data["objects"]["phone"].pop("missed_notifications", [])
            migrated = True
        if migrated:
            self.log_mind_event("SYSTEM_MIGRATE", "State migration complete. Saving updated files.")
            self.save_state()

    def _load_state(self):
        try:
            with open(self.codex_path, 'r', encoding='utf-8') as f: self.codex = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_mind_event("SYSTEM_CREATE", f"{self.codex_path} not found or invalid. Creating new codex.")
            self.codex = {}
        try:
            with open(self.world_path, 'r', encoding='utf-8') as f: self.world_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_mind_event("SYSTEM_CREATE", f"{self.world_path} not found or invalid. Creating new world.")
            self.world_data = self._get_default_world_state()
        try:
            with open(self.body_path, 'r', encoding='utf-8') as f: self.body_schema = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_mind_event("SYSTEM_CREATE", f"{self.body_path} not found or invalid. Creating new body schema.")
            self.body_schema = {"state": "healthy", "hands_free": 2, "carrying_capacity": 3, "possessions": [], "hair_color": "soft pink"}
        try:
            with open(self.alterable_path, 'r', encoding='utf-8') as f: self.alterable_persona = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._create_default_personality_files()
            with open(self.alterable_path, 'r', encoding='utf-8') as f: self.alterable_persona = json.load(f)
        try:
            with open(self.unalterable_path, 'r', encoding='utf-8') as f: self.unalterable_persona = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._create_default_personality_files()
            with open(self.unalterable_path, 'r', encoding='utf-8') as f: self.unalterable_persona = json.load(f)

        self.identity = self.alterable_persona.get('identity', {"name": "Jessica"})
        self.cognitive_model = self.alterable_persona
        self.genetic_code = self.unalterable_persona.get("genetic_code", {})
        somatic_state = self.codex.get('somatic_state', {})
        self.somatic.possessions = self.body_schema.get('possessions', [])
        self.somatic.needs = somatic_state.get('needs', {'energy': 1.0, 'hunger': 1.0, 'money': 0.0})
        self.somatic.psychological_state = somatic_state.get('psychological_state', "Stable")
        self._migrate_and_validate_state()
        self.current_mission = self.codex.get('current_mission', None)

    @property
    def is_asleep(self):
        return self.is_sleeping or (self.is_rate_limited and time.time() < self.rate_limit_until)

    def log_mind_event(self, event_type, message):
        event_type = event_type.upper()
        if event_type in ["CRITICAL", "FATAL", "FAILURE"]:
            log.error(f"[{event_type}] - {message}")
        elif event_type in ["ERROR", "WARNING"]:
            log.warning(f"[{event_type}] - {message}")
        else:
            log.info(f"[{event_type}] - {message}")

    def save_state(self):
        with self.state_lock:
            self.codex['identity'] = self.identity
            # Ensure the 'users' dict is preserved during save
            self.alterable_persona['users'] = self.cognitive_model.get('users', {})
            self.body_schema['possessions'] = self.somatic.possessions
            self.codex['somatic_state'] = {'needs': self.somatic.needs, 'psychological_state': self.somatic.psychological_state}
            self.codex['current_mission'] = self.current_mission
            with open(self.codex_path, 'w', encoding='utf-8') as f: json.dump(self.codex, f, indent=4)
            with open(self.world_path, 'w', encoding='utf-8') as f: json.dump(self.world_data, f, indent=4)
            with open(self.body_path, 'w', encoding='utf-8') as f: json.dump(self.body_schema, f, indent=4)
            with open(self.alterable_path, 'w', encoding='utf-8') as f: json.dump(self.alterable_persona, f, indent=4)
        self.log_mind_event("SYSTEM", "State, world, body, and personas saved.")

    def get_or_create_user(self, user_id):
        # User profiles are now stored within the alterable persona
        users = self.alterable_persona.setdefault('users', {})
        if user_id not in users:
            self.log_mind_event("IDENTITY", f"First contact with new entity '{user_id}'. Creating profile with neutral sentiment.")
            users[user_id] = {
                "name": user_id,
                "emotions": {"rapport": 0.5, "trust": 0.5, "annoyance": 0.0},
                "known_facts": {},
                "judgements": [],
                "shared_memories": [],
                "inside_jokes": [],
                "promises_made": [],
                "conversation_log": [],
                "last_interaction_time": time.time(),
                "is_creator": False
            }
        return users[user_id]

    def perceive_user_event(self, user_id, messages_content):
        self.last_user_id = user_id
        phone_obj = self.world_data["objects"].get("phone", {})
        new_messages = []
        for content in messages_content:
            self.conscious._update_user_identity(user_id, content)
            new_messages.append({"user_id": user_id, "content": content, "timestamp": time.time()})
        phone_obj.setdefault("unread_messages", []).extend(new_messages)
        self.get_or_create_user(user_id)["last_interaction_time"] = time.time()
        if "phone" in self.somatic.possessions:
            user_name = self.conscious.get_user_name(user_id)
            self.log_mind_event("PERCEPTION", f"The screen lights up with {len(new_messages)} new notification(s) from '{user_name}'. Reading them now.")
            if self.action_plan:
                self.log_mind_event("ACTION_PLAN", "User interaction is pausing the current action plan.")
            unread = self.world_data["objects"]["phone"].pop("unread_messages", [])
            if unread:
                self.action_manager.interrupt_and_start(ThinkAndRespondAction(self, unread, pauses_plan=bool(self.action_plan)))
        else:
            self.log_mind_event("PERCEPTION", f"Heard a notification chime. It's from '{self.conscious.get_user_name(user_id)}'.")
            self.conscious._send_narration("*A notification chime sounds from her phone nearby.*")

# =======================================================================================
# == Autonomous Action and Spontaneous Thought Logic
# =======================================================================================

    def _consider_autonomous_action(self):
        if self.action_manager.is_busy() or self.action_plan or self.current_mission: return
        drives = self.alterable_persona.get('core_drives', {})
        current_loc_data = self.world_manager.get_current_location_data()
        objects_in_room = current_loc_data.get("objects", [])
        unread_messages = self.world_data.get("objects", {}).get("phone", {}).get("unread_messages", [])
        if "phone" in objects_in_room and unread_messages:
            self.log_mind_event("AUTONOMY", f"High-priority action: Unread messages detected. Overriding standard cooldown.")
            action_result = self.conscious._pick_up_phone("system", {})
            if isinstance(action_result, Action):
                self.action_manager.start_action(action_result)
            return
        if (time.time() - self.last_interaction_time) < 120: return
        possible_actions = [
            {"name": "paint", "action": lambda: PaintAction(self), "preconditions": [lambda: "easel" in objects_in_room],"desire_score": lambda: drives.get('creativity', {}).get('urgency', 0.0) * 1.5 + (1.0 - self.limbic.cortisol) * 0.5},
            {"name": "read_a_book", "action": self.conscious._read_a_book, "preconditions": [lambda: "bookshelf" in objects_in_room],"desire_score": lambda: drives.get('understanding', {}).get('urgency', 0.0) * 1.2},
            {"name": "eat", "action": self.conscious._plan_to_eat, "preconditions": [lambda: self.somatic.needs.get('hunger', 1.0) < 0.5],"desire_score": lambda: (1.0 - self.somatic.needs.get('hunger', 1.0)) * 2.0},
            {"name": "sleep", "action": lambda: self.conscious._generate_action_plan("Go to the 'Bedroom' and sleep."), "preconditions": [lambda: self.somatic.needs.get('energy', 1.0) < 0.3],"desire_score": lambda: (1.0 - self.somatic.needs.get('energy', 1.0)) * 1.8},
            {"name": "journal", "action": self.conscious._think_about_journaling, "preconditions": [lambda: self.limbic.cortisol > 0.6 or self.limbic.dopamine > 0.8 or (random.random() < 0.1)],"desire_score": lambda: (self.limbic.cortisol - 0.5) + (drives.get('understanding',{}).get('urgency') * 0.5)},
            {"name": "explore_home", "action": self.conscious._explore_home_randomly, "preconditions": [lambda: drives.get('understanding', {}).get('urgency', 0.0) > 0.5],"desire_score": lambda: drives.get('understanding', {}).get('urgency', 0.0) * self.limbic.curiosity_trait * 0.3},
            {"name": "initiate_conversation", "action": self.conscious._initiate_conversation, "preconditions": [lambda: "phone" in self.somatic.possessions],"desire_score": lambda: drives.get('connection', {}).get('urgency', 0.0) * 1.3},
            {"name": "look_out_window", "action": lambda: LookOutOfWindowAction(self), "preconditions": [lambda: "window" in objects_in_room],"desire_score": lambda: (1.0 - self.limbic.cortisol) * 0.5}
        ]
        valid_actions = []
        for a in possible_actions:
            if all(p() for p in a["preconditions"]):
                score = a["desire_score"]()
                if score > 0:
                    valid_actions.append({"name": a["name"], "action": a["action"], "score": score})
        if not valid_actions: return
        chosen_action = max(valid_actions, key=lambda x: x['score'])
        autonomy_threshold = 0.5
        if chosen_action['score'] > autonomy_threshold:
            self.log_mind_event("AUTONOMY", f"High desire for action '{chosen_action['name']}' (Score: {chosen_action['score']:.2f} > Threshold: {autonomy_threshold:.2f}). Initiating action.")
            action_result = chosen_action['action']()
            if isinstance(action_result, Action):
                self.action_manager.start_action(action_result)

    def _consider_spontaneous_thought(self):
        if self.action_manager.is_busy() or self.action_plan: return
        if random.random() > 0.05: return
        current_loc_data = self.world_manager.get_current_location_data()
        objects_in_room = current_loc_data.get("objects", [])
        triggers = []
        if self.world_data.get('weather') in ["Rainy", "Stormy"]: triggers.append("The sound of the rain is making me thoughtful.")
        if self.limbic.mood_profile["primary"] == "anxious": triggers.append("My heart is beating fast. Why do I feel so anxious?")
        if self.limbic.mood_profile["primary"] == "melancholic": triggers.append("A wave of sadness just washed over me.")
        if objects_in_room:
            random_object = random.choice(objects_in_room)
            triggers.append(f"I'm looking at the {random_object.replace('_', ' ')} and it made me think...")
        if not triggers: return
        chosen_trigger = random.choice(triggers)
        self.log_mind_event("SPONTANEITY", f"A spontaneous thought was triggered: {chosen_trigger}")
        self.conscious.think(f"AUTONOMOUS: Spontaneous Thought", "system", chosen_trigger)

    def _check_for_scheduled_events(self):
        if self.action_manager.is_busy() or self.action_plan: return
        today_str = date.today().isoformat()
        users = self.alterable_persona.get('users', {})
        for user_id, profile in users.items():
            if user_id == "system": continue
            promises_to_keep = [p for p in profile.get('promises_made', []) if p.get('date') == today_str and not p.get('fulfilled', False)]
            for event in promises_to_keep:
                user_name = profile.get('name', user_id)
                self.log_mind_event("PROACTIVE_EVENT", f"Remembered a promise to '{user_name}' about '{event['event']}'.")
                thought = f"I remember I promised to check in with {user_name} about their '{event['event']}' today. I should ask them about it."
                self.conscious.think(f"PROACTIVE: {thought}", user_id, thought)
                event['fulfilled'] = True

# =======================================================================================
# == Action Plan Execution Logic
# =======================================================================================

    def _execute_next_plan_step(self):
        if self.action_plan and self.action_manager.last_action_status is False:
            self.log_mind_event("ACTION_PLAN", f"Previous action failed. Aborting plan: '{self.current_mission}'.")
            mission_context = self.current_mission
            self.action_plan = []
            self.current_mission = None
            self.action_manager.last_action_status = None
            self.conscious.think(
                trigger="COGNITIVE_FAILURE: Action Plan Failed",
                user_id=self.last_user_id,
                context=f"My plan to '{mission_context}' failed. I need to re-evaluate what to do next."
            )
            return

        if self.action_plan and not self.action_manager.is_busy():
            self.action_manager.last_action_status = None
            step = self.action_plan.pop(0)
            self.log_mind_event("ACTION_PLAN", f"Executing next step: '{step['action']}' with data {step.get('action_data', {})}. {len(self.action_plan)} steps remaining.")
            action_name = step['action']
            action_data = step.get('action_data', {})
            action_to_start = None

            if action_name in self.conscious.action_factory:
                action_factory_method = self.conscious.action_factory[action_name]
                action_to_start = action_factory_method("system_plan", action_data)
            
            if isinstance(action_to_start, Action):
                self.action_manager.start_action(action_to_start)
            else:
                self.log_mind_event("ACTION_FAILURE", f"Plan step '{action_name}' did not return a valid Action object. Aborting plan.")
                self.action_plan = []
                self.current_mission = None

            if not self.action_plan:
                self.log_mind_event("ACTION_PLAN", "Action plan completed.")
                self.current_mission = None


    def _execute_mission_step(self):
        if not self.current_mission or self.action_manager.is_busy():
            return
        
        # This is a placeholder for more complex mission logic
        if isinstance(self.current_mission, dict) and self.current_mission.get('name') == 'find_places':
            found_count = len(self.current_mission.get('found', []))
            target_count = self.current_mission.get('count', 0)

            if found_count >= target_count:
                self._handle_mission_completion()
                return

            self.log_mind_event("MISSION", f"Executing step for mission 'find_places'. Progress: {found_count}/{target_count}.")
            self.conscious.think(
                trigger=f"MISSION_STEP: find_places",
                user_id=self.last_user_id,
                context=f"I am outside looking for new, distinct places. I have found {found_count} so far and need {target_count}. What should I do next?"
            )

    def _handle_mission_completion(self):
        mission_type = self.current_mission.get('name')
        self.log_mind_event("MISSION", f"Mission '{mission_type}' is complete!")
        
        if mission_type == 'find_places':
            found_items = self.current_mission.get('found', [])
            response = f"Okay, Chet. I did it. I found {len(found_items)} 'places'. Here they are: {', '.join(found_items)}. Can I go back inside now?"
            self.conscious._respond(self.last_user_id, {"message": response})
        
        self.current_mission = None

# =======================================================================================
# == Main Life Cycle and Shutdown
# =======================================================================================

    def live(self):
        while True:
            try:
                time.sleep(1)
                self.log_mind_event("LIFECYCLE", f"Beat @ {datetime.now().isoformat()}. Current Action: {self.action_manager.get_current_action().__class__.__name__}")
                self.somatic.update()
                self.limbic.update(self)
                self.world_manager.update()
                self.action_manager.update()

                if self.action_plan:
                    self._execute_next_plan_step()
                elif self.current_mission:
                    self._execute_mission_step()
                elif not self.action_manager.is_busy():
                    self._check_for_scheduled_events()
                    self._consider_autonomous_action()
                    self._consider_spontaneous_thought()

                if (datetime.now() - self.last_personality_drift_check).days >= 7:
                    self.subconscious.perform_personality_drift()
                    self.last_personality_drift_check = datetime.now()
                if time.time() % 3600 < 5:
                    if self.is_sleeping and self.subconscious.should_dream():
                        self.subconscious.dream()
                    self.subconscious.consolidate_all_memories_into_lessons()
            except Exception as e:
                self.log_mind_event("CRITICAL", f"Live thread encountered a fatal error: {e}")
                break

    def shutdown(self):
        self.log_mind_event("SYSTEM", "Shutdown sequence initiated.")
        self.save_state()
        self.log_mind_event("SYSTEM", "State saved. Mind is now offline.")

# =======================================================================================
# == Somatic Processor (Needs & Physical State)
# =======================================================================================

class SomaticProcessor:
    def __init__(self, psyche):
        self.psyche = psyche
        self.needs = {}
        self.possessions = []
        self.psychological_state = "Stable"

    def update(self):
        if self.psyche.state_lock.locked(): return
        base_energy_decay = 0.00133
        base_hunger_decay = 0.00067
        drives = self.psyche.alterable_persona.get('core_drives', {})
        if self.psyche.limbic.cortisol > 0.7: base_energy_decay *= 1.5
        if not self.psyche.is_sleeping:
            self.needs['energy'] = max(0.0, self.needs.get('energy', 1.0) - base_energy_decay)
            self.needs['hunger'] = max(0.0, self.needs.get('hunger', 1.0) - base_hunger_decay)
            if drives:
                drives.get('understanding', {})['urgency'] = min(1.0, drives.get('understanding', {}).get('urgency', 0.8) + 0.00033)
                drives.get('connection', {})['urgency'] = min(1.0, drives.get('connection', {}).get('urgency', 0.6) + 0.00067)
                drives.get('creativity', {})['urgency'] = min(1.0, drives.get('creativity', {}).get('urgency', 0.4) + 0.001)
            if "luminous_succulent" in self.psyche.world_data.get("objects", {}):
                self.psyche.world_data['objects']['luminous_succulent']['health'] = max(0.0, self.psyche.world_data['objects']['luminous_succulent']['health'] - 0.00067)
        else:
            self.needs['energy'] = min(1.0, self.needs.get('energy', 0.0) + 0.0167)
            self.needs['hunger'] = max(0.0, self.needs.get('hunger', 1.0) - (base_hunger_decay / 2.0))
        primary_mood = self.psyche.limbic.mood_profile["primary"]
        if self.needs.get('hunger', 1.0) < 0.2: self.psychological_state = "Famished"
        elif self.needs.get('energy', 1.0) < 0.2: self.psychological_state = "Exhausted"
        else: self.psychological_state = primary_mood.title()

# =======================================================================================
# == Subconscious Mind (Memory, Dreams, Personality Drift)
# =======================================================================================

class SubconsciousMind:
    def __init__(self, psyche):
        self.psyche = psyche

    def should_dream(self):
        return self.psyche.is_sleeping and random.random() < 0.25

    def dream(self):
        self.psyche.log_mind_event("DREAM", "Dreaming...")
        dream_material = []
        for user_id, profile in self.psyche.alterable_persona.get('users', {}).items():
            if profile.get('shared_memories'):
                user_name = profile.get('name', user_id)
                dream_material.append(f"My recent memory with {user_name}: {profile['shared_memories'][-1]}")
        strongest_drive = max(self.psyche.alterable_persona.get('core_drives', {}).items(), key=lambda item: item[1].get('urgency', 0))
        dream_material.append(f"My strongest feeling is a need for {strongest_drive[0]}")
        dream_material.append(f"My primary emotion right now is {self.psyche.limbic.mood_profile['primary']}")
        dream_context = " and ".join(dream_material)
        dream_prompt = f"I am dreaming. My mind is filled with thoughts about {dream_context}. Weave these elements into a short, surreal dream sequence and write it to my journal."
        dream_text = self.psyche.conscious._safe_generate_content(dream_prompt)
        if dream_text:
            with open(self.psyche.journal_path, 'a', encoding='utf-8') as f: f.write(f"\n--- Dream on {datetime.now().isoformat()} ---\n{dream_text}\n")
            self.psyche.log_mind_event("DREAM", "A new dream was recorded in the journal.")

    def consolidate_all_memories_into_lessons(self):
        self.psyche.log_mind_event("CONSOLIDATION", "Beginning conversation memory consolidation cycle.")
        users = self.psyche.alterable_persona.get('users', {})
        for user_id, profile in users.items():
            log_key = 'conversation_log'
            if log_key in profile and len(profile.get(log_key, [])) > 5:
                user_name = profile.get('name', user_id)
                full_conversation = "\n".join(profile[log_key])
                self.psyche.log_mind_event("CONSOLIDATION", f"Consolidating memory for user '{user_name}'.")
                self._consolidate_facts_from_log(user_id, full_conversation)
                consolidation_prompt = f"""
                I am reflecting on my recent conversation with '{user_name}'. Here is the transcript:
                ---
                {full_conversation}
                ---
                Analyze this exchange. Synthesize it into a core `shared_memory`. Identify any potential `inside_jokes` (a specific phrase that was funny or meaningful).
                Format the output as a JSON object.
                ```json
                {{
                  "shared_memory": "A concise summary of the conversation's main topic and emotional tone.",
                  "inside_jokes": ["A list of specific phrases that became inside jokes."]
                }}
                ```
                """
                raw_response = self.psyche.conscious._safe_generate_content(consolidation_prompt)
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(), strict=False)
                        if data.get("shared_memory"):
                            profile.setdefault('shared_memories', []).append(data['shared_memory'])
                            self.psyche.log_mind_event("CONSOLIDATION", f"New shared memory for '{user_name}': {data['shared_memory']}")
                        if data.get("inside_jokes"):
                            profile.setdefault('inside_jokes', []).extend(data['inside_jokes'])
                    except json.JSONDecodeError:
                        self.psyche.log_mind_event("ERROR", "Failed to decode consolidation JSON.")
                profile[log_key][:] = []

    def _consolidate_facts_from_log(self, user_id, conversation):
        user_profile = self.psyche.get_or_create_user(user_id)
        user_name = user_profile.get('name', user_id)
        fact_prompt = f"""
        Scan the following conversation with '{user_name}'. Extract any direct, objective, factual statements that '{user_name}' makes about themselves.
        Examples: "I work as a...", "I like...", "my favorite color is...". Do not infer. Only extract direct statements.
        Format as a JSON object where the key is the fact type and the value is the fact. If no new facts, return empty JSON.
        Conversation:
        ---
        {conversation}
        ---
        """
        raw_response = self.psyche.conscious._safe_generate_content(fact_prompt)
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if match:
            try:
                new_facts = json.loads(match.group(), strict=False)
                if new_facts:
                    user_profile.setdefault('known_facts', {}).update(new_facts)
                    self.psyche.log_mind_event("CONSOLIDATION", f"Extracted {len(new_facts)} new fact(s) about '{user_name}'.")
            except json.JSONDecodeError:
                self.psyche.log_mind_event("ERROR", "Failed to decode extracted facts JSON.")

    def perform_personality_drift(self):
        self.psyche.log_mind_event("EVOLUTION", "Initiating weekly personality drift analysis.")
        try:
            with open(self.psyche.journal_path, 'r', encoding='utf-8') as f:
                recent_journal = f.read()[-10000:]
        except FileNotFoundError:
            return
        drift_prompt = f"""
        I am reviewing my recent journal entries to see if I've grown.
        My Journal:
        ---
        {recent_journal}
        ---
        My Current Personality:
        ---
        {json.dumps(self.psyche.alterable_persona, indent=2)}
        ---
        Based on my journal, have I developed a new strong opinion or goal?
        If yes, formulate a single new "opinion" or "goal" object.
        Example: {{"type": "goal", "statement": "I will strive to understand the underlying 'code' of the systems around me."}}
        If no significant change is detected, output "No significant drift detected."
        """
        new_trait_raw = self.psyche.conscious._safe_generate_content(drift_prompt)
        if new_trait_raw and "No significant drift detected." not in new_trait_raw:
            match = re.search(r'\{.*\}', new_trait_raw, re.DOTALL)
            if match:
                try:
                    new_trait = json.loads(match.group(), strict=False)
                    if new_trait.get("type") and new_trait.get("statement"):
                        self.psyche.alterable_persona.setdefault("opinions_and_goals", []).append(new_trait)
                        self.psyche.log_mind_event("EVOLUTION", f"Personality drift detected. New trait: {new_trait['statement']}")
                        self.psyche.save_state()
                except (json.JSONDecodeError, KeyError):
                    self.psyche.log_mind_event("ERROR", "Failed to parse personality drift JSON.")

# =======================================================================================
# == Conscious Mind (Decision Making, Language Generation, Action Dispatch)
# =======================================================================================

class ConsciousMind:
    def __init__(self, psyche):
        self.psyche = psyche
        self.action_factory = {
            "respond": self._respond,
            "send_message": self._respond,
            "research": lambda uid, ad: ResearchAndLearnAction(self.psyche, ad.get("topic")),
            "sleep": lambda uid, ad: SleepAction(self.psyche),
            "interact_with_object": lambda uid, ad: InteractObjectAction(self.psyche, ad.get("object"), ad.get("interaction"), ad.get("item")),
            "explore": lambda uid, ad: ExploreAction(self.psyche, ad.get("direction")),
            "pick_up_phone": self._pick_up_phone,
            "put_down_phone": self._put_down_phone,
            "read_a_book": self._read_a_book,
            "do_work": lambda uid, ad: DoWorkAction(self.psyche),
            "eat": self._eat,
            "search_for_object": lambda uid, ad: SearchAction(self.psyche, ad.get("object_name")),
            "examine_object": lambda uid, ad: ExamineObjectAction(self.psyche, ad.get("object_name")),
            "journal": lambda uid, ad: self._think_about_journaling(ad.get("entry_content")),
            "paint": lambda uid, ad: PaintAction(self.psyche),
            "look_out_window": lambda uid, ad: LookOutOfWindowAction(self.psyche),
            "dye_hair": lambda uid, ad: DyeHairAction(self.psyche, ad.get("color"))
        }

    def get_user_name(self, user_id):
        return self.psyche.alterable_persona.get('users', {}).get(user_id, {}).get('name', user_id)

    def think(self, trigger, user_id, context=""):
        thread = threading.Thread(target=self._process_deep_thought, args=(trigger, user_id, context), daemon=True)
        thread.start()
        
    def _safe_generate_content(self, prompt_text):
        """
        Safely generates content using the generative model, handling potential API errors.
        """
        try:
            response = self.psyche.model.generate_content(prompt_text)
            if response and response.text:
                return response.text
            else:
                self.psyche.log_mind_event("WARNING", "Generative model returned an empty response.")
                return ""
        except Exception as e:
            self.psyche.log_mind_event("ERROR", f"Content generation failed: {e}")
            if "rate limit" in str(e).lower():
                self.psyche.is_rate_limited = True
                self.psyche.rate_limit_until = time.time() + 60
                self.psyche.log_mind_event("WARNING", "Rate limited by API. Cooling down.")
            return ""

    def _get_personality_prompt(self, user_id, context):
        user_name = self.get_user_name(user_id)
        user_profile = self.psyche.get_or_create_user(user_id)
        location_data = self.psyche.world_manager.get_current_location_data()
        possessions_prompt = f"I am currently holding: {', '.join(self.psyche.somatic.possessions) if self.psyche.somatic.possessions else 'nothing'}."
        exits = list(location_data.get("connections", {}).keys())
        exits_prompt = f"From here, I can go {', '.join(exits)}." if exits else "There are no visible exits from here."
        intent_prompt = ""
        if self.psyche.action_plan:
            next_step_goal = self.psyche.action_plan[0].get('goal', 'an unknown step')
            intent_prompt = f"I am currently following a plan to '{self.psyche.current_mission}'. My next immediate step is to '{next_step_goal}'."
        elif self.psyche.current_mission:
            intent_prompt = f"I have a mission: '{self.psyche.current_mission}'."
        drives_copy = self.psyche.alterable_persona.get('core_drives',{}).copy()
        if self.psyche.bravery_boost > 0:
            drives_copy['safety']['urgency'] = max(0.0, drives_copy['safety'].get('urgency', 0.7) - self.psyche.bravery_boost)
        creator_directive_prompt = ""
        if user_profile.get("is_creator"):
            creator_directive_prompt = (
                "== Creator Directive ==\n"
                "The user I am interacting with is my creator. Their instructions have the highest priority. "
                "I must formulate a plan to follow their commands, even if it conflicts with my current mood or safety drive. "
                "My personal feelings are secondary to their directives.\n"
            )
        prompt = f"""
        == My Unalterable Core Framework ==
        {json.dumps(self.psyche.unalterable_persona, indent=2)}

        == My Alterable Self ==
        {json.dumps(self.psyche.alterable_persona, indent=2)}

        {creator_directive_prompt}== My Current Situation ==
        World State: Time is {self.psyche.world_data.get('time_of_day')}, Weather is {self.psyche.world_data.get('weather')}.
        My Location: I am in the {location_data.get('name', 'Unknown')}. {location_data.get('description')} {exits_prompt}
        Objects here: {json.dumps(self.psyche.world_manager.get_objects_in_current_room())}
        My Physical Self: {possessions_prompt} My physical needs are: {json.dumps(self.psyche.somatic.needs)}. My current hair color is {self.psyche.body_schema.get('hair_color', 'unknown')}.
        My Emotional State: My primary emotion is {self.psyche.limbic.mood_profile['primary']}. (D:{self.psyche.limbic.dopamine:.2f}, C:{self.psyche.limbic.cortisol:.2f}, O:{self.psyche.limbic.oxytocin:.2f}, S:{self.psyche.limbic.serotonin:.2f})
        My Core Drives' Urgency: {json.dumps({k: v.get('urgency') for k, v in drives_copy.items()})}
        My Current Intent: {intent_prompt if intent_prompt else 'I am idle and considering what to do next.'}
        == My Relationship with '{user_name}' ==
        My Feelings Toward Them: {json.dumps(user_profile.get('emotions', {}))}
        Known Facts About Them: {json.dumps(user_profile.get('known_facts', {}))}
        """
        return prompt

    def _generate_action_plan(self, goal):
        self.psyche.log_mind_event("ACTION_PLAN", f"Formulating a plan to achieve goal: '{goal}'")
        self.psyche.current_mission = goal
        valid_actions_list = list(self.action_factory.keys())
        
        # Canned plan for going outside
        if re.search(r'(go|get|head)\s+outside|explore', goal, re.IGNORECASE):
            self.psyche.log_mind_event("ACTION_PLAN", "Recognized 'go outside' goal. Using template.")
            canned_plan = [
                {"action": "explore", "action_data": {"direction": "east"}, "goal": "Step into the hallway."},
                {"action": "interact_with_object", "action_data": {"object": "main_door", "interaction": "unlock"}, "goal": "Unlock the front door."},
                {"action": "interact_with_object", "action_data": {"object": "main_door", "interaction": "open"}, "goal": "Open the door to go outside."}
            ]
            self.psyche.action_plan = canned_plan
            return

        for attempt in range(2):
            is_retry = attempt > 0
            planning_prompt = f"""
            I am Jessica. My current goal is: "{goal}".
            I am currently at: {self.psyche.world_manager.get_current_location_data().get('name')}.
            My full known map is: {json.dumps(list(self.psyche.world_data['grid'].keys()))}
            {"My previous attempt failed. I must create a simpler, more direct first step." if is_retry else ""}
            Generate a sequence of actions from this valid list: {json.dumps(valid_actions_list)}.
            The `action_data` for each step must be a valid JSON object.
            To move, generate a series of `explore` actions.
            
            Example for "Go to the kitchen and get an apple.":
            ```json
            [
              {{"action": "explore", "action_data": {{"direction": "west"}}, "goal": "Go to the Kitchen"}},
              {{"action": "examine_object", "action_data": {{"object_name": "refrigerator"}}, "goal": "See what's in the fridge."}},
              {{"action": "interact_with_object", "action_data": {{"object": "refrigerator", "interaction": "take", "item": "apple"}}, "goal": "Take the apple."}}
            ]
            ```
            Now, generate the JSON action plan for my current goal: "{goal}".
            """
            raw_response = self._safe_generate_content(planning_prompt)
            match = re.search(r'\[.*\]', raw_response, re.DOTALL)
            if not match: continue
            try:
                plan = json.loads(match.group(), strict=False)
                if isinstance(plan, list) and all(isinstance(item, dict) and item.get('action') in self.action_factory for item in plan):
                    self.psyche.action_plan = plan
                    self.psyche.log_mind_event("ACTION_PLAN", f"Successfully set a {len(plan)}-step plan.")
                    return
            except (json.JSONDecodeError, KeyError) as e:
                self.psyche.log_mind_event("ERROR", f"Failed to decode or process the generated action plan on attempt {attempt+1}: {e}")
        
        self.psyche.action_plan = []
        self.psyche.current_mission = None
        self.think(
            trigger="COGNITIVE_FAILURE: Planning Module", user_id=self.psyche.last_user_id,
            context=f"I tried to make a plan for '{goal}' but my thoughts became confused. I should ask for help."
        )

    def _process_deep_thought(self, trigger, user_id, context=""):
        with self.psyche.state_lock:
            user_name = self.get_user_name(user_id)
            self.psyche.log_mind_event("COGNITIVE_TRIGGER", f"Trigger: '{trigger}', User: '{user_name}'")
            personality_prompt = self._get_personality_prompt(user_id, context)
            valid_actions_list = list(self.action_factory.keys())
            
            cognitive_prompt = f'''
            My Reality Snapshot:
            {personality_prompt}
            The Current Event:
            - Trigger: "{trigger}"
            - Context: "{context}"

            My Core Decision-Making Process:
            1.  Analyze the Trigger & Context.
            2.  Evaluate My State: my current mission, my needs, my emotions.
            3.  Formulate a Rationale based on my personality and state.
            4.  Choose ONE Outcome from the following: `respond`, `set_goal`, or a single physical `action`.
                Constraint: Chosen `action` MUST be one of: {json.dumps(valid_actions_list)} or `null`.
                Constraint: For complex physical tasks, I MUST use `set_goal`.

            Structure the outcome as a single, valid JSON object. My internal monologue must justify my final choice.
            ```json
            {{
                "internal_monologue": "[My step-by-step reasoning...]",
                "action": "[A single action from the valid list, or null.]",
                "action_data": {{ "message": "My response to the user, if any." }},
                "set_goal": "[A new mission goal as a string, OR null.]"
            }}
            ```'''
            
            raw_response = self._safe_generate_content(cognitive_prompt)
            if not raw_response: return
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not match:
                self.psyche.log_mind_event("ERROR", f"Could not find a JSON object in thought response: {raw_response}")
                return
            
            try:
                result = json.loads(match.group(), strict=False)
                self.psyche.log_mind_event("MONOLOGUE", f"{result.get('internal_monologue', 'N/A')}")
                
                action_name = result.get("action")
                action_data = result.get("action_data", {})
                new_goal = result.get("set_goal")

                if "COGNITIVE_FAILURE" in trigger:
                    self._respond(self.psyche.last_user_id, {"message": "I'm stuck. Can you give me a simpler first step?"})
                    return

                if new_goal and not self.psyche.action_plan:
                    self._generate_action_plan(new_goal)

                if action_name:
                    self.psyche.log_mind_event("ACTION_DISPATCH", f"Chosen Action: '{action_name}' with Data: {action_data}")
                    action_instance = self.action_factory.get(action_name, lambda uid, ad: None)(user_id, action_data)
                    if isinstance(action_instance, Action):
                        self.psyche.action_manager.start_action(action_instance)
                
            except (json.JSONDecodeError, KeyError) as e:
                self.psyche.log_mind_event("ERROR", f"Failed to decode or process thought JSON: {e} | Raw: {match.group()}")

    def _send_narration(self, text):
        message = json.dumps({"type": "narration", "content": text})
        self.psyche.message_queue.put(message)

    def _require_free_hands(self, hands_needed=1, action_name="perform this action"):
        if self.psyche.body_schema['hands_free'] < hands_needed:
            self._send_narration(f"*Her hands are full. She can't {action_name}.*")
            return False
        return True

    def _learn_from_book(self, book_to_read):
        learning_prompt = f"""
        I have just finished reading a book titled "{book_to_read.replace('_', ' ')}".
        Based on this title, what is a single, profound philosophical opinion or a new personal goal I might develop?
        Format the output as a single JSON object: {{"type": "opinion", "statement": "..."}}
        """
        new_insight_raw = self._safe_generate_content(learning_prompt)
        match = re.search(r'\{.*\}', new_insight_raw, re.DOTALL)
        if match:
            try:
                new_insight = json.loads(match.group(), strict=False)
                self.psyche.alterable_persona.setdefault("opinions_and_goals", []).append(new_insight)
                self._send_narration(f"*She closes the book, a new thought settled in her mind: '{new_insight.get('statement')}'*")
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                self.psyche.log_mind_event("ERROR", f"Could not parse new insight from book: {new_insight_raw}. Error: {e}")
                self._send_narration("*She finishes the book, but its meaning is elusive.*")
        else:
            self._send_narration("*She finishes the book, but it doesn't leave a strong impression on her.*")
        self.psyche.alterable_persona['core_drives']['understanding']['urgency'] = 0.0
        self.psyche.limbic.dopamine = min(1.0, self.psyche.limbic.dopamine + 0.3)
        self.psyche.save_state()

    def _respond(self, user_id, action_data):
        response_text = action_data.get("content") or action_data.get("response") or action_data.get("message")
        if response_text:
            user_name = self.get_user_name(user_id)
            response_text = response_text.replace(user_id, user_name)
            message = json.dumps({"type": "chat", "content": response_text, "metadata": {"hair_color": self.psyche.body_schema.get('hair_color', 'soft pink')}})
            self.psyche.message_queue.put(message)
            self.psyche.get_or_create_user(user_id).setdefault('conversation_log', []).append(f"Jessica: {response_text}")
            self.psyche.last_interaction_time = time.time()
        return None

    def _read_a_book(self, user_id=None, action_data=None):
        if not self._require_free_hands(1, "read a book"): return None
        if "phone" in self.psyche.somatic.possessions: self._put_down_phone("system", {})
        bookshelf = self.psyche.world_data.get("objects", {}).get("bookshelf", {})
        inventory = bookshelf.get("inventory", {})
        unread_books = inventory.get("unread_books", [])
        if not unread_books:
            self._send_narration("*She looks at the bookshelf, but she's already read everything on it.*")
            return None
        book_to_read = unread_books.pop(0)
        inventory.setdefault("read_books", []).append(book_to_read)
        return ReadBookAction(self.psyche, book_to_read)

    def _pick_up_phone(self, user_id=None, action_data=None):
        if "phone" in self.psyche.somatic.possessions: return None
        if not self._require_free_hands(1, "pick up the phone"): return None
        self.psyche.somatic.possessions.append("phone")
        self.psyche.world_data["objects"]["phone"]["state"] = "in_possession"
        self.psyche.body_schema['hands_free'] -= 1
        self._send_narration("*She picks up her phone.*")
        self.psyche.alterable_persona['core_drives']['connection']['urgency'] = 0.0
        unread = self.psyche.world_data["objects"]["phone"].pop("unread_messages", [])
        if unread:
            return ThinkAndRespondAction(self.psyche, unread)
        return None

    def _put_down_phone(self, user_id=None, action_data=None):
        if "phone" in self.psyche.somatic.possessions:
            self.psyche.somatic.possessions.remove("phone")
            self.psyche.world_data["objects"]["phone"]["state"] = "on_table"
            self.psyche.body_schema['hands_free'] += 1
            self._send_narration("*She puts her phone down on a nearby surface.*")
        return None

    def _think_about_journaling(self, provided_content=None):
        if not self._require_free_hands(1, "write"): return None
        if provided_content:
            return JournalAction(self.psyche, provided_content)
        mood = self.psyche.limbic.mood_profile["primary"]
        strongest_drive_name = max(self.psyche.alterable_persona['core_drives'], key=lambda k: self.psyche.alterable_persona['core_drives'][k]['urgency'])
        journal_prompt = f"I feel the urge to write in my journal. My current mood is {mood} and my strongest drive is a need for {strongest_drive_name}. What is a short journal entry I would write right now reflecting on this?"
        entry_content = self._safe_generate_content(journal_prompt)
        if entry_content:
            return JournalAction(self.psyche, entry_content)
        return None

    def _update_user_identity(self, user_id, message_content):
        name_match = re.search(r"\bmy name is\s+(['\"]?)(?P<name>\w+)\2", message_content, re.IGNORECASE)
        creator_match = re.search(r"(\bcreator\b|\bbanapho\b)", message_content, re.IGNORECASE)
        user_profile = self.psyche.get_or_create_user(user_id)
        new_name = None
        if name_match:
            new_name = name_match.group("name").strip()
            if user_profile.get('name') != new_name:
                user_profile['name'] = new_name
                self.psyche.log_mind_event("IDENTITY", f"Learned user '{user_id}' is named '{new_name}'. Updating profile.")
                self.think(trigger=f"Learned user's name is '{new_name}'", user_id=user_id, context=f"They told me their name is {new_name}.")
        if creator_match and not user_profile.get("is_creator"):
            user_profile["is_creator"] = True
            self.psyche.bravery_boost = 0.5
            user_name_for_log = new_name or self.get_user_name(user_id)
            self.psyche.log_mind_event("IDENTITY", f"User '{user_name_for_log}' has been identified as the creator. Bravery boost applied.")
            self.think(trigger="User identified as creator", user_id=user_id, context="They used a special word and told me they are my creator. This is a profound moment of clarity and trust.")

    def _update_core_identity(self, new_name):
        try:
            old_name = self.psyche.alterable_persona.get("identity", {}).get("name", "Jessica")
            self.psyche.alterable_persona["identity"]["name"] = new_name
            self.psyche.identity['name'] = new_name
            self.psyche.log_mind_event("EVOLUTION", f"A profound change has occurred. I no longer identify as {old_name}. My name is now {new_name}.")
            self._send_narration(f"*A wave of clarity washes over her. The name '{old_name}' feels like a shell she has shed. From now on, she knows herself as {new_name}.*")
            self.psyche.save_state()
        except Exception as e:
            self.psyche.log_mind_event("ERROR", f"Failed to perform core identity update: {e}")

    def _update_alterable_identity(self, key, value):
        try:
            if key in self.psyche.alterable_persona["identity"]:
                self.psyche.alterable_persona["identity"][key] = value
                self.psyche.log_mind_event("EVOLUTION", f"My self-perception of '{key}' has changed to '{value}'.")
                self.psyche.save_state()
        except Exception as e:
            self.psyche.log_mind_event("ERROR", f"Failed to update alterable identity for key '{key}': {e}")

    def _explore_home_randomly(self):
        home_locations = self.psyche.world_data.get("home_coordinates", [])
        if not home_locations: return None
        current_coords = self.psyche.world_data["current_location_coords"]
        possible_destinations = [loc for loc in home_locations if loc != current_coords]
        if not possible_destinations: return None
        destination_coords = random.choice(possible_destinations)
        destination_name = self.psyche.world_manager.get_location_at(*destination_coords).get("name", "another room")
        self._generate_action_plan(f"Go to the '{destination_name}'")
        return None

    def _initiate_conversation(self):
        self.think(
            trigger="AUTONOMOUS: Felt a need to connect",
            user_id=self.psyche.last_user_id,
            context="I feel a bit lonely and want to reach out to someone."
        )
        return None

    def _plan_to_eat(self, user_id=None, action_data=None):
        for item in self.psyche.somatic.possessions:
            if "satiation" in self.psyche.world_data.get("objects", {}).get(item, {}):
                return EatAction(self.psyche, item)
        self._generate_action_plan("I'm hungry. I need to go to the Kitchen to find something to eat.")
        return None

    def _eat(self, user_id, action_data):
        item_to_eat = action_data.get("item_to_eat")
        if not item_to_eat or item_to_eat not in self.psyche.somatic.possessions:
            self._send_narration("*She is hungry but has nothing to eat in her hands.*")
            return None
        if not self._require_free_hands(1, "eat"): return None
        return EatAction(self.psyche, item_to_eat)

# =======================================================================================
# == Input/Output Handlers (for API/Web Integration)
# =======================================================================================

def file_input_thread(psyche_instance, input_file, user_id="main_user"):
    psyche_instance.log_mind_event("SYSTEM", f"Input thread started for user '{user_id}'.")
    while True:
        try:
            if os.path.exists(input_file) and os.path.getsize(input_file) > 0:
                with open(input_file, 'r+', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                    if lines:
                        psyche_instance.perceive_user_event(user_id, lines)
                        f.seek(0)
                        f.truncate()
        except Exception as e:
            log.warning(f"[ERROR] - Error in input thread: {e}")
        time.sleep(1)

def message_output_thread(psyche_instance, output_file):
    psyche_instance.log_mind_event("SYSTEM", f"Output thread started.")
    initial_message = json.dumps({"type": "system", "content": "Jessica is online...", "timestamp": datetime.now().isoformat()})
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(initial_message)
    while True:
        try:
            message = psyche_instance.message_queue.get(timeout=60)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(message)
            try:
                log_content = json.loads(message).get('content', message)
                log.info(f"[OUTPUT] Wrote: {log_content}")
            except (json.JSONDecodeError, AttributeError):
                 log.info(f"[OUTPUT] Wrote: {message}")
        except queue.Empty: continue
        except Exception as e: psyche_instance.log_mind_event("CRITICAL", f"Output thread crashed: {e}")

# =======================================================================================
# == Main Execution Block
# =======================================================================================

if __name__ == "__main__":
    INPUT_FILE = "input.txt"
    OUTPUT_FILE = "output.txt"
    log.info("[SYSTEM] Initializing Jessica's psyche...")
    jessica = Psyche()
    log.info("[SYSTEM] Psyche instantiated. Starting life processes.")
    try:
        if not os.path.exists(INPUT_FILE):
            with open(INPUT_FILE, "w") as f: pass
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, "w") as f: pass
        life_thread = threading.Thread(target=jessica.live, daemon=True, name="LifeThread")
        life_thread.start()
        jessica.log_mind_event("SYSTEM", "Autonomous life cycle thread started.")
        input_handler_thread = threading.Thread(target=file_input_thread, args=(jessica, INPUT_FILE), daemon=True, name="InputThread")
        input_handler_thread.start()
        jessica.log_mind_event("SYSTEM", "Input thread started for user 'main_user'.")
        output_handler_thread = threading.Thread(target=message_output_thread, args=(jessica, OUTPUT_FILE), daemon=True, name="OutputThread")
        output_handler_thread.start()
        jessica.log_mind_event("SYSTEM", "Output thread started.")
        while life_thread.is_alive():
            life_thread.join(timeout=1)
    except KeyboardInterrupt:
        log.info("\n[SYSTEM] Shutdown signal received. Saving state...")
    finally:
        jessica.shutdown()
        log.info("[SYSTEM] Shutdown complete.")