
Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Uses the official MCP Python client (ClientSession) for proper session management.
Provides centralized access to all MCP tools across different servers,
with automatic discovery and categorization.
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
    
    Handles session initialization, tool discovery, and tool execution
    using the Model Context Protocol (MCP) official SDK.
    
    @attribute sessions: Dictionary of MCP ClientSession instances for each category
    @attribute tools: Dictionary mapping category to list of available tools
    @attribute loop: Asyncio event loop for managing async operations
    """
    
    def __init__(self):
        """
        Initializes the MCP registry and connects to all configured servers.
        
        Creates a dedicated event loop for async MCP operations.
        
        @throws Exception: If connection to MCP servers fails
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
        time.sleep(0.1)
        
        self._initialize_sync()
    
    def _run_event_loop(self):
        """Runs the asyncio event loop in a background thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def _initialize_sync(self):
        """
        Initializes all MCP clients synchronously using the event loop.
        """
        if not Config.MCP_SERVERS:
            print("[MCP] No MCP servers configured")
            return
        
        for category, url in Config.MCP_SERVERS.items():
            try:
                coro = self._initialize_server(category, url)
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                future.result()
            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.sessions[category] = None
                self.tools[category] = []
    
    async def _initialize_server(self, category: str, url: str):
        """
        Initializes a single MCP server connection asynchronously.
        
        @param category: The category name for this server
        @param url: The URL of the MCP server
        """
        try:
            mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
            
            async with streamablehttp_client(mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
                    
                    self.sessions[category] = session
                    self.tools[category] = [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "inputSchema": dict(tool.inputSchema) if tool.inputSchema else {}
                        }
                        for tool in tools_result.tools
                    ]
                    print(f"[MCP/{category}] Successfully loaded {len(self.tools[category])} tools")
                    
        except Exception as e:
            print(f"[MCP/{category}] Error: {e}")
            self.sessions[category] = None
            self.tools[category] = []
    
    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        """
        Finds a tool by its name across all MCP servers.
        
        @param tool_name: The name of the tool to find
        @return: Tuple of (category, tool_dict) if found, None otherwise
        """
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None
    
    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a specific tool on an MCP server.
        
        @param category: The category/namespace of the MCP server
        @param tool_name: The name of the tool to call
        @param arguments: Dictionary of arguments for the tool
        @return: Dictionary containing the tool response or error
        """
        if category not in self.sessions or not self.sessions[category]:
            return {"error": f"MCP server {category} not available"}
        
        try:
            session = self.sessions[category]
            
            async def _call_tool():
                result = await session.call_tool(tool_name, arguments)
                content_list = []
                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            content_list.append({"type": "text", "text": item.text})
                        elif isinstance(item, dict):
                            content_list.append(item)
                        else:
                            content_list.append({"type": "text", "text": str(item)})
                return {"content": content_list} if content_list else {}
            
            coro = _call_tool()
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=Config.MCP_TIMEOUT)
            
        except Exception as e:
            return {"error": str(e)}
    
    def close_all(self):
        """
        Closes all MCP client connections.
        """
        for category, session in self.sessions.items():
            if session:
                try:
                    async def _close():
                        await session.aclose()
                    
                    coro = _close()
                    future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                    future.result(timeout=5)
                except:
                    pass
        
        self.loop.call_soon_threadsafe(self.loop.stop)
=======
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP REGISTRY MODULE
===================

Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Provides centralized access to all MCP tools across different servers,
with automatic discovery and categorization.
"""

import httpx
from typing import Optional, List, Dict, Any, Tuple
from agent.config import Config


class MCPRegistry:
    """
    Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
    
    Provides centralized access to all MCP tools across different servers,
    with automatic discovery and categorization.
    
    @attribute clients: Dictionary of HTTP clients for each MCP server category
    @attribute tools: Dictionary mapping category to list of available tools
    """
    
    def __init__(self):
        """
        Initializes the MCP registry and connects to all configured servers.
        
        @throws Exception: If connection to MCP servers fails
        """
        self.clients = {}
        self.tools = {}
        self._initialize()
    
    def _initialize(self):
        """
        Initializes HTTP clients for each MCP server and loads available tools.
        Uses MCP JSON-RPC protocol (tools/list) as per official specification.
        
        @throws Exception: If connection to any MCP server fails
        """
        if not Config.MCP_SERVERS:
            print("[MCP] No MCP servers configured")
            return
        
        for category, url in Config.MCP_SERVERS.items():
            try:
                mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
                client = httpx.Client(base_url=mcp_url, timeout=Config.MCP_TIMEOUT)
                
                response = client.post(
                    "/",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/list",
                        "params": {}
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                self.clients[category] = client
                self.tools[category] = data.get("result", {}).get("tools", [])
                print(f"[MCP/{category}] Successfully loaded {len(self.tools[category])} tools")
                
            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.clients[category] = None
                self.tools[category] = []
    
    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        """
        Finds a tool by its name across all MCP servers.
        
        @param tool_name: The name of the tool to find
        @return: Tuple of (category, tool_dict) if found, None otherwise
        """
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None
    
    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a specific tool on an MCP server using JSON-RPC protocol.
        
        @param category: The category/namespace of the MCP server
        @param tool_name: The name of the tool to call
        @param arguments: Dictionary of arguments for the tool
        @return: Dictionary containing the tool response or error
        """
        if category not in self.clients or not self.clients[category]:
            return {"error": f"MCP server {category} not available"}
        
        try:
            client = self.clients[category]
            
            response = client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                },
                timeout=Config.MCP_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            if "result" in data and "content" in data["result"]:
                return {"content": data["result"]["content"]}
            return data
            
        except Exception as e:
            return {"error": str(e)}
    
    def close_all(self):
        """
        Closes all HTTP client connections.
        """
        for client in self.clients.values():
            if client:
                client.close()
===================

Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Uses the official MCP Python client (ClientSession) for proper session management.
Provides centralized access to all MCP tools across different servers,
with automatic discovery and categorization.
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
    
    Handles session initialization, tool discovery, and tool execution
    using the Model Context Protocol (MCP) official SDK.
    
    @attribute sessions: Dictionary of MCP ClientSession instances for each category
    @attribute tools: Dictionary mapping category to list of available tools
    @attribute loop: Asyncio event loop for managing async operations
    """
    
    def __init__(self):
        """
        Initializes the MCP registry and connects to all configured servers.
        
        Creates a dedicated event loop for async MCP operations.
        
        @throws Exception: If connection to MCP servers fails
        """
        self.sessions: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
        time.sleep(0.1)
        
        self._initialize_sync()
    
    def _run_event_loop(self):
        """Runs the asyncio event loop in a background thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def _initialize_sync(self):
        """
        Initializes all MCP clients synchronously using the event loop.
        """
        if not Config.MCP_SERVERS:
            print("[MCP] No MCP servers configured")
            return
        
        for category, url in Config.MCP_SERVERS.items():
            try:
                coro = self._initialize_server(category, url)
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                future.result()
            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.sessions[category] = None
                self.tools[category] = []
    
    async def _initialize_server(self, category: str, url: str):
        """
        Initializes a single MCP server connection asynchronously.
        
        @param category: The category name for this server
        @param url: The URL of the MCP server
        """
        try:
            mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
            
            async with streamablehttp_client(mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
                    
                    self.sessions[category] = session
                    self.tools[category] = [
                        {
                            "name": tool.name,
                            "description": tool.description or "",
                            "inputSchema": dict(tool.inputSchema) if tool.inputSchema else {}
                        }
                        for tool in tools_result.tools
                    ]
                    print(f"[MCP/{category}] Successfully loaded {len(self.tools[category])} tools")
                    
        except Exception as e:
            print(f"[MCP/{category}] Error: {e}")
            self.sessions[category] = None
            self.tools[category] = []
    
    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        """
        Finds a tool by its name across all MCP servers.
        
        @param tool_name: The name of the tool to find
        @return: Tuple of (category, tool_dict) if found, None otherwise
        """
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None
    
    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a specific tool on an MCP server.
        
        @param category: The category/namespace of the MCP server
        @param tool_name: The name of the tool to call
        @param arguments: Dictionary of arguments for the tool
        @return: Dictionary containing the tool response or error
        """
        if category not in self.sessions or not self.sessions[category]:
            return {"error": f"MCP server {category} not available"}
        
        try:
            session = self.sessions[category]
            
            async def _call_tool():
                result = await session.call_tool(tool_name, arguments)
                content_list = []
                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            content_list.append({"type": "text", "text": item.text})
                        elif isinstance(item, dict):
                            content_list.append(item)
                        else:
                            content_list.append({"type": "text", "text": str(item)})
                return {"content": content_list} if content_list else {}
            
            coro = _call_tool()
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=Config.MCP_TIMEOUT)
            
        except Exception as e:
            return {"error": str(e)}
    
    def close_all(self):
        """
        Closes all MCP client connections.
        """
        for category, session in self.sessions.items():
            if session:
                try:
                    async def _close():
                        await session.aclose()
                    
                    coro = _close()
                    future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                    future.result(timeout=5)
                except:
                    pass
        
        self.loop.call_soon_threadsafe(self.loop.stop)
