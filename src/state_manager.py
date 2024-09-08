class StateManager:
    def __init__(self):
        self.transfer_in_progress = False
        self.menu_active = False
        self.current_mode = "transfer"  # Either 'transfer' or 'utility'

    def get_transfer_in_progress(self):
        return self.transfer_in_progress

    def set_transfer_in_progress(self, state):
        self.transfer_in_progress = state

    def get_menu_active(self):
        return self.menu_active

    def set_menu_active(self, state):
        self.menu_active = state

    def get_current_mode(self):
        return self.current_mode

    def set_current_mode(self, mode):
        if mode in ["transfer", "utility"]:
            self.current_mode = mode
        else:
            raise ValueError("Invalid mode. Must be 'transfer' or 'utility'.")