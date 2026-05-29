#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP REGISTRY MODULE
===================

Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Uses the official MCP Python client for proper session management.
"""

import asyncio
import threading
import time
from typing import Optional, List, Dict, Any, Tuple
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from agent.config import Config

class MCPRegistry:
    """
    Manages multiple MCP servers using the official MCP ClientSession.

    @attribute sessions: Dictionary of MCP ClientSession instances
    @attribute tools: Dictionary mapping category to list of available tools
    @attribute loop: Asyncio event loop for async operations
    @attribute streams: Dictionary to keep streams alive
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        self.streams: Dict[str, Tuple] = {}
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        time.sleep(0.1)
        self._initialize_sync()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _initialize_sync(self):
        if not Config.MCP_SERVERS:
            print("[MCP] No MCP servers configured")
            return

        for category, url in Config.MCP_SERVERS.items():
            try:
                coro = self._init_server(category, url)
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                future.result()
            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.sessions[category] = None
                self.tools[category] = []

    async def _init_server(self, category: str, url: str):
        try:
            mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
            read, write, close_fn = await streamablehttp_client(mcp_url)
            session = ClientSession(read, write)
            await session.initialize()
            tools = await session.list_tools()

            self.streams[category] = (read, write, close_fn)
            self.sessions[category] = session
            self.tools[category] = [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "inputSchema": dict(t.inputSchema) if t.inputSchema else {}
                }
                for t in tools.tools
            ]
            print(f"[MCP/{category}] Loaded {len(self.tools[category])} tools")
        except Exception as e:
            print(f"[MCP/{category}] Error: {e}")
            self.sessions[category] = None
            self.tools[category] = []

    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None

    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if category not in self.sessions or not self.sessions[category]:
            return {"error": f"MCP server {category} not available"}

        try:
            session = self.sessions[category]
            async def _call():
                result = await session.call_tool(tool_name, arguments)
                content = []
                for item in result.content:
                    if hasattr(item, 'text'):
                        content.append({"type": "text", "text": item.text})
                    else:
                        content.append({"type": "text", "text": str(item)})
                return {"content": content} if content else {}
            future = asyncio.run_coroutine_threadsafe(_call(), self.loop)
            return future.result(timeout=Config.MCP_TIMEOUT)
        except Exception as e:
            return {"error": str(e)}

    def close_all(self):
        for category, (read, write, close_fn) in self.streams.items():
            if close_fn:
                try:
                    asyncio.run_coroutine_threadsafe(close_fn(), self.loop).result(timeout=5)
                except:
                    pass
        self.streams.clear()
        self.sessions.clear()
        self.loop.call_soon_threadsafe(self.loop.stop)