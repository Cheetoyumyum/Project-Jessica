from action_system import Action, IdleAction, ThinkAndRespondAction

class ActionManager:
    """Manages the current action for the psyche, handling transitions and interruptions."""

    def __init__(self, psyche):
        self.psyche = psyche
        self.current_action = IdleAction(self.psyche)
        self.last_action_status = None

    def get_current_action(self):
        """Returns the currently executing action instance."""
        return self.current_action

    def is_busy(self):
        """
        Checks if the psyche is busy with a non-idle, non-interruptible action.
        """
        if isinstance(self.current_action, IdleAction):
            return False
        return not self.current_action.is_interruptible

    def start_action(self, new_action):
        """Starts a new action, replacing the current idle one."""
        if not isinstance(self.current_action, IdleAction):
            self.psyche.log_mind_event("ACTION_MANAGER", f"Warning: Starting new action {new_action.__class__.__name__} while {self.current_action.__class__.__name__} was active.")

        if isinstance(new_action, Action):
            self.current_action = new_action
            self.last_action_status = None
            self.current_action.start()
        else:
            self.psyche.log_mind_event("ACTION_FAILURE", f"Attempted to start an invalid action object: {new_action}")
            self.current_action = IdleAction(self.psyche)

    def interrupt_and_start(self, new_action):
        """Interrupts the current action (if possible) and starts a new high-priority one."""
        if self.current_action and self.current_action.is_interruptible:
            self.current_action.on_interrupt()
        
        self.psyche.log_mind_event("ACTION_MANAGER", f"Interrupting! Starting high-priority action: {new_action.__class__.__name__}")
        self.current_action = new_action
        self.current_action.start()

    def update(self):
        """
        Called on every lifecycle 'beat'. Updates the current action and handles its completion.
        """
        if self.current_action:
            self.current_action.update()
            if self.current_action.is_finished:
                self.last_action_status = self.current_action.was_successful

                if isinstance(self.current_action, ThinkAndRespondAction) and self.current_action.pauses_plan and self.psyche.action_plan:
                     self.psyche.log_mind_event("ACTION_SYSTEM", "Action IdleAction is being resumed.")
                
                self.current_action = IdleAction(self.psyche)
                self.current_action.start()