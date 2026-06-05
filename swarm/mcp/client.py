import asyncio
import json
import subprocess
from typing import Any, Optional

import httpx


class MCPClient:
    """Client for Model Context Protocol servers.
    
    Supports both stdio (subprocess) and HTTP/sse transports.
    """

    def __init__(self, server_name: str, transport: str = "stdio"):
        self.server_name = server_name
        self.transport = transport
        self._process: Optional[asyncio.subprocess.Process] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._url: Optional[str] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect_stdio(self, command: str, args: list = None, env: dict = None):
        args = args or []
        env_full = {**subprocess._clean_environ(), **(env or {})}
        self._process = await asyncio.create_subprocess_exec(
            command, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env_full if env else None,
        )
        self._connected = True
        self._read_task = asyncio.create_task(self._read_loop_stdio())

    async def connect_http(self, url: str):
        self._url = url.rstrip("/")
        self._http_client = httpx.AsyncClient(timeout=60.0)
        self._connected = True

    async def _read_loop_stdio(self):
        buffer = b""
        while self._process and self._process.stdout:
            try:
                chunk = await self._process.stdout.read(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if line_str:
                        try:
                            msg = json.loads(line_str)
                            self._handle_message(msg)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                break

    def _handle_message(self, msg: dict):
        msg_id = msg.get("id")
        if msg_id is not None and msg_id in self._pending:
            future = self._pending.pop(msg_id)
            if not future.done():
                if "error" in msg:
                    future.set_exception(RuntimeError(msg["error"].get("message", str(msg["error"]))))
                else:
                    future.set_result(msg.get("result", {}))

    async def _send_request(self, method: str, params: dict = None) -> dict:
        self._request_id += 1
        req_id = self._request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        if self.transport == "stdio":
            if self._process and self._process.stdin:
                line = json.dumps(request) + "\n"
                self._process.stdin.write(line.encode("utf-8"))
                await self._process.stdin.drain()
        elif self._http_client and self._url:
            resp = await self._http_client.post(
                f"{self._url}/mcp",
                json=request,
            )
            resp.raise_for_status()
            data = resp.json()
            self._handle_message(data)
        else:
            raise RuntimeError("MCP client not connected")

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"MCP request {method} timed out")

    async def list_tools(self) -> list[dict]:
        result = await self._send_request("tools/list")
        return result.get("tools", [])

    async def call_tool(self, name: str, arguments: dict = None) -> Any:
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        content = result.get("content", [])
        text_parts = []
        for c in content:
            if isinstance(c, dict):
                text_parts.append(c.get("text", json.dumps(c)))
            else:
                text_parts.append(str(c))
        return "\n".join(text_parts)

    async def list_resources(self) -> list[dict]:
        result = await self._send_request("resources/list")
        return result.get("resources", [])

    async def read_resource(self, uri: str) -> Any:
        result = await self._send_request("resources/read", {"uri": uri})
        return result.get("contents", [])

    async def close(self):
        self._connected = False
        if self._read_task:
            self._read_task.cancel()
            self._read_task = None
        if self._process:
            try:
                self._process.kill()
                await self._process.wait()
            except Exception:
                pass
            self._process = None
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    @property
    def is_connected(self) -> bool:
        return self._connected


class MCPManager:
    """Manages multiple MCP server connections and exposes their tools."""

    def __init__(self):
        self._clients: dict[str, MCPClient] = {}
        self._tool_map: dict[str, tuple[str, str]] = {}  # tool_name -> (server_name, original_tool_name)

    async def connect_server(self, name: str, transport: str, command: str = None,
                             args: list = None, url: str = None, env: dict = None):
        client = MCPClient(name, transport=transport)
        if transport == "stdio":
            await client.connect_stdio(command, args, env)
        elif transport in ("http", "sse", "http+sse"):
            await client.connect_http(url or command)
        else:
            raise ValueError(f"Unknown MCP transport: {transport}")
        self._clients[name] = client
        return client

    async def discover_tools(self) -> list[dict]:
        all_tools = []
        self._tool_map.clear()
        for name, client in self._clients.items():
            try:
                tools = await client.list_tools()
                for t in tools:
                    tool_name = t.get("name", "")
                    prefixed = f"mcp__{name}__{tool_name}"
                    self._tool_map[prefixed] = (name, tool_name)
                    t["_prefixed_name"] = prefixed
                    t["_server"] = name
                    all_tools.append(t)
            except Exception as e:
                pass
        return all_tools

    def get_server_for_tool(self, prefixed_name: str) -> Optional[tuple[str, str]]:
        return self._tool_map.get(prefixed_name)

    async def call_tool(self, prefixed_name: str, arguments: dict = None) -> str:
        server_info = self._tool_map.get(prefixed_name)
        if not server_info:
            raise ValueError(f"Unknown MCP tool: {prefixed_name}")
        server_name, original_name = server_info
        client = self._clients.get(server_name)
        if not client:
            raise ValueError(f"MCP server '{server_name}' not connected")
        return await client.call_tool(original_name, arguments)

    async def close_all(self):
        for client in self._clients.values():
            await client.close()
        self._clients.clear()
        self._tool_map.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close_all()
