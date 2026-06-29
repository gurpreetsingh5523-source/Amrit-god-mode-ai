import asyncio
import pytest
from orchestrator import Orchestrator
from event_bus import EventBus

@pytest.mark.asyncio
async def test_goal_engine():
    print("[TEST] Initializing Orchestrator and GoalEngine...")
    bus = EventBus()
    orch = Orchestrator(event_bus=bus)
    await orch.initialize()
    # Add a test goal
    print("[TEST] Adding test goal...")
    goal = orch.goal_engine.add_goal("Test: Write a hello world script", priority=1)
    # Run a cycle to process goals
    print("[TEST] Running orchestrator cycle...")
    await orch.run_cycle()
    # Check goal status
    print(f"[TEST] Goal status: {goal.status}")
    print(f"[TEST] Goal result: {goal.result}")
    assert goal.status in ("done", "failed"), "Goal should be processed"
    print("[TEST] GoalEngine test complete.")

if __name__ == "__main__":
    asyncio.run(test_goal_engine())