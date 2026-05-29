#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API SERVER FOR OPENWEBUI
========================

Exposes the diagnostic agent via an OpenAI-compatible API.
Allows using the chat in OpenWebUI or other interfaces.
"""

from fastapi import FastAPI, Request, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import time
import os
from datetime import datetime

from agent import DiagnosticAgent, Config, DocumentationMatch

security = HTTPBearer()


# ============================================================================
# DATA MODELS
# ============================================================================

class Message(BaseModel):
    """
    Represents a chat message.
    
    @attribute role: The role of the message sender (user, assistant, system)
    @attribute content: The content of the message
    """
    role: str
    content: str


class ChatRequest(BaseModel):
    """
    Request model for chat completions endpoint.
    
    @attribute messages: List of previous messages in the conversation
    @attribute model: The model to use for completion
    @attribute temperature: Sampling temperature (0.0 to 1.0)
    @attribute max_tokens: Maximum number of tokens to generate
    @attribute stream: Whether to stream the response
    """
    messages: List[Message]
    model: Optional[str] = "diagnostic-agent"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False


class ChatChoice(BaseModel):
    """
    A single choice in the chat completion response.
    
    @attribute index: The index of this choice
    @attribute message: The message content
    @attribute finish_reason: Why the generation stopped
    """
    index: int
    message: Message
    finish_reason: str


# FASTAPI APPLICATION
# ============================================================================
=======
class ChatResponse(BaseModel):
    """
    Response model for chat completions endpoint.
    
    @attribute id: Unique identifier for this completion
    @attribute object: The object type (chat.completion)
    @attribute created: Timestamp of creation
    @attribute model: The model used
    @attribute choices: List of generated choices
    @attribute usage: Token usage information
    """
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Dict[str, int]


app = FastAPI(============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Cluster Diagnostic API",
    description="API for cluster diagnostics (K8s, OpenSearch, Redis, Kafka)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, DiagnosticAgent] = {}
session_history: Dict[str, List[Message]] = {}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Verify the Bearer token from request headers.
    
    @param credentials: HTTPAuthorizationCredentials from FastAPI security
    @return: True if token is valid
    @throws HTTPException: If token is missing or invalid
    """
    if not Config.API_AUTH_TOKEN:
        # No token configured, allow all requests
        return True
    
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Bearer token required"
        )
    
    if credentials.credentials != Config.API_AUTH_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid token"
        )
    
    return True


# ============================================================================
# OPENAI-COMPATIBLE ENDPOINTS
# ============================================================================

@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    _: bool = Depends(verify_token)
):
    """
    OpenAI-compatible endpoint for chat completions.
    
    This endpoint is compatible with OpenWebUI and other OpenAI-compatible clients.
    Requires Bearer token authentication if API_AUTH_TOKEN is configured.
    
    @param request: The chat completion request
    @param x_session_id: Optional session ID for maintaining conversation state
    @param _: Dependency injection for token verification
    @return: ChatResponse with generated completion
    @throws HTTPException: If processing fails or authentication is invalid
    """
    # Create or retrieve session
    session_id = x_session_id or str(uuid.uuid4())
    
    if session_id not in sessions:
        sessions[session_id] = DiagnosticAgent()
        session_history[session_id] = []
    
    agent = sessions[session_id]
    history = session_history[session_id]
    
    # Get the latest user message
    user_message = ""
    for msg in request.messages:
        if msg.role == "user":
            user_message = msg.content
            history.append(msg)
    
    # Process with diagnostic agent
    try:
        response_text = agent.diagnose(user_message)
        
        # Format OpenAI response
        response = ChatResponse(
            id=f"chatcmpl-{uuid.uuid4()}",
            created=int(datetime.now().timestamp()),
            model=request.model,
            choices=[ChatChoice(
                index=0,
                message=Message(role="assistant", content=response_text),
                finish_reason="stop"
            )],
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        )
        
        # Add to history
        history.append(Message(role="assistant", content=response_text))
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/models")
async def list_models():
    """
    Lists available models for OpenWebUI.
    
    @return: List of available models
    """
    return {
        "object": "list",
        "data": [{
            "id": "diagnostic-agent",
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": "system",
            "permission": [{"object": "model_permission", "allow_creation_of": "fine_tuning_job"}],
            "root": None,
            "parent": None
        }]
    }


@app.get("/v1/models/{model_id}")
async def get_model(model_id: str):
    """
    Gets details of a specific model.
    
    @param model_id: The ID of the model to retrieve
    @return: Model details
    @throws HTTPException: If model not found
    """
    if model_id != "diagnostic-agent":
        raise HTTPException(status_code=404, detail="Model not found")
    
    return {
        "id": "diagnostic-agent",
        "object": "model",
        "created": int(datetime.now().timestamp()),
        "owned_by": "system",
        "permission": [],
        "root": None,
        "parent": None
    }


# ============================================================================
# DIAGNOSTIC-SPECIFIC ENDPOINTS
# ============================================================================

@app.post("/api/diagnose")
async def diagnose_endpoint(
    query: str,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    _: bool = Depends(verify_token)
):
    """
    Direct diagnostic endpoint for programmatic access.
    
    Requires Bearer token authentication if API_AUTH_TOKEN is configured.
    
    @param query: The diagnostic query string
    @param x_session_id: Optional session ID
    @param _: Dependency injection for token verification
    @return: Dictionary containing the diagnostic report
    @throws HTTPException: If authentication is invalid
    """
    session_id = x_session_id or str(uuid.uuid4())
    
    if session_id not in sessions:
        sessions[session_id] = DiagnosticAgent()
    
    return {"response": sessions[session_id].diagnose(query)}


@app.get("/api/sessions")
async def list_sessions():
    """
    Lists all active sessions.
    
    @return: Dictionary with session list and count
    """
    return {
        "sessions": list(sessions.keys()),
        "count": len(sessions)
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Deletes a specific session.
    
    @param session_id: The ID of the session to delete
    @return: Confirmation of deletion
    """
    if session_id in sessions:
        sessions[session_id].close()
        del sessions[session_id]
        if session_id in session_history:
            del session_history[session_id]
    return {"status": "deleted"}


# ============================================================================
# MCP PROXY ENDPOINTS
# ============================================================================

@app.get("/mcp/tools")
async def list_mcp_tools():
    """
    Lists all available MCP tools across all servers.
    
    @return: Dictionary containing list of all tools with their metadata
    """
    agent = DiagnosticAgent()
    tools = []
    
    for category, cat_tools in agent.mcp.tools.items():
        for tool in cat_tools:
            tools.append({
                "name": tool.get("name"),
                "description": tool.get("description"),
                "category": category,
                "parameters": tool.get("parameters", {})
            })
    
    agent.close()
    return {"tools": tools}


@app.post("/mcp/tools/{tool_name}/call")
async def call_mcp_tool(tool_name: str, arguments: Dict[str, Any]):
    """
    Directly calls an MCP tool.
    
    @param tool_name: The name of the tool to call
    @param arguments: Dictionary of arguments for the tool
    @return: Result of the tool execution
    @throws HTTPException: If tool not found
    """
    agent = DiagnosticAgent()
    tool_found = agent.mcp.get_tool(tool_name)
    
    if not tool_found:
        agent.close()
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
    
    category, tool_info = tool_found
    result = agent.mcp.call_tool(category, tool_name, arguments)
    agent.close()
    
    return result


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    @return: Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(sessions),
        "version": "1.0.0"
    }


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """
    Root endpoint with API information.
    
    @return: API information and available endpoints
    """
    return {
        "message": "Cluster Diagnostic API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "OpenAI-compatible": [
                "POST /v1/chat/completions",
                "GET /v1/models",
                "GET /v1/models/{model_id}"
            ],
            "Diagnostic": [
                "POST /api/diagnose",
                "GET /api/sessions",
                "DELETE /api/sessions/{session_id}"
            ],
            "MCP": [
                "GET /mcp/tools",
                "POST /mcp/tools/{tool_name}/call"
            ],
            "Health": [
                "GET /health"
            ]
        }
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 80)
    print("  API SERVER - Cluster Diagnostic")
    print("=" * 80)
    print("\nEndpoints:")
    print("  - OpenAI-compatible: POST /v1/chat/completions")
    print("  - Diagnostic:      POST /api/diagnose")
    print("  - Health:          GET /health")
    print("\nFor OpenWebUI:")
    print("  URL: http://localhost:8001/v1")
    print("  Model: diagnostic-agent")
    print("=" * 80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
