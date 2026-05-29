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
