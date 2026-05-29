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
from mcp.client.streamable_http import streamable_http_client
from agent.config import Config


class MCPRegistry:
    """
    Manages multiple MCP servers using the official MCP ClientSession.

    @attribute sessions: Dictionary of MCP ClientSession instances
    @attribute tools: Dictionary mapping category to list of available tools
    @attribute loop: Asyncio event loop for async operations
    @attribute _ready_events: Per-category events signaling session readiness
    @attribute _stop_events: Per-category events signaling session teardown
    """

    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        self._ready_events: Dict[str, asyncio.Event] = {}
        self._stop_events: Dict[str, asyncio.Event] = {}
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

        futures = []
        for category, url in Config.MCP_SERVERS.items():
            # Create events in the background loop to avoid cross-loop issues
            ready_event = asyncio.Event()
            stop_event = asyncio.Event()

            future_ready = asyncio.run_coroutine_threadsafe(
                self._create_event(), self.loop
            )
            future_stop = asyncio.run_coroutine_threadsafe(
                self._create_event(), self.loop
            )
            self._ready_events[category] = future_ready.result(timeout=5)
            self._stop_events[category] = future_stop.result(timeout=5)

            asyncio.run_coroutine_threadsafe(
                self._run_server_session(category, url),
                self.loop
            )

        # Wait for all sessions to be ready (or failed)
        for category in Config.MCP_SERVERS:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._wait_ready(category), self.loop
                )
                future.result(timeout=15)
            except Exception as e:
                print(f"[MCP/{category}] Timeout or error waiting for session: {e}")

    @staticmethod
    async def _create_event() -> asyncio.Event:
        return asyncio.Event()

    async def _wait_ready(self, category: str):
        await asyncio.wait_for(self._ready_events[category].wait(), timeout=10)

    async def _run_server_session(self, category: str, url: str):
        """
        Holds the session open for the lifetime of the registry.
        Signals _ready_events[category] once the session is initialized.
        """
        mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
        try:
            async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()

                    self.sessions[category] = session
                    self.tools[category] = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": dict(t.inputSchema) if t.inputSchema else {}
                        }
                        for t in tools_result.tools
                    ]
                    print(f"[MCP/{category}] Loaded {len(self.tools[category])} tools")
                    self._ready_events[category].set()

                    # Keep the session alive until stop is requested
                    await self._stop_events[category].wait()

        except Exception as e:
            print(f"[MCP/{category}] Error: {e}")
            self.sessions[category] = None
            self.tools[category] = []
            self._ready_events[category].set()  # Unblock _initialize_sync

    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None

    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if category not in self.sessions or not self.sessions[category]:
            return {"error": f"MCP server {category} not available"}

        async def _call():
            result = await self.sessions[category].call_tool(tool_name, arguments)
            content = []
            for item in result.content:
                if hasattr(item, "text"):
                    content.append({"type": "text", "text": item.text})
                else:
                    content.append({"type": "text", "text": str(item)})
            return {"content": content} if content else {}

        try:
            future = asyncio.run_coroutine_threadsafe(_call(), self.loop)
            return future.result(timeout=Config.MCP_TIMEOUT)
        except Exception as e:
            return {"error": str(e)}

    def close_all(self):
        for category, stop_event in self._stop_events.items():
            asyncio.run_coroutine_threadsafe(
                self._set_event(stop_event), self.loop
            ).result(timeout=5)
        self.sessions.clear()
        self.loop.call_soon_threadsafe(self.loop.stop)

    @staticmethod
    async def _set_event(event: asyncio.Event):
        event.set()