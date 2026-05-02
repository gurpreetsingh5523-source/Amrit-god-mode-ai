from base_agent import BaseAgent


class CheckerAgent(BaseAgent):
    def execute(self, task=None):
        try:
            if task and task.get("system") == "external":
                # Placeholder logic for external system check
                print("Performing external system check...")
                # Add actual implementation here
                return {
                    "status": "success",
                    "message": "External system check completed.",
                }
            else:
                return {"status": "error", "message": "Invalid task or system type."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
