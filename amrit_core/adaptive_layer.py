class AdaptiveLayer:
    def __init__(self):
        self.fail_counts = {}

    def record_failure(self, task):
        self.fail_counts[task] = self.fail_counts.get(task, 0) + 1

    def should_switch_strategy(self, task):
        return self.fail_counts.get(task, 0) >= 3

    def get_strategy(self, task):
        if self.should_switch_strategy(task):
            return "safe_mode"
        return "normal"
