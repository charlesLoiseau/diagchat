#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API SERVER LAUNCH SCRIPT
========================

Launches the FastAPI server for OpenWebUI integration.
Loads configuration from .env file if present.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    from api.server import app
    import uvicorn
    
    print("=" * 80)
    print("  API SERVER LAUNCH")
    print("=" * 80)
    print("\nConfiguration:")
    print("  - Host: 0.0.0.0")
    print("  - Port: 8001")
    print("\nEndpoints:")
    print("  - OpenAI-compatible: POST /v1/chat/completions")
    print("  - Health:          GET /health")
    print("  - Docs:            GET /docs")
    print("\nFor OpenWebUI:")
    print("  URL: http://localhost:8001/v1")
    print("  Model: diagnostic-agent")
    print("\nPress Ctrl+C to stop")
    print("=" * 80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
