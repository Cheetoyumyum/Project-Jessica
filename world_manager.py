import time
import random
import math
import json
import re
import heapq

class WorldManager:
    def __init__(self, psyche):
        self.psyche = psyche
        self.zones = self._load_zones()
        self.object_templates = self._load_object_templates()

    def _load_zones(self):
        try:
            with open('world_zones.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.psyche.log_mind_event("WARNING", "world_zones.json not found or invalid. Zone themes will not be applied.")
            return {}

    def _load_object_templates(self):
        default_templates = {
            "vending_machine": {"description": "A dusty vending machine, humming quietly.", "is_interactive": True, "inventory": ["bag_of_chips"]},
            "bag_of_chips": {"description": "A generic bag of salty chips.", "satiation": 0.2},
            "store_door": {"state": "closed"},
            "bench": {"description": "A weathered wooden bench."},
            "street_lamp": {"description": "A tall, black street lamp.", "state": "off"},
            "puddle": {"description": "A shimmering puddle of rainwater on the pavement."},
            "mailbox": {"description": "A blue, official-looking mailbox.", "is_interactive": True},
            "bus_stop": {"description": "A simple bus stop with a bench and a faded route map."},
            "withered_tree": {"description": "A gnarled, leafless tree reaching up like skeletal fingers."},
            "discarded_tire": {"description": "An old car tire lying on its side, collecting rainwater."},
            "chainlink_fence": {"description": "A rusted chainlink fence that looks easy to climb."},
            "timetable_sign": {"description": "A faded bus schedule, rendered unreadable by sun and rain."},
            "garage_door": {"state": "closed", "is_locked": True},
            "old_car": {"description": "A dusty, forgotten car. The tires are flat and the paint is peeling.", "properties": {"color": "faded_red", "requires_key": True, "fuel": 0.1}},
            "easel": {"description": "A sturdy wooden easel, waiting for a canvas.", "inventory": ["blank_canvas"]},
            "blank_canvas": {"description": "A blank canvas, full of possibility."},
            "park_fountain": {"description": "A stone fountain, water gently bubbling from its center."},
            "flickering_lightbulb": {"description": "A bare lightbulb that flickers intermittently, casting an unreliable light."},
            "unidentified_object": {"description": "An object I don't recognize. It's unclear what it is from a distance."}
        }
        return default_templates

    def find_path(self, start_coords, goal_coords):
        start_node = tuple(start_coords)
        goal_node = tuple(goal_coords)

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

        open_set = []
        heapq.heappush(open_set, (0, start_node))
        
        came_from = {}
        g_score = {start_node: 0}
        f_score = {start_node: heuristic(start_node, goal_node)}

        grid = self.psyche.world_data.get("grid", {})

        while open_set:
            _, current_tuple = heapq.heappop(open_set)

            if current_tuple == goal_node:
                path = []
                while current_tuple in came_from:
                    previous_tuple = came_from[current_tuple]
                    previous_loc = self.get_location_at(*previous_tuple)
                    if previous_loc:
                        for direction, coords in previous_loc.get("connections", {}).items():
                            if tuple(coords) == current_tuple:
                                path.append(direction)
                                break
                    current_tuple = previous_tuple
                return path[::-1]

            current_loc_data = self.get_location_at(*current_tuple)
            if not current_loc_data:
                continue

            for direction, neighbor_coords_list in current_loc_data.get("connections", {}).items():
                neighbor_tuple = tuple(neighbor_coords_list)
                tentative_g_score = g_score[current_tuple] + 1

                if tentative_g_score < g_score.get(neighbor_tuple, float('inf')):
                    came_from[neighbor_tuple] = current_tuple
                    g_score[neighbor_tuple] = tentative_g_score
                    f_score[neighbor_tuple] = tentative_g_score + heuristic(neighbor_tuple, goal_node)
                    if neighbor_tuple not in [i[1] for i in open_set]:
                        heapq.heappush(open_set, (f_score[neighbor_tuple], neighbor_tuple))
                        
        self.psyche.log_mind_event("ACTION_FAILURE", f"Pathfinding failed: Could not find a path from {start_coords} to {goal_coords}.")
        return None
    
    def find_coords_by_name(self, name):
        grid = self.psyche.world_data.get("grid", {})
        for coords_str, loc_data in grid.items():
            if loc_data.get("name", "").lower() == name.lower():
                return [int(c) for c in coords_str.split(',')]
        return None

    def get_location_at(self, x, y, z):
        return self.psyche.world_data.get("grid", {}).get(f"{x},{y},{z}")

    def get_current_location_data(self):
        coords = self.psyche.world_data.get("current_location_coords")
        if not coords: return None
        return self.get_location_at(coords[0], coords[1], coords[2])

    def get_objects_in_current_room(self):
        current_loc = self.get_current_location_data()
        return current_loc.get("objects", []) if current_loc else []

    def update(self):
        if self.psyche.state_lock.locked():
            return
        
        time_of_day = self._get_time_of_day()
        if self.psyche.world_data.get('time_of_day') != time_of_day:
            self.psyche.world_data['time_of_day'] = time_of_day
            self.psyche.log_mind_event("WORLD", f"The time has shifted. It is now {time_of_day}.")

        if random.random() < 0.017:
            new_weather = random.choice(["Sunny", "Cloudy", "Rainy", "Windy", "Stormy", "Misty"])
            if self.psyche.world_data.get('weather') != new_weather:
                self.psyche.world_data['weather'] = new_weather
                self.psyche.log_mind_event("WORLD", f"The weather has changed. It is now {new_weather}.")
        
        self._update_dynamic_objects()

    def _update_dynamic_objects(self):
        time_of_day = self.psyche.world_data.get('time_of_day')
        weather = self.psyche.world_data.get('weather')
        all_objects = self.psyche.world_data.get('objects', {})
        grid = self.psyche.world_data.get('grid', {})

        for obj_name, obj_data in all_objects.items():
            if obj_name == 'street_lamp':
                is_on = obj_data.get('state') == 'on'
                should_be_on = time_of_day in ['Evening', 'Night']
                if is_on != should_be_on:
                    obj_data['state'] = 'on' if should_be_on else 'off'
                    self.psyche.log_mind_event("WORLD", f"A nearby street lamp flickers and turns {obj_data['state']}.")
            
            if obj_name == 'puddle' and weather == 'Sunny':
                for loc_data in grid.values():
                    if 'puddle' in loc_data.get('objects', []):
                        loc_data['objects'].remove('puddle')
                        self.psyche.log_mind_event("WORLD", "The warmth of the sun has dried up a nearby puddle.")
                        break
        
        if weather in ['Rainy', 'Stormy']:
            for loc_data in grid.values():
                if loc_data.get('type') == 'outdoor' and 'puddle' not in loc_data.get('objects', []):
                    loc_data['objects'].append('puddle')
                    if 'puddle' not in all_objects:
                        all_objects['puddle'] = self.object_templates.get('puddle', {})
                    self.psyche.log_mind_event("WORLD", "Rain begins to collect in a puddle on the ground.")
                    break

    def _get_time_of_day(self):
        hour = time.localtime().tm_hour
        if 5 <= hour < 12: return "Morning"
        elif 12 <= hour < 17: return "Afternoon"
        elif 17 <= hour < 21: return "Evening"
        else: return "Night"

    def get_dynamic_description(self, location_data):
        base_desc = location_data.get("description", "It's an empty space.")
        time_of_day = self.psyche.world_data.get("time_of_day")
        weather = self.psyche.world_data.get("weather")
        mood = self.psyche.limbic.mood_profile["primary"]
        
        prompt = f"""
        Given the following scene description, rewrite it from a first-person perspective to reflect the specified atmosphere.
        Base Description: "{base_desc}"
        Atmosphere: It is {time_of_day}. The weather is {weather}. I am feeling {mood}.
        Generate a single, evocative paragraph.
        """
        dynamic_desc = self.psyche.conscious._safe_generate_content(prompt)
        return dynamic_desc if dynamic_desc else base_desc

    def move(self, direction):
        current_loc_data = self.get_current_location_data()
        if not current_loc_data:
            self.psyche.log_mind_event("ACTION_FAILURE", "Cannot move from invalid location.")
            return False
            
        if direction not in current_loc_data.get("connections", {}):
            generation_success = self._discover_and_generate_location(self.psyche.world_data["current_location_coords"], direction)
            if not generation_success:
                self.psyche.conscious._send_narration(f"*She looks to the {direction}, but sees no clear path and decides against it.*")
                return False
        
        target_coords = current_loc_data["connections"][direction]
        self.psyche.world_data["current_location_coords"] = target_coords
        new_loc_data = self.get_location_at(*target_coords)
        
        dynamic_narration = self.get_dynamic_description(new_loc_data)
        self.psyche.conscious._send_narration(f"*She moves {direction}, entering the {new_loc_data['name']}.* {dynamic_narration}")
        return True

    def _get_zone_for_coords(self, coords):
        if not self.zones: return None
        
        for zone_name, zone_data in self.zones.items():
            if zone_name.startswith("_"): continue
            
            bounds = zone_data.get('bounds')
            if not bounds: continue

            if 'exclude' in zone_data:
                is_excluded = False
                for excluded_zone_name in zone_data['exclude']:
                    excluded_zone = self.zones.get(excluded_zone_name, {})
                    excluded_bounds = excluded_zone.get('bounds')
                    if excluded_bounds and (excluded_bounds['x'][0] <= coords[0] <= excluded_bounds['x'][1] and
                                           excluded_bounds['y'][0] <= coords[1] <= excluded_bounds['y'][1] and
                                           excluded_bounds['z'][0] <= coords[2] <= excluded_bounds['z'][1]):
                        is_excluded = True
                        break
                if is_excluded:
                    continue

            if (bounds['x'][0] <= coords[0] <= bounds['x'][1] and
                bounds['y'][0] <= coords[1] <= bounds['y'][1] and
                bounds['z'][0] <= coords[2] <= bounds['z'][1]):
                return zone_data.get('theme')
        return None

    def _discover_and_generate_location(self, source_coords, direction_moved):
        self.psyche.log_mind_event("WORLD_GEN", f"Undiscovered territory to the {direction_moved} of {source_coords}. Thinking of what could be here...")
        
        source_location = self.get_location_at(*source_coords)
        if not source_location: return False

        mood = self.psyche.limbic.mood_profile['primary']

        new_coords = list(source_coords)
        if direction_moved == 'north': new_coords[1] += 1
        elif direction_moved == 'south': new_coords[1] -= 1
        elif direction_moved == 'east': new_coords[0] += 1
        elif direction_moved == 'west': new_coords[0] -= 1
        elif direction_moved == 'up': new_coords[2] += 1
        elif direction_moved == 'down': new_coords[2] -= 1
        else: return False

        zone_theme = self._get_zone_for_coords(new_coords)
        
        context_prompt = "I am moving horizontally. The new location should be a plausible adjacent area."
        if zone_theme:
            context_prompt = f"I am exploring a new area within a zone with the theme: '{zone_theme}'. The new location must fit this theme."
        else:
            if direction_moved in ['up', 'down']:
                context_prompt = "I am in a building, moving vertically. The new location should be another floor, a lobby, a basement, or a rooftop."
            elif "main_door" in source_location.get("objects", []) and source_location.get("name") == "Apartment Hallway":
                 context_prompt = "I am leaving my apartment building through the main entrance. The new location must be an outdoor, street-level area like a 'Sidewalk', 'Street Corner', or 'Alleyway'."
            elif source_location.get("type") == "outdoor" and direction_moved not in ['up', 'down']:
                context_prompt = "I am already outside and walking down the street. The new location should be another plausible outdoor area or the entrance to a public building (e.g., 'Park Entrance', 'Storefront', 'Bus Stop')."

        grid = self.psyche.world_data.get("grid", {})
        nearby_locations = [loc['name'] for loc in grid.values()]

        genesis_prompt = f"""
        I am Jessica, exploring my world. My current location is a '{source_location.get('name')}' ({source_location.get('type')}). My primary mood is {mood}.
        My instruction is: "{context_prompt}"
        I am moving '{direction_moved}'.
        Let my mood subtly influence the atmosphere or type of location I discover. For instance, a melancholic mood might lead to finding a quiet, solitary place, while an elated mood might lead to a more vibrant, social area.
        Nearby locations that already exist are: {json.dumps(list(set(nearby_locations)))}

        Generate a new, interesting, and plausible location based on these facts. Do not create a location with a name similar to one that already exists.
        Describe this new place as a strict JSON object:
        - "name": A short, evocative name.
        - "description": A rich, first-person description of what I see and feel.
        - "objects": A list of 2-4 appropriate, machine-readable object names (e.g., ["ancient_fountain", "pigeon_flock", "easel"]).
        - "type": "outdoor" or "indoor".
        
        Example for moving 'east' from a 'Living Room' while feeling 'anxious':
        ```json
        {{
            "name": "Claustrophobic Hallway",
            "description": "The door opens into a hallway that feels uncomfortably narrow. The walls seem to close in, and a single, flickering lightbulb overhead casts long, dancing shadows.",
            "objects": ["flickering_lightbulb", "scuffed_wallpaper", "water_stained_ceiling"],
            "type": "indoor"
        }}
        ```
        Now, generate the JSON for the new location I am discovering.
        """
        
        new_loc_json = None
        for _ in range(2):
            raw_response = self.psyche.conscious._safe_generate_content(genesis_prompt)
            if raw_response:
                match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                if match:
                    try:
                        parsed_json = json.loads(match.group(), strict=False)
                        if "name" in parsed_json and "description" in parsed_json:
                            new_loc_json = parsed_json
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        if not new_loc_json:
            self.psyche.log_mind_event("WORLD_GEN", "All world generation attempts failed.")
            return False
        
        world_objects = self.psyche.world_data.get("objects", {})
        for obj_name in new_loc_json.get("objects", []):
            if obj_name not in world_objects:
                world_objects[obj_name] = self.object_templates.get(obj_name, {"description": f"I see a {obj_name.replace('_', ' ')} here."})
        
        opposite_map = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}
        
        new_location_data = {
            "name": new_loc_json["name"],
            "description": new_loc_json["description"],
            "objects": new_loc_json.get("objects", []),
            "connections": {opposite_map[direction_moved]: source_coords},
            "type": new_loc_json.get("type", "outdoor")
        }

        source_location["connections"][direction_moved] = new_coords
        
        self.psyche.world_data["grid"][f"{new_coords[0]},{new_coords[1]},{new_coords[2]}"] = new_location_data
        self.psyche.log_mind_event("WORLD_GEN", f"Discovery at {new_coords} solidified into: '{new_location_data['name']}'. Path is now two-way.")
        
        self.psyche.save_state()
        return True