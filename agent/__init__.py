#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGENT PACKAGE
=============

Cluster Diagnostic Agent - Main package.

This package contains the multi-step diagnostic agent for infrastructure
monitoring and troubleshooting (Kubernetes, OpenSearch, Redis, Kafka).

Structure:
- config.py: Configuration settings
- models.py: Data models (DocumentationMatch, DiagnosticReport)
- clients/: Client implementations
  - mcp_registry.py: MCP server management
  - qdrant_client.py: Qdrant vector search
  - llm_client.py: LLM (Gemma4) integration
- diagnostic_agent.py: Main diagnostic agent
"""

from .config import Config
from .models import DocumentationMatch, DiagnosticReport
from .clients.mcp_registry import MCPRegistry
from .clients.qdrant_client import QdrantDiagnostic
from .clients.llm_client import LLMAPI
from .diagnostic_agent import DiagnosticAgent

__all__ = [
    'Config',
    'DocumentationMatch',
    'DiagnosticReport',
    'MCPRegistry',
    'QdrantDiagnostic',
    'LLMAPI',
    'DiagnosticAgent',
]

__version__ = "1.0.0"
