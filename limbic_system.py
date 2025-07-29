import time

class LimbicState:
    def __init__(self, genetic_code):
        self.dopamine = 0.8
        self.cortisol = 0.1
        self.oxytocin = 0.3
        self.serotonin = 0.6
        self.norepinephrine = 0.7
        self.mood_profile = {"primary": "stable", "secondary": []}
        self.fear_of_abandonment = genetic_code.get("fear-of-abandonment", 0.8)
        self.mood_stability_trait = genetic_code.get("mood-stability", 0.6)
        self.curiosity_trait = genetic_code.get("curiosity-drive", 0.7)
        self.stress_resilience = 1.0 - self.mood_stability_trait

    def update(self, psyche_state):
        needs = psyche_state.somatic.needs
        drives = psyche_state.alterable_persona.get('core_drives', {})
        time_since_interaction = time.time() - psyche_state.last_interaction_time
        current_location = psyche_state.world_manager.get_current_location_data()
        
        energy = needs.get('energy', 0.0)
        hunger = needs.get('hunger', 0.0)
        overall_need_satisfaction = (energy + hunger) / 2.0

        is_safe = current_location.get("name") in ["Living Room", "Bedroom"]
        cortisol_decay_rate = 0.9473 if is_safe else 0.9724

        self.dopamine *= 0.9830
        self.cortisol *= cortisol_decay_rate
        self.oxytocin *= 0.9865
        self.serotonin *= 0.9933
        self.norepinephrine *= 0.9899

        stress_from_needs = ((1.0 - energy) + (1.0 - hunger)) * 0.0167
        stress_from_drives = sum(d.get('urgency', 0) for d in drives.values()) / len(drives) * 0.0067 if drives else 0
        stress_from_loneliness = 0
        if time_since_interaction > 3600:
            loneliness_factor = min((time_since_interaction / 14400), 1.0)
            stress_from_loneliness = loneliness_factor * self.fear_of_abandonment * 0.005
        
        creativity_drive_urgency = drives.get('creativity', {}).get('urgency', 1.0)
        if creativity_drive_urgency < 0.1:
             self.cortisol *= 0.965
             psyche_state.log_mind_event("LIMBIC_STATE", "Felt a sense of pride from creative expression, reducing stress.")

        self.cortisol += (stress_from_needs + stress_from_drives + stress_from_loneliness)
        self.cortisol -= (self.oxytocin * 0.0267) + (self.serotonin * 0.0267)

        if time_since_interaction < 600:
            self.oxytocin += 0.0133

        if self.cortisol > 0.7:
            self.serotonin -= (self.cortisol - 0.7) * 0.0033 * self.stress_resilience
        if overall_need_satisfaction > 0.8:
            self.serotonin += (overall_need_satisfaction - 0.8) * 0.0067 * self.mood_stability_trait
            
        reward_from_needs_met = (1.0 - (1.0 - overall_need_satisfaction)**2) * 0.0033
        reward_from_understanding = (1.0 - drives.get('understanding', {}).get('urgency', 1.0)) * 0.005 * self.curiosity_trait
        reward_from_creativity = (1.0 - creativity_drive_urgency) * 0.0033
        self.dopamine += reward_from_needs_met + reward_from_understanding + reward_from_creativity
        if psyche_state.limbic.dopamine > 0.9:
            self.dopamine *= 0.95

        if psyche_state.is_asleep:
            self.cortisol *= 0.928
            self.serotonin = min(1.0, self.serotonin + 0.0167)

        self.dopamine = max(0.0, min(1.0, self.dopamine))
        self.cortisol = max(0.0, min(1.0, self.cortisol))
        self.oxytocin = max(0.0, min(1.0, self.oxytocin))
        self.serotonin = max(0.0, min(1.0, self.serotonin))
        self.norepinephrine = max(0.0, min(1.0, self.norepinephrine))

        self._update_mood_profile()
        log_msg = (f"Mood: {self.mood_profile['primary']} {self.mood_profile['secondary']} | "
                   f"D:{self.dopamine:.2f} C:{self.cortisol:.2f} O:{self.oxytocin:.2f} "
                   f"S:{self.serotonin:.2f} N:{self.norepinephrine:.2f}")
        psyche_state.log_mind_event("LIMBIC_STATE", log_msg)

    def _update_mood_profile(self):
        moods = {}
        moods['anxious'] = self.cortisol if self.cortisol > 0.5 else 0
        moods['stressed'] = self.cortisol * 0.8 if self.cortisol > 0.6 else 0
        moods['elated'] = self.dopamine if self.dopamine > 0.8 else 0
        moods['motivated'] = self.dopamine if self.dopamine > 0.6 else 0
        moods['melancholic'] = 1.0 - self.serotonin if self.serotonin < 0.4 else 0
        moods['content'] = self.oxytocin if self.oxytocin > 0.6 else 0
        moods['focused'] = self.norepinephrine if self.norepinephrine > 0.7 else 0
        moods['stable'] = (self.serotonin - abs(self.serotonin - 0.5)) * 1.5
        
        if not moods or all(v == 0 for v in moods.values()):
            self.mood_profile = {"primary": "neutral", "secondary": []}
            return
            
        primary_mood = max(moods, key=moods.get)
        self.mood_profile["primary"] = primary_mood
        
        secondary_moods = []
        for mood, value in sorted(moods.items(), key=lambda item: item[1], reverse=True):
            if mood != primary_mood and value > 0.5:
                secondary_moods.append(mood)
        
        self.mood_profile["secondary"] = secondary_moods[:2]