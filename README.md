# Cluster Diagnostic Agent

**Multi-step diagnostic agent for infrastructure troubleshooting (Kubernetes, OpenSearch, Redis, Kafka)**

The Cluster Diagnostic Agent is an intelligent tool that helps you identify, diagnose, and resolve infrastructure issues across multiple systems. It combines the power of Model Context Protocol (MCP) tools, vector search with Qdrant, and Large Language Models (LLM) to provide accurate, actionable diagnostic reports.

---

## Quick Example

**Problem:** Your Kubernetes pods are restarting in a loop.

**Query:**
```
"My app pods are restarting in a loop with OOMKilled errors in namespace production"
```

**Output:**
```
================================================================================
  DIAGNOSTIC REPORT
================================================================================

## IDENTIFIED PROBLEM
Pods `app-backend-*` in namespace `production` are restarting in loop with exit code 137 (OOMKilled)

## SEVERITY
**RED**

## RELEVANT DOCUMENTATION
- **K8s Memory Management Guide** (Score: 0.98) [Internal Wiki](https://docs.internal/k8s/memory)
- **OOMKilled Errors** (Score: 0.95) [Internal Wiki](https://docs.internal/errors/oom)

## RESOLUTION STEPS
1. Check logs: `kubectl logs -n production pod/app-backend-xyz --previous`
2. Analyze consumption: `kubectl describe -n production pod/app-backend-xyz`
3. Increase memory: edit deployment to change limits.memory from 512Mi to 2Gi
4. Verify: `kubectl get pods -n production -w`

--- 
Query: My app pods are restarting... | Category: kubernetes
================================================================================
```

The agent automatically:
1. Identifies the problem category (Kubernetes)
2. Executes relevant MCP tools to gather data
3. Searches documentation in Qdrant for similar issues
4. Generates a structured report with severity, documentation links, and actionable steps

---

## Installation

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd mcp-agent

# Create virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

**Main dependencies:**
- `openai>=1.3.0` - For LLM and Embedding API clients (OpenAI-compatible)
- `qdrant-client>=1.7.0` - For vector database access
- `fastapi>=0.109.0` - For API server
- `python-dotenv>=1.0.0` - For environment variable management

### Required Services

The diagnostic agent requires the following services to be running:

| Service | Purpose | Default URL |
|---------|---------|-------------|
| Kubernetes MCP Server | Kubernetes cluster access | http://localhost:8090 |
| OpenSearch MCP Server | OpenSearch cluster access | http://localhost:8091 |
| Redis MCP Server | Redis cluster access | http://localhost:8092 |
| Kafka MCP Server | Kafka cluster access | http://localhost:8093 |
| Qdrant | Vector database for documentation | http://localhost:8000 |
| LLM API (OpenAI-compatible) | Language model for analysis | http://localhost:8080/v1 |
| Embedding API (BGE-M3) | Embedding model for vector search | http://localhost:1234/v1 |

---

## Configuration

### Environment Variables

Copy the `.env.example` file to `.env` and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# LLM Configuration (OpenAI-compatible API)
LLM_URL=http://localhost:8080/v1
LLM_API_KEY=your_bearer_token_here
LLM_MODEL=diagnostic-agent
LLM_TIMEOUT=120.0

# Embedding Model Configuration (OpenAI-compatible API for BGE-M3)
EMBEDDING_URL=http://localhost:1234/v1
EMBEDDING_API_KEY=your_bearer_token_here
EMBEDDING_MODEL=bge-m3
EMBEDDING_TIMEOUT=120.0

# MCP Servers Configuration
# Only servers with configured URLs will be loaded
MCP_KUBERNETES_URL=http://localhost:8090
MCP_OPENSEARCH_URL=http://localhost:8091
MCP_REDIS_URL=http://localhost:8092
MCP_KAFKA_URL=http://localhost:8093
MCP_TIMEOUT=10.0

# Qdrant Configuration
QDRANT_HOST=localhost
QDRANT_PORT=8000
QDRANT_COLLECTION=documentation
QDRANT_TIMEOUT=15.0

# API Server Configuration
API_HOST=0.0.0.0
API_PORT=8001

# Security (optional)
API_AUTH_TOKEN=your_secure_token_here
```

> **Note:** If LLM and Embedding services share the same API key, you can omit `EMBEDDING_API_KEY` and the system will use `LLM_API_KEY`.

> **Security Note:** The `.env` file is in `.gitignore` and will not be committed to version control. Never commit sensitive tokens to your repository.

---

## Usage

### CLI Mode (Interactive Chat)

Start an interactive chat session to diagnose issues:

```bash
python run.py
```

Example session:
```
================================================================================
  MULTI-STEP DIAGNOSTIC AGENT
================================================================================

================================================================================
  INTERACTIVE CHAT MODE
================================================================================

Example queries:
  - 'My app pods are restarting in a loop'
  - 'OpenSearch is returning 503 errors'
  - 'Redis has 500ms latency'
  - 'Kafka has lag on topic orders'

Type 'quit' to exit
================================================================================

Enter your query: My app pods are restarting in a loop

[Processing...]
[TOOL] Executing: kubernetes/get_pods
[TOOL] Executing: kubernetes/describe_pod

================================================================================
  DIAGNOSTIC REPORT
(... report content ...)
================================================================================

Enter your query: quit
Goodbye!
```

### API Mode (For OpenWebUI Integration)

Start the FastAPI server:

```bash
python run_api.py
```

The API will be available at `http://localhost:8001`.

#### OpenAI-Compatible Endpoint

This endpoint is compatible with OpenWebUI and other OpenAI-compatible clients:

```bash
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "My Kubernetes pods are crashing"}
    ],
    "model": "diagnostic-agent",
    "temperature": 0.7
  }'
```

#### Direct Diagnostic Endpoint

For programmatic access:

```bash
curl -X POST http://localhost:8001/api/diagnose \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "My Redis latency is high"}'
```

#### API Documentation

Access the interactive Swagger UI:
```bash
open http://localhost:8001/docs
```

#### Health Check

```bash
curl http://localhost:8001/health
```

---

## Project Structure

```
mcp-agent/
├── .env                    # Environment variables (excluded from git)
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── run.py                  # CLI entry point
└── run_api.py              # API server entry point

├── agent/                  # Main agent package
│   ├── __init__.py         # Package exports
│   ├── config.py           # Configuration management
│   ├── models.py           # Data models (DocumentationMatch, DiagnosticReport)
│   ├── diagnostic_agent.py # Main diagnostic agent
│   └── clients/            # Client implementations
│       ├── __init__.py     # Clients package exports
│       ├── mcp_registry.py # MCP server management
│       ├── qdrant_client.py # Qdrant vector search client
│       └── llm_client.py   # LLM (Gemma4) client

└── api/                    # FastAPI server package
    ├── __init__.py         # API package init
    └── server.py           # FastAPI endpoints
```

---

## Architecture Overview

The diagnostic agent follows a **multi-step workflow** to provide accurate diagnoses:

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                                │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DiagnosticAgent                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 1. CATEGORY IDENTIFICATION                                 ││
│  │    - Analyzes query keywords                               ││
│  │    - Determines problem domain (k8s, opensearch, redis, kafka)││
│  └─────────────────────────────────────────────────────────────┘│
│                                    │                                │
│                                    ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 2. QUICK DIAGNOSIS                                          ││
│  │    - Uses LLM to identify main problem                      ││
│  │    - Extracts key elements to investigate                     ││
│  │    - Determines urgency level                               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                    │                                │
│                                    ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 3. TOOL EXECUTION                                            ││
│  │    - Selects relevant MCP tools based on category           ││
│  │    - Executes tools to gather live data                       ││
│  │    - Merges results for analysis                              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                    │                                │
│                                    ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 4. DOCUMENTATION SEARCH                                      ││
│  │    - Enriches query with diagnostic terms                    ││
│  │    - Searches Qdrant for relevant documentation              ││
│  │    - Returns top matches with relevance scores                ││
│  └─────────────────────────────────────────────────────────────┘│
│                                    │                                │
│                                    ▼                                │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ 5. FINAL REPORT GENERATION                                   ││
│  │    - Combines all data (tools, docs, diagnosis)              ││
│  │    - Uses LLM to synthesize findings                          ││
│  │    - Returns structured report with:                         ││
│  │      * Identified problem                                    ││
│  │      * Severity level                                       ││
│  │      * Relevant documentation links                          ││
│  │      * Actionable resolution steps                           ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Config (`agent/config.py`)

Centralized configuration class that loads all settings from environment variables with fallback to defaults.

**Key Features:**
- Environment variable support with defaults
- All sensitive data (API keys, tokens) stored in `.env`
- Type hints for all configuration values
- Comprehensive Javadoc-style documentation

**Environment Variables:**
```python
# LLM Configuration
LLM_URL          # LLM API endpoint URL
LLM_API_KEY      # Bearer token for LLM authentication
LLM_TIMEOUT      # Request timeout in seconds

# MCP Servers
MCP_KUBERNETES_URL, MCP_OPENSEARCH_URL, MCP_REDIS_URL, MCP_KAFKA_URL
MCP_TIMEOUT      # MCP request timeout

# Qdrant
QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION, QDRANT_TIMEOUT

# API Security
API_AUTH_TOKEN   # Optional token for API endpoint protection
```

### 2. Data Models (`agent/models.py`)

Defines the core data structures used throughout the application.

**`DocumentationMatch`** - Represents a documentation entry found in Qdrant:
- `title`: Documentation title
- `content`: Documentation text content
- `url`: Optional URL to the source
- `source`: Documentation source identifier
- `score`: Relevance score (0.0 to 1.0)

**`DiagnosticReport`** - Complete diagnostic report structure:
- `problem`: Description of the identified issue
- `category`: Problem category (kubernetes, opensearch, redis, kafka, general)
- `severity`: Severity level (low, medium, high, critical)
- `documentation`: List of relevant DocumentationMatch objects
- `solution_steps`: List of actionable resolution steps
- `tools_used`: List of MCP tools that were executed
- `raw_data`: Dictionary containing raw diagnostic data

### 3. MCP Registry (`agent/clients/mcp_registry.py`)

Manages connections to multiple MCP servers (Kubernetes, OpenSearch, Redis, Kafka).

**Key Features:**
- Automatic discovery of available tools on each MCP server
- Centralized access to all MCP tools
- Automatic categorization by server type
- Connection pooling and management

**Main Methods:**
- `__init__()`: Initializes connections to all configured MCP servers
- `get_tool(tool_name)`: Finds a tool by name across all servers
- `call_tool(category, tool_name, arguments)`: Executes a specific tool
- `close_all()`: Closes all HTTP client connections

### 4. Qdrant Client (`agent/clients/qdrant_client.py`)

Handles connection to Qdrant vector database for semantic documentation search.

**Key Features:**
- Automatic collection detection
- Semantic search with vector embeddings
- Result sorting by relevance score
- Conversion to DocumentationMatch objects

**Main Methods:**
- `__init__()`: Initializes Qdrant client and detects collection
- `search(query, limit)`: Searches for relevant documentation
- `_mock_embedding(text)`: Generates mock embedding vector (TODO: replace with actual embedder)

### 5. LLM Client (`agent/clients/llm_client.py`)

Handles communication with the LLM (Gemma4) API.

**Key Features:**
- Bearer token authentication support
- Automatic header management
- Response parsing for multiple API formats
- Error handling with fallback messages

**Main Methods:**
- `__init__()`: Initializes HTTP client with optional Bearer token
- `generate(messages, temperature)`: Generates response from LLM
- `close()`: Closes HTTP client connection

### 6. Diagnostic Agent (`agent/diagnostic_agent.py`)

Main class that orchestrates the complete diagnostic workflow.

**Key Features:**
- Multi-step diagnostic process
- Automatic category identification
- Tool selection and execution
- Documentation search
- Report generation and formatting
- Interactive chat mode
- Connection testing

**Main Methods:**
- `__init__()`: Initializes all components (MCP, Qdrant, LLM)
- `diagnose(user_query)`: Executes complete diagnostic workflow
- `_identify_category(query)`: Determines problem category from keywords
- `_quick_diagnose(query, category)`: Performs initial diagnosis with LLM
- `_execute_relevant_tools(query, category, diagnosis)`: Runs relevant MCP tools
- `_search_documentation(query, diagnosis, tools_results)`: Searches Qdrant
- `_generate_final_report(...)`: Creates structured diagnostic report
- `chat()`: Starts interactive chat session
- `test_connections()`: Tests connectivity to all services
- `close()`: Cleans up all connections

### 7. API Server (`api/server.py`)

FastAPI application providing OpenAI-compatible endpoints.

**Key Features:**
- OpenAI-compatible `/v1/chat/completions` endpoint
- Bearer token authentication
- Session management for multi-user support
- CORS support for OpenWebUI integration
- Health check endpoint
- Interactive Swagger UI documentation

**Main Endpoints:**
- `POST /v1/chat/completions`: OpenAI-compatible chat endpoint
- `GET /v1/models`: Lists available models
- `GET /v1/models/{model_id}`: Gets model details
- `POST /api/diagnose`: Direct diagnostic endpoint
- `GET /api/sessions`: Lists active sessions
- `DELETE /api/sessions/{session_id}`: Deletes a session
- `GET /mcp/tools`: Lists all MCP tools
- `POST /mcp/tools/{tool_name}/call`: Directly calls an MCP tool
- `GET /health`: Health check
- `GET /`: API information

**Authentication:**
The API supports optional Bearer token authentication. If `API_AUTH_TOKEN` is configured in `.env`, all endpoints will require a valid token in the `Authorization` header:
```
Authorization: Bearer YOUR_TOKEN
```

If no token is configured, all requests are allowed without authentication.

---

## Security Best Practices

1. **Never commit sensitive data**: The `.env` file is in `.gitignore`. Always keep it that way.

2. **Use strong tokens**: Generate long, random tokens for `LLM_API_KEY` and `API_AUTH_TOKEN`.

3. **Rotate tokens regularly**: Change your tokens periodically for enhanced security.

4. **Use HTTPS in production**: Always use HTTPS when deploying the API server in production.

5. **Restrict API access**: Use firewall rules to restrict access to the API server.

6. **Environment-specific configuration**: Use different `.env` files for development, staging, and production.

---

## Troubleshooting

### Common Issues

**"MCP server not available"**
- Verify the MCP server is running
- Check the URL in your `.env` file
- Ensure the server is accessible from your machine

**"Qdrant connection error"**
- Verify Qdrant server is running
- Check `QDRANT_HOST` and `QDRANT_PORT` in `.env`
- Ensure the collection exists in Qdrant

**"LLM Error"**
- Verify the LLM API endpoint is correct
- Check `LLM_API_KEY` in `.env`
- Ensure the LLM service is running

**"API Authentication failed"**
- Verify `API_AUTH_TOKEN` in `.env`
- Ensure you're sending the token in the `Authorization` header
- Check for typos in the token

### Testing Connections

Run the CLI and use the connection test:
```bash
python run.py
```

The agent will automatically test all connections on startup.

---

## License

This project is proprietary. All rights reserved.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (if available)
5. Submit a pull request

---

## Support

For issues, questions, or feedback, please contact the development team.
