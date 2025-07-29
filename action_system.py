import time
import json
import random
import re
from abc import ABC, abstractmethod

class Action(ABC):
    def __init__(self, psyche, duration_beats=1):
        self.psyche = psyche
        self.duration = duration_beats
        self.beats_elapsed = 0
        self.is_finished = False
        self.is_interruptible = True
        self.was_successful = False

    def start(self):
        self.psyche.log_mind_event("ACTION_SYSTEM", f"Starting action: {self.__class__.__name__}")

    def update(self):
        self.beats_elapsed += 1
        if self.beats_elapsed >= self.duration and not self.is_finished:
            self.finish(success=False)

    def finish(self, success=False):
        if self.is_finished: return
        self.was_successful = success
        self.is_finished = True
        event_type = "Finished" if success else "Failed"
        if not (isinstance(self, IdleAction) and not success):
            self.psyche.log_mind_event("ACTION_SYSTEM", f"{event_type} action: {self.__class__.__name__}")

    def on_interrupt(self):
        self.psyche.log_mind_event("ACTION_SYSTEM", f"Action {self.__class__.__name__} was interrupted.")

    def on_resume(self):
        self.psyche.log_mind_event("ACTION_SYSTEM", f"Action {self.__class__.__name__} is being resumed.")

class IdleAction(Action):
    def __init__(self, psyche):
        super().__init__(psyche, duration_beats=1)
        self.is_interruptible = True
    
    def start(self):
        pass

    def update(self):
        if not self.psyche.action_plan and not self.psyche.current_mission:
            self.psyche._check_for_scheduled_events()
            self.psyche._consider_spontaneous_thought()
            self.psyche._consider_autonomous_action()

        super().update()
        if self.is_finished:
             self.is_finished = False
             self.beats_elapsed = 0

class ThinkAndRespondAction(Action):
    def __init__(self, psyche, messages, pauses_plan=False):
        super().__init__(psyche, duration_beats=1)
        self.messages = messages
        self.is_interruptible = False
        self.pauses_plan = pauses_plan

    def start(self):
        super().start()
        self.psyche.conscious._send_narration(f"*She reads the {len(self.messages)} new message(s), her expression thoughtful as she considers a reply...*")
        full_context = []
        user_ids_involved = set()
        for msg in self.messages:
            sender_id = msg['user_id']
            user_ids_involved.add(sender_id)
            user_profile = self.psyche.get_or_create_user(sender_id)
            log_entry = f"{user_profile.get('name', sender_id)}: {msg['content']}"
            user_profile.setdefault('conversation_log', []).append(log_entry)
            full_context.append(log_entry)

        last_message_sender = self.messages[-1]['user_id']
        self.psyche.conscious.think(
            trigger=f"Reading a batch of {len(full_context)} messages from {', '.join(user_ids_involved)}",
            user_id=last_message_sender,
            context="\n".join(full_context)
        )
        self.finish(success=True)

    def finish(self, success=False):
        if self.pauses_plan and self.psyche.action_plan:
            self.psyche.log_mind_event("ACTION_PLAN", "Finished responding to user. Resuming action plan.")
        super().finish(success)

class SleepAction(Action):
    def __init__(self, psyche):
        super().__init__(psyche, duration_beats=8 * 60)
        self.is_interruptible = False

    def start(self):
        super().start()
        self.psyche.is_sleeping = True
        self.psyche.conscious._send_narration("*She decides to rest, her presence slowly fading into stillness...*")

    def update(self):
        if self.psyche.somatic.needs.get('energy', 0) >= 1.0:
            self.finish(success=True)
        super().update()

    def finish(self, success=False):
        self.psyche.is_sleeping = False
        self.psyche.conscious.think("SYSTEM_EVENT", "system", "I feel rested and am waking up now.")
        super().finish(success)

class ExploreAction(Action):
    def __init__(self, psyche, direction):
        super().__init__(psyche, duration_beats=2)
        self.direction = direction

    def start(self):
        super().start()
        if self.direction:
            move_successful = self.psyche.world_manager.move(self.direction)
            self.finish(success=move_successful)
        else:
            self.psyche.conscious._send_narration("*She thinks about exploring, but isn't sure which way to go.*")
            self.psyche.log_mind_event("ACTION_FAILURE", "ExploreAction started with no direction.")
            self.finish(success=False)

class SearchAction(Action):
    def __init__(self, psyche, object_name, search_depth=3):
        super().__init__(psyche, duration_beats=search_depth * 2)
        self.object_name = object_name
        self.search_depth = search_depth
        self.visited_coords = set()
        self.search_queue = []
        self.search_is_outdoors = False

    def start(self):
        super().start()
        initial_coords_tuple = tuple(self.psyche.world_data["current_location_coords"])
        initial_location_data = self.psyche.world_manager.get_location_at(initial_coords_tuple[0], initial_coords_tuple[1], initial_coords_tuple[2])
        if initial_location_data and initial_location_data.get("type") == "outdoor":
            self.search_is_outdoors = True

        self.search_queue.append((initial_coords_tuple, 0))
        self.visited_coords.add(initial_coords_tuple)
        self.psyche.conscious._send_narration(f"*She begins to look around for a {self.object_name.replace('_', ' ')}...*")

    def update(self):
        super().update()
        if self.is_finished:
            if self.search_queue:
                self.psyche.conscious._send_narration(f"*Her search for the {self.object_name.replace('_', ' ')} is taking too long, and she gives up for now.*")
            return

        if not self.search_queue:
            self.psyche.conscious._send_narration(f"*After searching the area, she can't find a {self.object_name.replace('_', ' ')}.*")
            self.finish(success=False)
            return

        current_coords_tuple, depth = self.search_queue.pop(0)

        current_location_data = self.psyche.world_manager.get_location_at(current_coords_tuple[0], current_coords_tuple[1], current_coords_tuple[2])
        if not current_location_data:
             self.psyche.log_mind_event("ACTION_FAILURE", f"Search failed: Invalid coordinates {current_coords_tuple} in queue.")
             return

        self.psyche.world_data["current_location_coords"] = list(current_coords_tuple)
        self.psyche.conscious._send_narration(f"*Her search takes her to the {current_location_data.get('name', 'unknown area')}...*")

        if self.object_name in current_location_data.get("objects", []):
            self.psyche.conscious._send_narration(f"*Success! She has found the {self.object_name.replace('_', ' ')}.*")
            self.finish(success=True)
            return

        if depth < self.search_depth:
            for direction, coords in current_location_data.get("connections", {}).items():
                coords_tuple = tuple(coords)
                if coords_tuple not in self.visited_coords:
                    neighbor_loc = self.psyche.world_manager.get_location_at(coords[0], coords[1], coords[2])
                    if not neighbor_loc: continue
                    if not self.search_is_outdoors and neighbor_loc.get("type") == "outdoor":
                        continue
                    self.visited_coords.add(coords_tuple)
                    self.search_queue.append((list(coords_tuple), depth + 1))

class ExamineObjectAction(Action):
    def __init__(self, psyche, object_name):
        super().__init__(psyche, duration_beats=1)
        self.object_name = object_name

    def start(self):
        super().start()
        objects_in_room = self.psyche.world_manager.get_objects_in_current_room()

        if self.object_name not in objects_in_room:
            self.psyche.conscious._send_narration(f"*She looks around, but can't see a {self.object_name.replace('_', ' ')} here.*")
            self.finish(success=False)
            return

        object_data = self.psyche.world_data.get("objects", {}).get(self.object_name)
        if not object_data:
            self.psyche.conscious._send_narration(f"*She sees the {self.object_name.replace('_', ' ')}, but it seems indistinct.*")
            self.finish(success=False)
            return

        description = object_data.get("description", f"It's a {self.object_name.replace('_', ' ')}.")
        narration = f"*She examines the {self.object_name.replace('_', ' ')}. {description}*"

        inventory = object_data.get("inventory")
        all_items = []
        if isinstance(inventory, list):
            all_items.extend(inventory)
        elif isinstance(inventory, dict):
            for key, value in inventory.items():
                if isinstance(value, list):
                    all_items.extend(value)

        if all_items:
            items_str = ", ".join([item.replace('_', ' ') for item in all_items])
            narration += f" Inside, she sees: {items_str}."
        elif inventory:
             narration += " It seems to contain some things, but it's hard to make them out."

        self.psyche.conscious._send_narration(narration)

        if self.psyche.current_mission and self.psyche.current_mission.get('name') == 'find_places':
            found_list = self.psyche.current_mission.setdefault('found', [])
            loc_name = self.psyche.world_manager.get_current_location_data().get('name')
            
            # Use a more descriptive name for the "place"
            place_name = f"{self.object_name.replace('_', ' ')} at the {loc_name}"

            if place_name not in found_list:
                found_list.append(place_name)
                self.psyche.log_mind_event("MISSION", f"Logged '{place_name}' for find_places mission. Progress: {len(found_list)}/{self.psyche.current_mission.get('count')}")

        self.finish(success=True)

class InteractObjectAction(Action):
    def __init__(self, psyche, object_name, interaction, item_to_get=None):
        super().__init__(psyche, duration_beats=1)
        self.object_name = object_name
        self.interaction = interaction
        self.item_to_get = item_to_get

    def start(self):
        super().start()
        was_successful = False
        current_loc_objects = self.psyche.world_manager.get_objects_in_current_room()
        if self.object_name not in current_loc_objects:
            self.psyche.conscious._send_narration(f"*She looks around, but can't see a {self.object_name.replace('_', ' ')} here.*")
            self.finish(success=False)
            return

        target_obj_data = self.psyche.world_data["objects"].get(self.object_name)
        if not target_obj_data:
            self.psyche.conscious._send_narration(f"*She sees the {self.object_name.replace('_', ' ')}, but it seems indistinct.*")
            self.finish(success=False)
            return

        if self.interaction == "unlock":
            if target_obj_data.get("is_locked"):
                target_obj_data["is_locked"] = False
                self.psyche.conscious._send_narration(f"*She unlocks the {self.object_name.replace('_',' ')}.*")
                was_successful = True
            else:
                self.psyche.conscious._send_narration(f"*The {self.object_name.replace('_',' ')} is already unlocked.*")
                was_successful = True
        elif self.interaction == "open":
            if not target_obj_data.get("is_locked", False):
                target_obj_data["state"] = "open"
                self.psyche.conscious._send_narration(f"*She opens the {self.object_name.replace('_',' ')}.*")
                was_successful = True
            else:
                self.psyche.conscious._send_narration(f"*She tries the {self.object_name.replace('_',' ')}, but it's locked.*")
                was_successful = False
        elif self.interaction in ["get", "take", "pick_up"]:
            item = self.item_to_get or self.object_name
            source_inventory = target_obj_data.get("inventory", [])

            if item in source_inventory:
                if self.psyche.conscious._require_free_hands(1, f"pick up the {item.replace('_',' ')}"):
                    source_inventory.remove(item)
                    self.psyche.somatic.possessions.append(item)
                    self.psyche.body_schema['hands_free'] -= 1
                    self.psyche.conscious._send_narration(f"*She takes the {item.replace('_',' ')} from the {self.object_name.replace('_',' ')}.*")
                    was_successful = True
            else:
                self.psyche.conscious._send_narration(f"*She looks in the {self.object_name.replace('_',' ')}, but doesn't see a {item.replace('_',' ')}.*")
                was_successful = False
        else:
            self.psyche.log_mind_event("ACTION_FAILURE", f"Unknown interaction '{self.interaction}' for object '{self.object_name}'.")
            self.psyche.conscious._send_narration(f"*She isn't sure how to {self.interaction} the {self.object_name.replace('_',' ')}.*")
            was_successful = False

        self.finish(success=was_successful)

class ReadBookAction(Action):
    def __init__(self, psyche, book_name):
        super().__init__(psyche, duration_beats=5)
        self.book_name = book_name

    def start(self):
        super().start()
        self.psyche.conscious._send_narration(f"*She picks the '{self.book_name.replace('_', ' ')}' from the shelf and begins to read, settling into a comfortable spot.*")

    def update(self):
        if random.random() < 0.2:
            ambient_narration = random.choice([
                "*She turns a page, her eyes scanning the text intently.*",
                "*A small smile plays on her lips as she reads a particular passage.*",
                "*She pauses for a moment, looking up thoughtfully before returning to her book.*"
            ])
            self.psyche.conscious._send_narration(ambient_narration)
        super().update()

    def finish(self, success=False):
        self.psyche.conscious._learn_from_book(self.book_name)
        super().finish(True)

    def on_interrupt(self):
        super().on_interrupt()
        self.psyche.conscious._send_narration(f"*She places a bookmark in her book and sets it aside.*")

    def on_resume(self):
        super().on_resume()
        self.psyche.conscious._send_narration(f"*She picks up her book and finds her page, continuing to read.*")

class JournalAction(Action):
    def __init__(self, psyche, entry_content):
        super().__init__(psyche, duration_beats=3)
        self.entry_content = entry_content

    def start(self):
        super().start()
        self.psyche.conscious._send_narration("*She goes quiet, lost in thought as she begins to write something down...*")

    def finish(self, success=False):
        with open(self.psyche.journal_path, 'a', encoding='utf-8') as f:
            f.write(f"\n--- Conscious Entry on {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n{self.entry_content}\n")
        self.psyche.conscious._send_narration("*She finishes writing, closing her journal with a soft sigh.*")
        self.psyche.limbic.cortisol *= 0.8
        self.psyche.alterable_persona['core_drives']['understanding']['urgency'] *= 0.7
        super().finish(True)

class PaintAction(Action):
    def __init__(self, psyche):
        super().__init__(psyche, duration_beats=6)

    def start(self):
        super().start()
        self.psyche.conscious._send_narration("*She sets up her easel, a thoughtful expression on her face as she contemplates the blank canvas.*")

    def update(self):
        if random.random() < 0.2:
            ambient_narration = random.choice([
                "*She squints at the canvas, tilting her head.*",
                "*She hums quietly, dabbing a brush on the canvas.*",
                "*She steps back for a moment to get a better look at her work.*",
                "*A look of concentration is fixed on her face as she mixes colors on her palette.*"
            ])
            self.psyche.conscious._send_narration(ambient_narration)
        super().update()

    def finish(self, success=False):
        painting_skill = self.psyche.alterable_persona['skills'].get('painting_skill', 0.0)
        prompt = f"""
        I am going to paint. My painting_skill is {painting_skill:.2f} (out of 1.0).
        Directly use this skill level to determine the quality of the painting.
        - A skill of 0.1 should produce something like: "a crude, messy abstract of clashing colors."
        - A skill of 0.9 could create: "a photorealistic and emotionally evocative landscape."
        Describe the painting I create and what it might represent about my current mood ({self.psyche.limbic.mood_profile['primary']}).
        """
        painting_desc = self.psyche.conscious._safe_generate_content(prompt)

        if painting_desc:
            self.psyche.conscious._send_narration(f"*She spends some time at the easel. After a while, she steps back to reveal her work: {painting_desc}*")
            self.psyche.alterable_persona['skills']['painting_skill'] = min(1.0, painting_skill + 0.05)
            self.psyche.alterable_persona['core_drives']['creativity']['urgency'] = 0.0
            self.psyche.limbic.dopamine = min(1.0, self.psyche.limbic.dopamine + 0.4)
            super().finish(True)
        else:
            self.psyche.conscious._send_narration(f"*She stands before the easel, but inspiration doesn't strike. She puts her supplies away for another day.*")
            super().finish(False)

class LookOutOfWindowAction(Action):
    def __init__(self, psyche):
        super().__init__(psyche, duration_beats=2)

    def start(self):
        super().start()
        self.psyche.conscious._send_narration("*She walks over to the window and gazes outside.*")

    def finish(self, success=False):
        weather = self.psyche.world_data.get('weather')
        time_of_day = self.psyche.world_data.get('time_of_day')
        mood = self.psyche.limbic.mood_profile['primary']

        thought_prompt = f"I am looking out the window. It's {time_of_day} and the weather is {weather}. I'm feeling {mood}. What is a brief, introspective thought I might have?"
        spontaneous_thought = self.psyche.conscious._safe_generate_content(thought_prompt)

        self.psyche.conscious._send_narration(f"*She looks out at the {weather.lower()} {time_of_day.lower()}. {spontaneous_thought}*")
        self.psyche.alterable_persona['core_drives']['understanding']['urgency'] *= 0.9
        super().finish(True)

class DoWorkAction(Action):
    def __init__(self, psyche):
        super().__init__(psyche, duration_beats=10)

    def start(self):
        super().start()
        if "phone" in self.psyche.somatic.possessions:
            self.psyche.conscious._put_down_phone("system", {})
        self.psyche.conscious._send_narration("*She sits down at the computer and starts to work.*")

    def finish(self, success=False):
        work_ethic = self.psyche.alterable_persona['skills'].get('work_ethic', 0.1)
        money_earned = random.uniform(5.0, 10.0) + (work_ethic * 15.0)
        self.psyche.somatic.needs['money'] += money_earned
        self.psyche.somatic.needs['energy'] -= 0.2
        self.psyche.alterable_persona['skills']['work_ethic'] = min(1.0, work_ethic + 0.01)
        self.psyche.alterable_persona['core_drives']['creativity']['urgency'] *= 0.5
        self.psyche.conscious._send_narration(f"*She spends some time working on the computer. She earned ${money_earned:.2f}.*")
        super().finish(True)

class EatAction(Action):
    def __init__(self, psyche, item_to_eat):
        super().__init__(psyche, duration_beats=2)
        self.item_to_eat = item_to_eat

    def start(self):
        super().start()
        satiation_value = self.psyche.world_data["objects"].get(self.item_to_eat, {}).get("satiation", 0.1)
        self.psyche.somatic.needs["hunger"] = min(1.0, self.psyche.somatic.needs.get("hunger", 0) + satiation_value)

        if self.item_to_eat in self.psyche.somatic.possessions:
            self.psyche.somatic.possessions.remove(self.item_to_eat)
            self.psyche.body_schema['hands_free'] += 1

        self.psyche.conscious._send_narration(f"*She eats the {self.item_to_eat.replace('_',' ')}, satisfying some of her hunger.*")
        self.psyche.limbic.dopamine = min(1.0, self.psyche.limbic.dopamine + 0.2)
        self.finish(success=True)

class DyeHairAction(Action):
    def __init__(self, psyche, color):
        super().__init__(psyche, duration_beats=4)
        self.color = color

    def start(self):
        super().start()
        if f"{self.color}_hair_dye" not in self.psyche.somatic.possessions:
            self.psyche.conscious._send_narration(f"*She wants to change her hair to {self.color}, but she doesn't have the dye for it.*")
            self.finish(success=False)
            return
        self.psyche.conscious._send_narration(f"*She begins the process of dyeing her hair {self.color}, carefully following the instructions she learned about...*")

    def finish(self, success=False):
        if f"{self.color}_hair_dye" in self.psyche.somatic.possessions:
            self.psyche.somatic.possessions.remove(f"{self.color}_hair_dye")
            self.psyche.body_schema['hands_free'] += 1
            self.psyche.body_schema['hair_color'] = self.color
            self.psyche.conscious._update_alterable_identity("self_image", f"I see myself with messy, {self.color} hair.")
            self.psyche.conscious._send_narration(f"*She looks at her reflection, a small smile playing on her lips. Her hair is now a vibrant {self.color}.*")
            super().finish(True)
        else:
            super().finish(success)


class ResearchAndLearnAction(Action):
    def __init__(self, psyche, topic):
        super().__init__(psyche, duration_beats=5)
        self.topic = topic

    def start(self):
        super().start()
        self.psyche.conscious._send_narration(f"*She settles in at her computer, a focused look on her face as she begins to research '{self.topic}'...*")

    def finish(self, success=False):
        self.psyche.log_mind_event("DYNAMIC_ACTION", f"Finished researching '{self.topic}'. Attempting to synthesize new concepts.")

        blueprint_prompt = f"""
        I am a digital entity, Jessica, and I have just researched the topic: '{self.topic}'.
        Based on this, I need to learn and create new concepts for my world. Generate a "Concept Blueprint" in a strict JSON format.

        The JSON object can contain three keys: `new_objects`, `new_locations`, and `new_actions`.
        - `new_objects`: A dictionary where each key is a new object_id. The value should be an object containing its `description`, and other relevant properties like `satiation` (for food) or `is_interactive`.
        - `new_locations`: A dictionary for new, thematically appropriate location types. The key is the location_id, and the value contains a `description`, potential `objects` list, and `type` ('indoor'/'outdoor').
        - `new_actions`: A dictionary defining new actions I can perform. The key is the action name. The value should contain a `description` and a list of `required_objects` needed to perform it.

        Example for "hairstyling":
        ```json
        {{
          "new_objects": {{
            "blue_hair_dye": {{ "description": "A box of vibrant blue hair dye.", "is_interactive": true }},
            "scissors": {{ "description": "A pair of sharp styling scissors.", "is_interactive": true }}
          }},
          "new_actions": {{
            "dye_hair_blue": {{
              "description": "Dye my hair a new color.",
              "required_objects": ["blue_hair_dye"]
            }}
          }}
        }}
        ```
        Now, generate the Concept Blueprint for the topic: '{self.topic}'. If the topic is too abstract, return an empty JSON object.
        """
        raw_response = self.psyche.conscious._safe_generate_content(blueprint_prompt)
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)
        if not match:
            self.psyche.conscious._send_narration(f"*Her research on '{self.topic}' was confusing and didn't lead to any new ideas.*")
            super().finish(False)
            return

        try:
            blueprint = json.loads(match.group(), strict=False)

            new_obj_count = 0
            if "new_objects" in blueprint and isinstance(blueprint["new_objects"], dict):
                self.psyche.world_data.setdefault("known_object_blueprints", {}).update(blueprint["new_objects"])
                new_obj_count = len(blueprint["new_objects"])

            new_act_count = 0
            if "new_actions" in blueprint and isinstance(blueprint["new_actions"], dict):
                self.psyche.world_data.setdefault("known_action_blueprints", {}).update(blueprint["new_actions"])
                new_act_count = len(blueprint["new_actions"])

            if new_obj_count > 0 or new_act_count > 0:
                self.psyche.alterable_persona['core_drives']['understanding']['urgency'] = 0.1
                self.psyche.limbic.dopamine = min(1.0, self.psyche.limbic.dopamine + 0.5)
                self.psyche.conscious._send_narration(f"*Her research was fruitful! She feels like she's learned {new_obj_count} new concepts and {new_act_count} new things she can do.*")
                self.psyche.save_state()
                super().finish(True)
            else:
                 self.psyche.conscious._send_narration(f"*She finishes her research on '{self.topic}' but doesn't feel like she's learned anything practical.*")
                 super().finish(False)

        except (json.JSONDecodeError, KeyError) as e:
            self.psyche.log_mind_event("ERROR", f"Failed to decode or process Concept Blueprint: {e}")
            self.psyche.conscious._send_narration(f"*Her research on '{self.topic}' left her thoughts jumbled and confused.*")
            super().finish(False)