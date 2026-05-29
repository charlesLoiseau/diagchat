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
    - LLM_URL: URL for the OpenAI-compatible LLM API endpoint
    - LLM_API_KEY: Bearer token for LLM API authentication
    - LLM_MODEL: Model name to use for completions
    - LLM_TIMEOUT: Timeout for LLM requests in seconds
    - EMBEDDING_URL: URL for the OpenAI-compatible Embedding API endpoint
    - EMBEDDING_API_KEY: Bearer token for Embedding API authentication
    - EMBEDDING_MODEL: Model name for embeddings (e.g., bge-m3)
    - EMBEDDING_TIMEOUT: Timeout for Embedding requests in seconds
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
    @attribute LLM_URL: URL for the OpenAI-compatible LLM API endpoint
    @attribute LLM_API_KEY: Bearer token for LLM API authentication
    @attribute LLM_MODEL: Model name to use for completions
    @attribute EMBEDDING_URL: URL for the OpenAI-compatible Embedding API endpoint
    @attribute EMBEDDING_API_KEY: Bearer token for Embedding API authentication
    @attribute EMBEDDING_MODEL: Model name for embeddings
    @attribute QDRANT_HOST: Qdrant server hostname
    @attribute QDRANT_PORT: Qdrant server port
    @attribute QDRANT_COLLECTION: Default Qdrant collection name
    @attribute MCP_TIMEOUT: Timeout for MCP requests in seconds
    @attribute LLM_TIMEOUT: Timeout for LLM requests in seconds
    @attribute QDRANT_TIMEOUT: Timeout for Qdrant requests in seconds
    @attribute API_AUTH_TOKEN: Bearer token for API endpoints (optional)
    """
    
    # LLM Configuration
    LLM_URL: str = os.getenv("LLM_URL", "http://localhost:8080/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "diagnostic-agent")
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))

    # Embedding Configuration (for BGE-M3 or similar models)
    EMBEDDING_URL: str = os.getenv("EMBEDDING_URL", "http://localhost:1234/v1")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "bge-m3")
    EMBEDDING_TIMEOUT: float = float(os.getenv("EMBEDDING_TIMEOUT", "120.0"))
    
    # MCP Servers Configuration
    # Only includes servers that are explicitly configured in environment variables
    MCP_SERVERS: Dict[str, str] = {}
    if os.getenv("MCP_KUBERNETES_URL"):
        MCP_SERVERS["kubernetes"] = os.getenv("MCP_KUBERNETES_URL")
    if os.getenv("MCP_OPENSEARCH_URL"):
        MCP_SERVERS["opensearch"] = os.getenv("MCP_OPENSEARCH_URL")
    if os.getenv("MCP_REDIS_URL"):
        MCP_SERVERS["redis"] = os.getenv("MCP_REDIS_URL")
    if os.getenv("MCP_KAFKA_URL"):
        MCP_SERVERS["kafka"] = os.getenv("MCP_KAFKA_URL")
    MCP_TIMEOUT: float = float(os.getenv("MCP_TIMEOUT", "10.0"))
    
    # Qdrant Configuration
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "8000"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "documentation")
    QDRANT_TIMEOUT: float = float(os.getenv("QDRANT_TIMEOUT", "15.0"))
    
    # API Security Configuration
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
