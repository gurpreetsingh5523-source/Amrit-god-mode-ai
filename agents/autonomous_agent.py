class AutonomousAgent:
    def __init__(self, core, agent_id=None):
        self.core = core
        self.agent_id = agent_id or id(self)

    async def run_goal(self, goal: str):
        print(f"[AutonomousAgent-{self.agent_id}] Goal: {goal}")
        # Step 1: Plan
        plan = await self.core.llm.generate(
            f"Break this goal into steps:\n{goal}"
        )
        steps = plan.split("\n")
        results = []
        for step in steps:
            if not step.strip():
                continue
            print(f"[AutonomousAgent-{self.agent_id}] Executing: {step}")
            result = await self.core.think(step)
            results.append(result)
        return {
            "goal": goal,
            "steps": steps,
            "results": results
        }
