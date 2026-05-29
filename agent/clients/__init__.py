#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLIENTS PACKAGE
===============

Contains all client implementations for external services:
- mcp_registry.py: MCP server management
- qdrant_client.py: Qdrant vector search
- llm_client.py: LLM (Gemma4) integration
"""

from .mcp_registry import MCPRegistry
from .qdrant_client import QdrantDiagnostic
from .llm_client import LLMAPI

__all__ = ['MCPRegistry', 'QdrantDiagnostic', 'LLMAPI']
