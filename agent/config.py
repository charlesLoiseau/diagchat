#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONFIGURATION MODULE
=====================

Centralized configuration for the diagnostic agent.
Loads settings from environment variables with fallback to defaults.
"""

import os
from typing import Dict, Any


class Config:
    """
    Configuration class for the diagnostic agent.
    
    Contains all configurable parameters for MCP servers, LLM, and Qdrant.
    Settings are loaded from environment variables with fallback to defaults.
    
    Environment Variables:
    - LLM_URL: URL for the LLM (Gemma4) API endpoint
    - LLM_API_KEY: Bearer token for LLM API authentication
    - LLM_TIMEOUT: Timeout for LLM requests in seconds
    - MCP_KUBERNETES_URL: Kubernetes MCP server URL
    - MCP_OPENSEARCH_URL: OpenSearch MCP server URL
    - MCP_REDIS_URL: Redis MCP server URL
    - MCP_KAFKA_URL: Kafka MCP server URL
    - MCP_TIMEOUT: Timeout for MCP requests in seconds
    - QDRANT_HOST: Qdrant server hostname
    - QDRANT_PORT: Qdrant server port
    - QDRANT_COLLECTION: Default Qdrant collection name
    - QDRANT_TIMEOUT: Timeout for Qdrant requests in seconds
    - API_AUTH_TOKEN: Bearer token for API endpoints (optional)
    
    @attribute MCP_SERVERS: Dictionary mapping category names to MCP server URLs
    @attribute LLM_URL: URL for the LLM (Gemma4) API endpoint
    @attribute LLM_API_KEY: Bearer token for LLM API authentication
    @attribute QDRANT_HOST: Qdrant server hostname
    @attribute QDRANT_PORT: Qdrant server port
    @attribute QDRANT_COLLECTION: Default Qdrant collection name
    @attribute MCP_TIMEOUT: Timeout for MCP requests in seconds
    @attribute LLM_TIMEOUT: Timeout for LLM requests in seconds
    @attribute QDRANT_TIMEOUT: Timeout for Qdrant requests in seconds
    @attribute API_AUTH_TOKEN: Bearer token for API endpoints (optional)
    """
    
    # LLM Configuration
    LLM_URL: str = os.getenv("LLM_URL", "http://localhost:8080/v1/chat/completions")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))
    
    # MCP Servers Configuration
    MCP_SERVERS: Dict[str, str] = {
        "kubernetes": os.getenv("MCP_KUBERNETES_URL", "http://localhost:8090"),
        "opensearch": os.getenv("MCP_OPENSEARCH_URL", "http://localhost:8091"),
        "redis": os.getenv("MCP_REDIS_URL", "http://localhost:8092"),
        "kafka": os.getenv("MCP_KAFKA_URL", "http://localhost:8093")
    }
    MCP_TIMEOUT: float = float(os.getenv("MCP_TIMEOUT", "10.0"))
    
    # Qdrant Configuration
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "8000"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "documentation")
    QDRANT_TIMEOUT: float = float(os.getenv("QDRANT_TIMEOUT", "15.0"))
    
    # API Security Configuration
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
