#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Registry module.

Manages multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).
Provides centralized access to all MCP tools across different servers,
with automatic discovery and categorization.
"""

import httpx
from typing import Optional, List, Dict, Any, Tuple
from agent.config import Config


class MCPRegistry:
    """
    Manages multiple MCP servers and provides centralized tool access.

    Handles the full MCP Streamable HTTP lifecycle: initialize handshake,
    session management, tool discovery, and tool invocation across
    multiple categorized MCP servers.

    @attribute clients: HTTP clients keyed by server category.
    @attribute session_ids: Mcp-Session-Id values keyed by server category.
    @attribute tools: Available tools keyed by server category.
    """

    def __init__(self):
        """
        Initializes the registry and connects to all configured MCP servers.

        @throws Exception: If the connection or handshake fails for any server.
        """
        self.clients: Dict[str, httpx.Client] = {}
        self.session_ids: Dict[str, Optional[str]] = {}
        self.tools: Dict[str, List[Dict]] = {}
        self._req_id = 0
        self._initialize()

    def _next_id(self) -> int:
        """
        Returns the next monotonically increasing JSON-RPC request ID.

        @return: Integer request ID.
        """
        self._req_id += 1
        return self._req_id

    def _mcp_headers(self, category: str) -> Dict[str, str]:
        """
        Builds the HTTP headers required for a MCP Streamable HTTP request.

        Includes the Mcp-Session-Id header when a session has been established,
        and an Accept header that allows both JSON and SSE responses.

        @param category: Server category used to look up the current session ID.
        @return: Dictionary of HTTP headers.
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        session_id = self.session_ids.get(category)
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    def _post(self, category: str, payload: Dict) -> Dict[str, Any]:
        """
        Sends a JSON-RPC request to the MCP server using Streamable HTTP transport.

        Persists the Mcp-Session-Id from the response headers if present.

        @param category: Server category identifying which client to use.
        @param payload: JSON-RPC request body.
        @return: Parsed JSON response body.
        @throws httpx.HTTPStatusError: If the server returns a non-2xx status code.
        """
        client = self.clients[category]
        response = client.post(
            "/mcp",
            json=payload,
            headers=self._mcp_headers(category),
            timeout=Config.MCP_TIMEOUT,
        )
        response.raise_for_status()

        new_session_id = response.headers.get("Mcp-Session-Id")
        if new_session_id:
            self.session_ids[category] = new_session_id

        return response.json()

    def _notify(self, category: str, method: str, params: Dict | None = None):
        """
        Sends a JSON-RPC notification to the MCP server.

        Notifications do not expect a response. Errors are silently ignored
        to avoid disrupting the initialization flow.

        @param category: Server category identifying which client to use.
        @param method: JSON-RPC notification method name.
        @param params: Optional parameters for the notification.
        """
        client = self.clients[category]
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            **({"params": params} if params else {}),
        }
        try:
            client.post(
                "/mcp",
                json=payload,
                headers=self._mcp_headers(category),
                timeout=Config.MCP_TIMEOUT,
            )
        except Exception:
            pass

    def _initialize(self):
        """
        Initializes an HTTP client for each configured MCP server.

        For each server, performs the mandatory MCP handshake sequence:
        sends an initialize request, then a notifications/initialized notification,
        and finally loads the available tools via tools/list.

        @throws Exception: If the handshake or tool discovery fails for a server.
        """
        if not Config.MCP_SERVERS:
            print("[MCP] No MCP servers configured")
            return

        for category, url in Config.MCP_SERVERS.items():
            try:
                client = httpx.Client(base_url=url, timeout=Config.MCP_TIMEOUT)
                self.clients[category] = client
                self.session_ids[category] = None

                self._post(category, {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"roots": {"listChanged": False}},
                        "clientInfo": {"name": "mcp-registry", "version": "1.0.0"},
                    },
                })

                self._notify(category, "notifications/initialized")

                data = self._post(category, {
                    "jsonrpc": "2.0",
                    "id": self._next_id(),
                    "method": "tools/list",
                    "params": {},
                })
                self.tools[category] = data.get("result", {}).get("tools", [])
                print(f"[MCP/{category}] {len(self.tools[category])} tools loaded "
                      f"(session: {self.session_ids.get(category) or 'stateless'})")

            except Exception as e:
                print(f"[MCP/{category}] Error: {e}")
                self.clients[category] = None
                self.session_ids[category] = None
                self.tools[category] = []

    def get_tool(self, tool_name: str) -> Optional[Tuple[str, Dict]]:
        """
        Finds a tool by name across all registered MCP servers.

        @param tool_name: The name of the tool to find.
        @return: Tuple of (category, tool_dict) if found, None otherwise.
        """
        for category, tools in self.tools.items():
            for tool in tools:
                if tool.get("name") == tool_name:
                    return (category, tool)
        return None

    def call_tool(self, category: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes a tool on the specified MCP server using Streamable HTTP transport.

        @param category: Server category identifying which MCP server to call.
        @param tool_name: Name of the tool to invoke.
        @param arguments: Arguments to pass to the tool.
        @return: Dictionary containing the tool result under the "content" key,
                 or an "error" key if the call failed.
        """
        if category not in self.clients or not self.clients[category]:
            return {"error": f"MCP server '{category}' not available"}

        try:
            data = self._post(category, {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            })

            if "error" in data:
                return {"error": data["error"]}

            result = data.get("result", {})
            if "content" in result:
                return {"content": result["content"]}
            return result

        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def close_all(self):
        """
        Closes all HTTP client connections.

        Sends a DELETE request to /mcp to explicitly terminate the server-side
        session before closing the underlying HTTP client, when a session ID exists.
        """
        for category, client in self.clients.items():
            if not client:
                continue
            session_id = self.session_ids.get(category)
            if session_id:
                try:
                    client.delete(
                        "/mcp",
                        headers={"Mcp-Session-Id": session_id},
                        timeout=5.0,
                    )
                except Exception:
                    pass
            client.close()