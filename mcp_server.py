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
from typing import Optional, Any, Dict
from logger import setup_logger
from swarm import Queen
from llm_router import LLMRouter
from event_bus import EventBus
from orchestrator import Orchestrator

logger = setup_logger("mcp")

# MCP Protocol version
MCP_VERSION = "2024-11-05"

# ─── Tool Registry ──────────────────────────────────────────────


def _build_tools(orchestrator: Any) -> list[dict]:
    """
    Build MCP tool definitions from AMRIT capabilities.
    Args:
        orchestrator: The orchestrator instance.
    Returns:
        List of tool definitions.
    """
    tool_definitions = [
        {
            "name": "amrit_goal",
            "description": "Set and execute a high-level goal. AMRIT decomposes it into tasks and runs agents.",
            "inputSchema": _create_input_schema(["goal"]),
        },
        {
            "name": "amrit_agent_run",
            "description": "Run a specific AMRIT agent with a task. Agents: coder, researcher, tester, debugger, planner, internet, vision, voice, memory, tool.",
            "inputSchema": _create_input_schema(["agent", "task"]),
        },
        {
            "name": "amrit_swarm",
            "description": "Launch a multi-agent swarm with queen/worker coordination to solve complex objectives.",
            "inputSchema": _create_input_schema(["objective"], {"tasks"}),
        },
        {
            "name": "amrit_code",
            "description": "Generate, refactor, or analyze code using AMRIT's coding agent with local LLM.",
            "inputSchema": _create_input_schema(["action"], ["code", "prompt", "language"]),
        },
        {
            "name": "amrit_research",
            "description": "Research a topic using AMRIT's internet agent + arXiv pipeline.",
            "inputSchema": _create_input_schema(["query"], ["depth"]),
        },
        {
            "name": "amrit_test",
            "description": "Run tests or generate tests for code.",
            "inputSchema": _create_input_schema(["action"], ["file", "code"]),
        },
        {
            "name": "amrit_memory_search",
            "description": "Search AMRIT's vector memory (episodic, semantic, long-term).",
            "inputSchema": _create_input_schema(["query"], ["memory_type", "limit"]),
        },
        {
            "name": "amrit_selffix",
            "description": "Run AMRIT's self-evolution engine to analyze and fix its own code.",
            "inputSchema": _create_input_schema(["max_cycles"], strict=False),
        },
        {
            "name": "amrit_status",
            "description": "Get current AMRIT system status — agents, swarm, memory, LLM stats.",
            "inputSchema": _create_input_schema([], strict=False),
        },
        {
            "name": "amrit_llm",
            "description": "Direct LLM completion using AMRIT's local models (Ollama/AirLLM). Zero API cost.",
            "inputSchema": _create_input_schema(["prompt"], ["system", "model", "max_tokens"]),
        },
    ]
    return tool_definitions


def _create_input_schema(required_fields: list[str], optional_fields: list[str] = [], strict: bool = True) -> dict:
    """
    Helper to create input schemas.
    Args:
        required_fields: List of required field names.
        optional_fields: List of optional field names.
        strict: Whether to enforce required fields.
    Returns:
        Schema dictionary.
    """
    properties = {field: {"type": "string"} for field in required_fields}
    if optional_fields:
        properties.update({field: {"type": "string"} for field in optional_fields})
    return {
        "type": "object",
        "properties": properties,
        "required": required_fields if strict else [],
    }


# ─── Tool Execution ─────────────────────────────────────────────



async def _execute_tool(name: str, args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """
    Execute an MCP tool call and return result.
    Args:
        name: Tool name.
        args: Arguments for the tool.
        orchestrator: Orchestrator instance.
    Returns:
        Result dictionary.
    """
    try:
        if name == "amrit_goal":
            return await _tool_amrit_goal(args, orchestrator)
        elif name == "amrit_agent_run":
            return await _tool_amrit_agent_run(args, orchestrator)
        elif name == "amrit_swarm":
            return await _tool_amrit_swarm(args, orchestrator)
        elif name == "amrit_code":
            return await _tool_amrit_code(args, orchestrator)
        elif name == "amrit_research":
            return await _tool_amrit_research(args, orchestrator)
        elif name == "amrit_test":
            return await _tool_amrit_test(args, orchestrator)
        elif name == "amrit_memory_search":
            return await _tool_amrit_memory_search(args, orchestrator)
        elif name == "amrit_selffix":
            return await _tool_amrit_selffix(args, orchestrator)
        elif name == "amrit_status":
            return await _tool_amrit_status(args, orchestrator)
        elif name == "amrit_llm":
            return await _tool_amrit_llm(args, orchestrator)
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    except Exception as e:
        logger.error(f"MCP tool error [{name}]: {e}")
        return {"content": [{"type": "text", "text": f"Error: {str(e)}"}], "isError": True}


# Modularized tool handlers for clarity and testability
async def _tool_amrit_goal(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_goal tool."""
    result = await orchestrator.run_goal(args["goal"])
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

async def _tool_amrit_agent_run(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_agent_run tool."""
    agent = orchestrator.get_agent(args["agent"])
    if not agent:
        return {"content": [{"type": "text", "text": f"Agent '{args['agent']}' not found"}], "isError": True}
    result = await agent.execute(args.get("task", {}))
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

async def _tool_amrit_swarm(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_swarm tool."""
    queen = Queen(orchestrator.bus, orchestrator.agents, orchestrator.state)
    tasks = args.get("tasks", [])
    if not tasks:
        planner = orchestrator.get_agent("planner")
        if planner:
            plan = await planner.execute({"name": args["objective"], "action": args["objective"]})
            tasks = plan.get("tasks", [{"name": args["objective"], "agent": "coder"}])
    result = await queen.spawn_swarm(args["objective"], tasks)
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

async def _tool_amrit_code(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_code tool."""
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

async def _tool_amrit_research(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_research tool."""
    researcher = orchestrator.get_agent("researcher")
    if researcher:
        result = await researcher.execute({
            "name": args["query"], "action": "research",
            "query": args["query"], "depth": args.get("depth", "medium"),
        })
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    return {"content": [{"type": "text", "text": "Researcher agent not available"}], "isError": True}

async def _tool_amrit_test(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_test tool."""
    tester = orchestrator.get_agent("tester")
    result = await tester.execute({
        "action": args["action"], "name": args.get("file", "test"),
        "file": args.get("file", ""), "code": args.get("code", ""),
    })
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

async def _tool_amrit_memory_search(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_memory_search tool."""
    memory = orchestrator.get_agent("memory")
    if memory:
        result = await memory.execute({
            "action": "search", "query": args["query"],
            "type": args.get("memory_type", "all"),
            "limit": args.get("limit", 5),
        })
        return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}
    return {"content": [{"type": "text", "text": "Memory agent not available"}], "isError": True}

async def _tool_amrit_selffix(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_selffix tool."""
    result = await orchestrator._run_selffix()
    return {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}

async def _tool_amrit_status(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_status tool."""
    router = LLMRouter()
    status = {
        "agents": list(orchestrator.agents.keys()),
        "agent_count": len(orchestrator.agents),
        "llm_stats": router.get_stats(),
        "event_bus": orchestrator.bus.stats(),
    }
    return {"content": [{"type": "text", "text": json.dumps(status, default=str)}]}

async def _tool_amrit_llm(args: Dict[str, Any], orchestrator: Any) -> Dict[str, Any]:
    """Handle amrit_llm tool."""
    router = LLMRouter()
    result = await router.complete(
        prompt=args["prompt"],
        system=args.get("system", ""),
        model=args.get("model"),
        max_tokens=args.get("max_tokens", 400),
    )
    return {"content": [{"type": "text", "text": result}]}


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
        """
        Run MCP server over stdio (for Claude Code integration).
        Modularized for clarity and maintainability.
        """
        logger.info("🔌 AMRIT MCP Server starting (stdio)...")
        reader, writer = await self._setup_stdio_streams()
        await self._stdio_event_loop(reader, writer)

    async def _setup_stdio_streams(self):
        """Set up asyncio streams for stdio communication."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())
        return reader, writer

    async def _stdio_event_loop(self, reader, writer):
        """Main event loop for stdio server."""
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
        Modularized for clarity and maintainability.
        """
        logger.info(f"🔌 AMRIT MCP Server starting (SSE) on {host}:{port}")
        server = await asyncio.start_server(self._handle_sse_client, host, port)
        logger.info(f"🔌 MCP SSE ready: http://{host}:{port}")
        async with server:
            await server.serve_forever()

    async def _handle_sse_client(self, reader, writer):
        """Handle a single SSE client connection."""
        try:
            request_data = await self._read_http_request(reader)
            request_text = request_data.decode("utf-8", errors="ignore")
            lines = request_text.split("\r\n")
            method_line = lines[0] if lines else ""
            if "POST" in method_line:
                await self._handle_sse_post(request_text, writer)
            elif "OPTIONS" in method_line:
                await self._handle_sse_options(writer)
            else:
                await self._handle_sse_health(writer)
        except Exception as e:
            logger.error(f"SSE client error: {e}")
        finally:
            writer.close()

    async def _read_http_request(self, reader) -> bytes:
        """Read HTTP request data from client."""
        request_data = b""
        while True:
            chunk = await reader.read(4096)
            request_data += chunk
            if b"\r\n\r\n" in request_data:
                break
            if not chunk:
                break
        return request_data

    async def _handle_sse_post(self, request_text: str, writer):
        """Handle POST request for SSE server."""
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

    async def _handle_sse_options(self, writer):
        """Handle OPTIONS (CORS preflight) request for SSE server."""
        http_response = (
            "HTTP/1.1 204 No Content\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "\r\n"
        )
        writer.write(http_response.encode())
        await writer.drain()

    async def _handle_sse_health(self, writer):
        """Handle health check request for SSE server."""
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


# ─── CLI Entry Point ─────────────────────────────────────────────

async def start_mcp_server(mode: str = "stdio"):
    """Start MCP server (called from main.py)."""

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