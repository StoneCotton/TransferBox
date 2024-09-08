class StateManager:
    def __init__(self):
        self.current_state = "standby"
        self.menu_active = False

    def get_current_state(self):
        return self.current_state

    def set_current_state(self, state):
        if state in ["standby", "transfer", "utility"]:
            self.current_state = state
        else:
            raise ValueError("Invalid state. Must be 'standby', 'transfer', or 'utility'.")

    def is_standby(self):
        return self.current_state == "standby"

    def is_transfer(self):
        return self.current_state == "transfer"

    def is_utility(self):
        return self.current_state == "utility"

    def enter_standby(self):
        self.current_state = "standby"
        self.menu_active = False

    def enter_transfer(self):
        if self.current_state == "standby":
            self.current_state = "transfer"
        else:
            raise ValueError("Can only enter transfer state from standby state.")

    def enter_utility(self):
        if self.current_state == "standby":
            self.current_state = "utility"
            self.menu_active = True
        else:
            raise ValueError("Can only enter utility state from standby state.")

    def exit_utility(self):
        if self.current_state == "utility":
            self.current_state = "standby"
            self.menu_active = False
        else:
            raise ValueError("Can only exit utility state when in utility state.")

    def is_menu_active(self):
        return self.menu_active

    def set_menu_active(self, active):
        self.menu_active = active