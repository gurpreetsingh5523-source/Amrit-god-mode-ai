"""
AMRIT GODMODE — MCP (Model Context Protocol) Server
=====================================================
Lightweight MCP server exposing AMRIT tools to Claude Code / Codex.
No heavy dependencies — pure JSON-RPC 2.0 over stdio/SSE.

Protocol: https://modelcontextprotocol.io/specification
Transport: stdio (default) or SSE (HTTP)

Google lightweight principle: single-file, zero framework,
pure asyncio + json. No express/fastify/flask needed.
"""

import asyncio
import json
import sys
import os
import time
from typing import Optional
from logger import setup_logger

logger = setup_logger("mcp")

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# ─── Tool Registry ──────────────────────────────────────────────


def _build_tools(orchestrator) -> list[dict]:
    """Build MCP tool definitions from AMRIT capabilities."""
    tools = [
        {
            "name": "amrit_goal",
            "description": "Set and execute a high-level goal. AMRIT decomposes it into tasks and runs agents.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The goal to achieve"},
                },
                "required": ["goal"],
            },
        },
        {
            "name": "amrit_agent_run",
            "description": "Run a specific AMRIT agent with a task. Agents: coder, researcher, tester, debugger, planner, internet, vision, voice, memory, tool.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "description": "Agent name (coder, researcher, tester, etc.)"},
                    "task": {"type": "object", "description": "Task dict with 'name' and optional 'action', 'data'"},
                },
                "required": ["agent", "task"],
            },
        },
        {
            "name": "amrit_swarm",
            "description": "Launch a multi-agent swarm with queen/worker coordination to solve complex objectives.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "What the swarm should accomplish"},
                    "tasks": {
                        "type": "array",
                        "description": "List of tasks [{name, agent, data, priority, depends_on}]",
                        "items": {"type": "object"},
                    },
                },
                "required": ["objective"],
            },
        },
        {
            "name": "amrit_code",
            "description": "Generate, refactor, or analyze code using AMRIT's coding agent with local LLM.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["generate", "refactor", "review", "explain"], "description": "Code action"},
                    "code": {"type": "string", "description": "Source code (for refactor/review/explain)"},
                    "prompt": {"type": "string", "description": "What to generate or how to refactor"},
                    "language": {"type": "string", "description": "Programming language", "default": "python"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "amrit_research",
            "description": "Research a topic using AMRIT's internet agent + arXiv pipeline.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Research query or topic"},
                    "depth": {"type": "string", "enum": ["quick", "medium", "deep"], "default": "medium"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "amrit_test",
            "description": "Run tests or generate tests for code.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["run", "generate"], "description": "Test action"},
                    "file": {"type": "string", "description": "File to test"},
                    "code": {"type": "string", "description": "Code to generate tests for"},
                },
                "required": ["action"],
            },
        },
        {
            "name": "amrit_memory_search",
            "description": "Search AMRIT's vector memory (episodic, semantic, long-term).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "memory_type": {"type": "string", "enum": ["episodic", "semantic", "long_term", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
        {
            "name": "amrit_selffix",
            "description": "Run AMRIT's self-evolution engine to analyze and fix its own code.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "max_cycles": {"type": "integer", "default": 1, "description": "Number of fix cycles"},
                },
            },
        },
        {
            "name": "amrit_status",
            "description": "Get current AMRIT system status — agents, swarm, memory, LLM stats.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "amrit_llm",
            "description": "Direct LLM completion using AMRIT's local models (Ollama/AirLLM). Zero API cost.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Prompt for the LLM"},
                    "system": {"type": "string", "description": "System prompt"},
                    "model": {"type": "string", "description": "Model category: coding, reasoning, fast, creative, deep"},
                    "max_tokens": {"type": "integer", "default": 400},
                },
                "required": ["prompt"],
            },
        },
    ]
    return tools


# ─── Tool Execution ─────────────────────────────────────────────


async def _execute_tool(name: str, args: dict, orchestrator) -> dict:
    """Execute an MCP tool call and return result."""
    try:
        if name == "amrit_goal":
            result = await orchestrator.run_goal(args["goal"])
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_agent_run":
            agent = orchestrator.get_agent(args["agent"])
            if not agent:
                return {"content": [{"type": "text", "text": f"Agent '{args['agent']}' not found"}], "isError": True}
            result = await agent.execute(args.get("task", {}))
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_swarm":
            from swarm import Queen
            queen = Queen(orchestrator.bus, orchestrator.agents, orchestrator.state)
            tasks = args.get("tasks", [])
            if not tasks:
                # Auto-decompose via planner
                planner = orchestrator.get_agent("planner")
                if planner:
                    plan = await planner.execute({"name": args["objective"], "action": args["objective"]})
                    tasks = plan.get("tasks", [{"name": args["objective"], "agent": "coder"}])
            result = await queen.spawn_swarm(args["objective"], tasks)
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_code":
            coder = orchestrator.get_agent("coder")
            task = {"action": args["action"], "name": args.get("prompt", args["action"])}
            if args.get("code"):
                task["code"] = args["code"]
            if args.get("prompt"):
                task["prompt"] = args["prompt"]
            if args.get("language"):
                task["language"] = args["language"]
            result = await coder.execute(task)
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_research":
            researcher = orchestrator.get_agent("researcher")
            if researcher:
                result = await researcher.execute({
                    "name": args["query"], "action": "research",
                    "query": args["query"], "depth": args.get("depth", "medium"),
                })
                return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
            return {"content": [{"type": "text", "text": "Researcher agent not available"}], "isError": True}

        elif name == "amrit_test":
            tester = orchestrator.get_agent("tester")
            result = await tester.execute({
                "action": args["action"], "name": args.get("file", "test"),
                "file": args.get("file", ""), "code": args.get("code", ""),
            })
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_memory_search":
            memory = orchestrator.get_agent("memory")
            if memory:
                result = await memory.execute({
                    "action": "search", "query": args["query"],
                    "type": args.get("memory_type", "all"),
                    "limit": args.get("limit", 5),
                })
                return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
            return {"content": [{"type": "text", "text": "Memory agent not available"}], "isError": True}

        elif name == "amrit_selffix":
            result = await orchestrator._run_selffix()
            return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

        elif name == "amrit_status":
            from llm_router import LLMRouter
            router = LLMRouter()
            status = {
                "agents": list(orchestrator.agents.keys()),
                "agent_count": len(orchestrator.agents),
                "llm_stats": router.get_stats(),
                "event_bus": orchestrator.bus.stats(),
            }
            return {"content": [{"type": "text", "text": json.dumps(status, default=str)}]}

        elif name == "amrit_llm":
            from llm_router import LLMRouter
            router = LLMRouter()
            result = await router.complete(
                prompt=args["prompt"],
                system=args.get("system", ""),
                model=args.get("model"),
                max_tokens=args.get("max_tokens", 400),
            )
            return {"content": [{"type": "text", "text": result}]}

        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

    except Exception as e:
        logger.error(f"MCP tool error [{name}]: {e}")
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}


# ─── MCP Protocol Handler ───────────────────────────────────────


class MCPServer:
    """
    Lightweight MCP server — JSON-RPC 2.0 over stdio.
    No frameworks. Pure asyncio + json.
    """

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.tools = []
        self._initialized = False

    async def initialize(self, orchestrator):
        """Late init with orchestrator (after agents loaded)."""
        self.orchestrator = orchestrator
        self.tools = _build_tools(orchestrator)
        self._initialized = True

    def _response(self, id, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": id, "result": result}

    def _error(self, id, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}

    async def handle_message(self, msg: dict) -> Optional[dict]:
        """Handle a single JSON-RPC message."""
        method = msg.get("method", "")
        id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            return self._response(id, {
                "protocolVersion": MCP_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "amrit-godmode",
                    "version": "3.0.0",
                },
            })

        elif method == "notifications/initialized":
            logger.info("🔌 MCP client connected")
            return None  # notification, no response

        elif method == "tools/list":
            return self._response(id, {
                "tools": self.tools,
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            logger.info(f"🔧 MCP tool call: {tool_name}")
            result = await _execute_tool(tool_name, arguments, self.orchestrator)
            return self._response(id, result)

        elif method == "ping":
            return self._response(id, {})

        else:
            return self._error(id, -32601, f"Method not found: {method}")

    async def run_stdio(self):
        """Run MCP server over stdio (for Claude Code integration)."""
        logger.info("🔌 AMRIT MCP Server starting (stdio)...")
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                msg = json.loads(line)
                response = await self.handle_message(msg)

                if response:
                    out = json.dumps(response) + "\n"
                    writer.write(out.encode("utf-8"))
                    await writer.drain()

            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"MCP error: {e}")
                continue

    async def run_sse(self, host: str = "127.0.0.1", port: int = 3900):
        """
        Run MCP server over SSE (HTTP) for remote/web integration.
        Lightweight: pure asyncio, no aiohttp/flask.
        """
        logger.info(f"🔌 AMRIT MCP Server starting (SSE) on {host}:{port}")

        async def handle_client(reader, writer):
            try:
                # Read HTTP request
                request_data = b""
                while True:
                    chunk = await reader.read(4096)
                    request_data += chunk
                    if b"\r\n\r\n" in request_data:
                        break
                    if not chunk:
                        break

                request_text = request_data.decode("utf-8", errors="ignore")
                lines = request_text.split("\r\n")
                method_line = lines[0] if lines else ""

                if "POST" in method_line:
                    # Extract body
                    body = ""
                    if "\r\n\r\n" in request_text:
                        body = request_text.split("\r\n\r\n", 1)[1]

                    if body:
                        msg = json.loads(body)
                        response = await self.handle_message(msg)
                        response_json = json.dumps(response) if response else "{}"

                        http_response = (
                            "HTTP/1.1 200 OK\r\n"
                            "Content-Type: application/json\r\n"
                            "Access-Control-Allow-Origin: *\r\n"
                            f"Content-Length: {len(response_json)}\r\n"
                            "\r\n"
                            f"{response_json}"
                        )
                        writer.write(http_response.encode())
                        await writer.drain()

                elif "OPTIONS" in method_line:
                    # CORS preflight
                    http_response = (
                        "HTTP/1.1 204 No Content\r\n"
                        "Access-Control-Allow-Origin: *\r\n"
                        "Access-Control-Allow-Methods: POST, OPTIONS\r\n"
                        "Access-Control-Allow-Headers: Content-Type\r\n"
                        "\r\n"
                    )
                    writer.write(http_response.encode())
                    await writer.drain()

                else:
                    # Health check
                    body = json.dumps({"status": "ok", "server": "amrit-godmode-mcp", "version": "3.0.0"})
                    http_response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "\r\n"
                        f"{body}"
                    )
                    writer.write(http_response.encode())
                    await writer.drain()

            except Exception as e:
                logger.error(f"SSE client error: {e}")
            finally:
                writer.close()

        server = await asyncio.start_server(handle_client, host, port)
        logger.info(f"🔌 MCP SSE ready: http://{host}:{port}")
        async with server:
            await server.serve_forever()


# ─── CLI Entry Point ─────────────────────────────────────────────

async def start_mcp_server(mode: str = "stdio"):
    """Start MCP server (called from main.py)."""
    from event_bus import EventBus
    from orchestrator import Orchestrator

    bus = EventBus()
    orch = Orchestrator(bus)
    await orch.initialize()

    server = MCPServer()
    await server.initialize(orch)

    if mode == "sse":
        await server.run_sse()
    else:
        await server.run_stdio()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    asyncio.run(start_mcp_server(mode))
