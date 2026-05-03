"""Monitor Agent — System health, resource usage, performance tracking."""
import os
import time
from base_agent import BaseAgent

class MonitorAgent(BaseAgent):
    def __init__(self, eb, state):
        super().__init__("MonitorAgent", eb, state)
        self._metrics = []

    async def execute(self, task: dict) -> dict:
        d = task.get("data", {})
        action = d.get("action", "check")
        await self.report(f"Monitor [{action}]")
        if action == "check":
            return await self._system_check()
        if action == "memory":
            return self._memory_info()
        if action == "cpu":
            return self._cpu_info()
        if action == "disk":
            return self._disk_info()
        if action == "alert":
            return await self._check_alerts()
        if action == "history":
            return self.ok(metrics=self._metrics[-50:])
        if action == "agents":
            return await self.check_agents()
        return await self._system_check()

    async def check_agents(self) -> dict:
        """
        Check health/status of all registered agents. Emits alerts if any agent is unresponsive or unhealthy.
        """
        unhealthy = []
        healthy = []
        # Try to get orchestrator from state or event bus if possible
        orc = getattr(self, 'orchestrator', None)
        if not orc and hasattr(self, 'state'):
            orc = getattr(self.state, 'orchestrator', None)
        if not orc:
            # Can't check agents without orchestrator
            await self.report("No orchestrator found for agent health check.", level="warning")
            return self.ok(note="No orchestrator found for agent health check.")
        agents = getattr(orc, 'agents', {})
        for name, agent in agents.items():
            try:
                # Prefer agent._system_check if available, else just ping execute
                if hasattr(agent, '_system_check'):
                    result = await agent._system_check()
                else:
                    # Send a minimal health check task
                    result = await agent.execute({"data": {"action": "check"}})
                if result.get('ok', True):
                    healthy.append(name)
                else:
                    unhealthy.append(name)
            except Exception as e:
                unhealthy.append(name)
                await self.report(f"Agent {name} health check failed: {e}", level="warning")
        if unhealthy:
            await self.emit("monitor.agent_alert", {"unhealthy": unhealthy})
        return self.ok(healthy=healthy, unhealthy=unhealthy, total=len(agents))

    async def _system_check(self) -> dict:
        try:
            import psutil
            info = {
                "cpu_percent":    psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_gb_used": round(psutil.virtual_memory().used / 1e9, 2),
                "disk_percent":   psutil.disk_usage("/").percent,
                "uptime_s":       round(time.time() - psutil.boot_time()),
                "python_pid":     os.getpid(),
            }
            self._metrics.append({"t": time.time(), **info})
            await self.set_state("last_health", info)
            await self.emit("monitor.health", info)
            return self.ok(**info)
        except ImportError:
            return self.ok(note="psutil not installed: pip install psutil",
                           pid=os.getpid())

    def _memory_info(self) -> dict:
        try:
            import psutil
            m = psutil.virtual_memory()
            return self.ok(total_gb=round(m.total/1e9,2),
                           used_gb=round(m.used/1e9,2),
                           free_gb=round(m.available/1e9,2),
                           percent=m.percent)
        except ImportError:
            return self.ok(note="psutil required")

    def _cpu_info(self) -> dict:
        try:
            import psutil
            return self.ok(percent=psutil.cpu_percent(0.5),
                           count=psutil.cpu_count(),
                           freq_mhz=psutil.cpu_freq().current if psutil.cpu_freq() else 0)
        except ImportError:
            return self.ok(note="psutil required")

    def _disk_info(self) -> dict:
        try:
            import psutil
            d = psutil.disk_usage("/")
            return self.ok(total_gb=round(d.total/1e9,2),
                           used_gb=round(d.used/1e9,2),
                           free_gb=round(d.free/1e9,2),
                           percent=d.percent)
        except ImportError:
            return self.ok(note="psutil required")

    async def _check_alerts(self) -> dict:
        alerts = []
        try:
            import psutil
            if psutil.virtual_memory().percent > 90:
                alerts.append("⚠️ Memory > 90%")
            if psutil.cpu_percent(0.5) > 95:
                alerts.append("⚠️ CPU > 95%")
            if psutil.disk_usage("/").percent > 95:
                alerts.append("⚠️ Disk > 95%")
        except ImportError:
            pass
        if alerts:
            await self.emit("monitor.alert", {"alerts": alerts})
        return self.ok(alerts=alerts, healthy=len(alerts)==0)
