#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP REGISTRY MODULE
===================

Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Uses the official MCP Python client for proper session management.
Provides centralized access to all MCP tools across different servers,
with automatic discovery and categorization.
"""

import asyncio
import threading
import time
from typing import Optional, List, Dict, Any, Tuple
from mcp import Client
from agent.config import Config


class MCPRegistry:
    """
    Manages multiple MCP servers using the official MCP Python client.
    
    Handles session initialization, tool discovery, and tool execution
    using the Model Context Protocol (MCP) official SDK.
    
    @attribute clients: Dictionary of MCP Client instances for each category
    @attribute tools: Dictionary mapping category to list of available tools
    @attribute loop: Asyncio event loop for managing async operations
    """
    
    def __init__(self):
        """
        Initializes the MCP registry and connects to all configured servers.
        
        Creates a dedicated event loop for async MCP operations.
        
        @throws Exception: If connection to MCP servers fails
        """
        self.clients: Dict[str, Client] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        
        # Create dedicated event loop for MCP async operations
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        
        # Give the event loop a moment to start
        time.sleep(0.1)
        
        # Initialize all configured MCP servers
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
                # Create a coroutine for initialization
                coro = self._initialize_server(category, url)
                future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                future.result()  # Block until complete
            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.clients[category] = None
                self.tools[category] = []
    
    async def _initialize_server(self, category: str, url: str):
        """
        Initializes a single MCP server connection asynchronously.
        
        @param category: The category name for this server
        @param url: The URL of the MCP server
        """
        try:
            # Create client and initialize session
            client = Client(url=url)
            await client.initialize()
            
            # List available tools
            tools = await client.list_tools()
            
            self.clients[category] = client
            self.tools[category] = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema or {}
                }
                for tool in tools
            ]
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
        Calls a specific tool on an MCP server.
        
        @param category: The category/namespace of the MCP server
        @param tool_name: The name of the tool to call
        @param arguments: Dictionary of arguments for the tool
        @return: Dictionary containing the tool response or error
        """
        if category not in self.clients or not self.clients[category]:
            return {"error": f"MCP server {category} not available"}
        
        try:
            client = self.clients[category]
            coro = client.call_tool(tool_name, arguments)
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            result = future.result(timeout=Config.MCP_TIMEOUT)
            
            # Convert MCP ToolResult to dict
            return {
                "content": [
                    {"type": "text", "text": str(content)}
                    if hasattr(content, 'text') else content
                    for content in result.content
                ] if hasattr(result, 'content') else {}
            }
        except Exception as e:
            return {"error": str(e)}
    
    def close_all(self):
        """
        Closes all MCP client connections.
        """
        for category, client in self.clients.items():
            if client:
                try:
                    # Close client asynchronously
                    coro = client.close()
                    future = asyncio.run_coroutine_threadsafe(coro, self.loop)
                    future.result(timeout=5)
                except:
                    pass
        
        # Stop the event loop thread
        self.loop.call_soon_threadsafe(self.loop.stop)
