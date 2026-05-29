#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTIC AGENT MODULE
========================

Main diagnostic agent with multi-step workflow.
Orchestrates the complete diagnostic process:
1. Identify problem category
2. Perform initial diagnosis
3. Execute relevant MCP tools
4. Search Qdrant for documentation
5. Generate final synthesis with LLM
"""

import time
import sys
import io
import json
import re
from typing import Optional, List, Dict, Any, Tuple

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agent.config import Config
from agent.models import DocumentationMatch, DiagnosticReport
from agent.clients.mcp_registry import MCPRegistry
from agent.clients.qdrant_client import QdrantDiagnostic
from agent.clients.llm_client import LLMAPI


class DiagnosticAgent:
    """
    Main diagnostic agent with multi-step workflow.
    
    Orchestrates the complete diagnostic process:
    1. Identify problem category
    2. Perform initial diagnosis
    3. Execute relevant MCP tools
    4. Search Qdrant for documentation
    5. Generate final synthesis with LLM
    
    @attribute mcp: MCPRegistry instance for tool access
    @attribute qdrant: QdrantDiagnostic instance for documentation search
    @attribute llm: LLMAPI instance for LLM access
    @attribute history: List of previous diagnostic sessions
    """
    
    def __init__(self):
        """
        Initializes the diagnostic agent and all its components.
        
        @throws Exception: If initialization of any component fails
        """
        print("=" * 80)
        print("  MULTI-STEP DIAGNOSTIC AGENT")
        print("=" * 80)
        
        # Initialize clients
        self.mcp = MCPRegistry()
        self.qdrant = QdrantDiagnostic()
        self.llm = LLMAPI()
        
        # History tracking
        self.history: List[Dict[str, str]] = []
        
        print("\n" + "=" * 80)
    
    def diagnose(self, user_query: str) -> str:
        """
        Executes the complete diagnostic workflow.
        
        @param user_query: The user's diagnostic query
        @return: Formatted diagnostic report string
        @throws Exception: If diagnostic process fails
        """
        start_total = time.time()
        
        # Step 1: Identify category
        category = self._identify_category(user_query)
        
        # Step 2: Quick initial diagnosis
        initial_diagnosis = self._quick_diagnose(user_query, category)
        
        # Step 3: Execute relevant tools
        tools_results = self._execute_relevant_tools(user_query, category, initial_diagnosis)
        
        # Step 4: Search documentation
        docs = self._search_documentation(user_query, initial_diagnosis, tools_results)
        
        # Step 5: Generate final report
        report = self._generate_final_report(
            user_query, category, initial_diagnosis, tools_results, docs
        )
        
        # Add to history
        self.history.append({
            "query": user_query,
            "response": report,
            "timestamp": time.time()
        })
        
        return report
    
    def _identify_category(self, query: str) -> str:
        """
        Identifies the problem category based on keywords.
        
        @param query: The user query string
        @return: Category name (kubernetes, opensearch, redis, kafka, general)
        """
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["k8s", "kubernetes", "pod", "node", 
                                                 "deployment", "service", "namespace", "container"]):
            return "kubernetes"
        elif any(kw in query_lower for kw in ["opensearch", "search", "index", 
                                                  "cluster health", "shard", "elastic"]):
            return "opensearch"
        elif any(kw in query_lower for kw in ["redis", "cache", "memory", 
                                                  "connection", "latency", "key"]):
            return "redis"
        elif any(kw in query_lower for kw in ["kafka", "broker", "topic", 
                                                  "consumer", "producer", "lag", "message"]):
            return "kafka"
        else:
            return "general"
    
    def _quick_diagnose(self, query: str, category: str) -> Dict[str, Any]:
        """
        Performs a quick initial diagnosis to identify key elements.
        
        @param query: The user query string
        @param category: The identified problem category
        @return: Dictionary containing problem, key_elements, and urgency
        """
        prompt = f"""Analyze this diagnostic query and identify:
1. The main problem
2. Key elements to check
3. Urgency level (low, medium, high, critical)

Query: {query}
Category: {category}

Respond in strict JSON:
{{
  "problem": "...",
  "key_elements": ["...", "..."],
  "urgency": "low|medium|high|critical"
}}"""
        
        try:
            response = self.llm.generate([
                {"role": "system", "content": "You are a technical diagnostic expert."},
                {"role": "user", "content": prompt}
            ])
            
            # Try to parse JSON response
            try:
                return json.loads(response)
            except:
                return {"problem": query, "key_elements": [], "urgency": "medium"}
                
        except Exception as e:
            print(f"[Quick Diagnose] Error: {e}")
            return {"problem": query, "key_elements": [], "urgency": "medium"}
    
    def _execute_relevant_tools(self, query: str, category: str, diagnosis: Dict) -> List[Dict]:
        """
        Identifies and executes relevant MCP tools for the diagnosis.
        
        @param query: The user query string
        @param category: The problem category
        @param diagnosis: Initial diagnosis dictionary
        @return: List of tool execution results
        """
        tools_to_call = []
        key_elements = diagnosis.get("key_elements", [])
        
        # Select tools based on category and keywords
        for cat, cat_tools in self.mcp.tools.items():
            for tool in cat_tools:
                tool_name = tool.get("name", "").lower()
                tool_desc = tool.get("description", "").lower()
                
                # Check if tool is relevant
                relevant = False
                
                # By category
                if cat == category:
                    relevant = True
                
                # By keywords
                query_kw = query.lower()
                for kw in ["status", "health", "log", "describe", "metric", "error"]:
                    if kw in tool_name or kw in tool_desc:
                        relevant = True
                        break
                
                # By diagnosis key elements
                for element in key_elements:
                    if element.lower() in tool_name or element.lower() in tool_desc:
                        relevant = True
                        break
                
                if relevant:
                    tools_to_call.append({
                        "category": cat,
                        "name": tool.get("name"),
                        "description": tool.get("description"),
                        "parameters": tool.get("parameters", {}),
                        "reason": f"Relevant for {category}"
                    })
        
        # Limit to max 3 tools
        tools_to_call = tools_to_call[:3]
        
        # Execute tools
        results = []
        for tool_info in tools_to_call:
            try:
                # Prepare arguments
                arguments = {}
                for param, schema in tool_info.get("parameters", {}).items():
                    if schema.get("required"):
                        # Try to infer value from query
                        arguments[param] = self._extract_param_from_query(query, param)
                    elif "default" in schema:
                        arguments[param] = schema["default"]
                
                print(f"[TOOL] Executing: {tool_info['category']}/{tool_info['name']}")
                
                start = time.time()
                result = self.mcp.call_tool(
                    tool_info["category"],
                    tool_info["name"],
                    arguments
                )
                duration = time.time() - start
                
                results.append({
                    "tool": f"{tool_info['category']}/{tool_info['name']}",
                    "arguments": arguments,
                    "result": result,
                    "status": "success" if "error" not in result else "failed",
                    "duration": duration
                })
                
            except Exception as e:
                results.append({
                    "tool": f"{tool_info['category']}/{tool_info['name']}",
                    "error": str(e),
                    "status": "failed"
                })
        
        return results
    
    def _extract_param_from_query(self, query: str, param: str) -> str:
        """
        Attempts to extract a parameter value from the query string.
        
        @param query: The user query string
        @param param: The parameter name to extract
        @return: Extracted parameter value, or empty string if not found
        """
        query_lower = query.lower()
        param_lower = param.lower()
        
        # Common patterns for different parameter types
        patterns = {
            "pod": [r'pod[/:]?\s*(\S+)', r'pod\s+(\S+)'],
            "namespace": [r'namespace[/:]?\s*(\S+)', r'-n\s+(\S+)'],
            "node": [r'node[/:]?\s*(\S+)'],
            "deployment": [r'deployment[/:]?\s*(\S+)'],
            "topic": [r'topic[/:]?\s*(\S+)'],
            "index": [r'index[/:]?\s*(\S+)'],
            "service": [r'service[/:]?\s*(\S+)'],
        }
        
        for pattern in patterns.get(param_lower, []):
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # If param appears in query
        if param_lower in query_lower:
            # Extract what follows
            match = re.search(rf'{param_lower}[:\s]+([^\s,;]+)', query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _search_documentation(self, query: str, diagnosis: Dict, 
                             tools_results: List[Dict]) -> List[DocumentationMatch]:
        """
        Searches Qdrant for relevant documentation using enriched query.
        Automatically identifies products mentioned in the query and filters
        Qdrant search to only return documentation for those products.
        
        @param query: The user query string
        @param diagnosis: Initial diagnosis dictionary
        @param tools_results: List of tool execution results
        @return: List of DocumentationMatch objects
        """
        # Identify products from query
        matched_products = self.qdrant.match_products(query)
        
        # Enrich query with diagnostic terms
        enriched_query = query
        
        if isinstance(diagnosis, dict):
            if diagnosis.get("problem"):
                enriched_query += f" {diagnosis['problem']}"
            for kw in diagnosis.get("key_elements", []):
                enriched_query += f" {kw}"
        
        # Add generic diagnostic terms
        enriched_query += " troubleshooting guide solution fix error resolution"
        
        # Search with product filter if products were identified
        if matched_products:
            print(f"[Qdrant] Filtering by products: {matched_products}")
            return self.qdrant.search(enriched_query, limit=5, products=matched_products)
        else:
            return self.qdrant.search(enriched_query, limit=5)
    
    def _generate_final_report(self, query: str, category: str, diagnosis: Dict,
                             tools_results: List[Dict], 
                             docs: List[DocumentationMatch]) -> str:
        """
        Generates the final diagnostic report using the LLM.
        
        @param query: The user query string
        @param category: The problem category
        @param diagnosis: Initial diagnosis dictionary
        @param tools_results: List of tool execution results
        @param docs: List of DocumentationMatch objects
        @return: Formatted diagnostic report string
        """
        # Build prompt for LLM
        prompt_parts = []
        
        # Query context
        prompt_parts.append("QUERY CONTEXT:")
        prompt_parts.append(f"User query: {query}")
        prompt_parts.append(f"Category: {category}")
        
        # Initial diagnosis
        if isinstance(diagnosis, dict):
            prompt_parts.append("")
            prompt_parts.append("INITIAL DIAGNOSIS:")
            prompt_parts.append(f"- Problem: {diagnosis.get('problem', 'Not specified')}")
            prompt_parts.append(f"- Urgency: {diagnosis.get('urgency', 'medium')}")
            if diagnosis.get("key_elements"):
                prompt_parts.append(f"- Key elements: {', '.join(diagnosis['key_elements'])}")
        
        # Tool results
        if tools_results:
            prompt_parts.append("")
            prompt_parts.append("TOOL RESULTS:")
            for result in tools_results:
                status = "SUCCESS" if result.get("status") == "success" else "FAILED"
                prompt_parts.append(f"- [{status}] {result['tool']}")
                if result.get("result") and isinstance(result["result"], dict):
                    for k, v in result["result"].items():
                        if k != "_error" and isinstance(v, str) and len(v) < 200:
                            prompt_parts.append(f"    {k}: {v}")
        
        # Found documentation
        if docs:
            prompt_parts.append("")
            prompt_parts.append("FOUND DOCUMENTATION:")
            for doc in docs:
                url_info = f" [LINK: {doc.source}]({doc.url})" if doc.url else f" [{doc.source}]"
                prompt_parts.append(f"- {doc.title} (score: {doc.score:.2f}){url_info}")
                prompt_parts.append(f"    > {doc.content[:200]}...")
        
        # Instructions for LLM
        prompt_parts.append("")
        prompt_parts.append("INSTRUCTIONS:")
        prompt_parts.append("1. Analyze all elements above")
        prompt_parts.append("2. Identify the main problem precisely")
        prompt_parts.append("3. Evaluate severity (low, medium, high, critical)")
        prompt_parts.append("4. Propose NUMBERED and ACTIONABLE resolution steps")
        prompt_parts.append("5. Reference relevant documentation with title")
        prompt_parts.append("")
        prompt_parts.append("REQUIRED RESPONSE FORMAT:")
        prompt_parts.append("## IDENTIFIED PROBLEM")
        prompt_parts.append("[Clear and precise problem description]")
        prompt_parts.append("")
        prompt_parts.append("## SEVERITY")
        prompt_parts.append("[low|medium|high|critical]")
        prompt_parts.append("")
        prompt_parts.append("## RELEVANT DOCUMENTATION")
        prompt_parts.append("[List with titles and scores]")
        prompt_parts.append("")
        prompt_parts.append("## RESOLUTION STEPS")
        prompt_parts.append("[1. First step...]")
        
        # Call LLM
        response = self.llm.generate([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": "\n".join(prompt_parts)}
        ])
        
        # Format final response
        return self._format_response(response, query, category, docs, tools_results)
    
    def _get_system_prompt(self) -> str:
        """
        Gets the specialized system prompt for the LLM.
        
        @return: System prompt string
        """
        return """You are a senior infrastructure diagnostic expert.
Your specialties: Kubernetes, OpenSearch, Redis, Kafka.

YOUR CAPABILITIES:
- Analyze technical data (logs, metrics, status)
- Correlate information from multiple sources
- Propose actionable and precise solutions
- Reference relevant documentation

STRICT RULES:
1. Be EXTREMELY PRECISE in your diagnostics
2. ALWAYS cite sources (documentation, tools used)
3. Propose exact commands to execute
4. NUMBER ALL resolution steps
5. Use Markdown format with emojis as in the example

EXAMPLE FORMAT:
## IDENTIFIED PROBLEM
Pods `app-backend-*` in namespace `production` are restarting in loop with exit code 137 (OOMKilled)

## SEVERITY
high

## RELEVANT DOCUMENTATION
- [K8s Memory Management Guide](https://docs.internal/k8s/memory) - Score: 0.98
- [OOMKilled Errors](https://docs.internal/errors/oom) - Score: 0.95

## RESOLUTION STEPS
1. Check logs: `kubectl logs -n production pod/app-backend-xyz --previous`
2. Analyze consumption: `kubectl describe -n production pod/app-backend-xyz`
3. Increase memory: edit deployment to change limits.memory from 512Mi to 2Gi"""
    
    def _format_response(self, llm_response: str, query: str, category: str,
                        docs: List[DocumentationMatch], tools_results: List[Dict]) -> str:
        """
        Formats the final diagnostic report.
        
        @param llm_response: Raw response from LLM
        @param query: Original user query
        @param category: Problem category
        @param docs: List of DocumentationMatch objects
        @param tools_results: List of tool execution results
        @return: Formatted report string
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("  DIAGNOSTIC REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Extract problem
        problem = self._extract_section(llm_response, "IDENTIFIED PROBLEM")
        if problem:
            lines.append("## IDENTIFIED PROBLEM")
            lines.append(problem)
            lines.append("")
        
        # Extract severity
        severity = self._extract_section(llm_response, "SEVERITY")
        if severity:
            severity = severity.strip().lower()
            severity_emoji = {
                "low": "GREEN",
                "medium": "YELLOW", 
                "high": "RED",
                "critical": "CRITICAL"
            }
            severity_display = severity_emoji.get(severity, severity).upper()
            lines.append("## SEVERITY")
            lines.append(f"**{severity_display}**")
            lines.append("")
        
        # Documentation
        doc_section = self._extract_section(llm_response, "RELEVANT DOCUMENTATION")
        if doc_section:
            lines.append("## RELEVANT DOCUMENTATION")
            lines.append(doc_section)
            lines.append("")
        else:
            # Auto-formatting from docs
            if docs:
                lines.append("## RELEVANT DOCUMENTATION")
                for doc in docs:
                    url_part = ""
                    if doc.url:
                        url_part = f" [{doc.source}]({doc.url})"
                    else:
                        url_part = f" [{doc.source}]"
                    lines.append(f"- **{doc.title}** (Score: {doc.score:.2f}){url_part}")
                lines.append("")
        
        # Resolution steps
        steps_section = self._extract_section(llm_response, "RESOLUTION STEPS")
        if steps_section:
            lines.append("## RESOLUTION STEPS")
            # Number automatically
            step_lines = []
            for line in steps_section.split('\n'):
                line = line.strip()
                if line and not line.startswith('##') and not line.startswith('='):
                    if line[0].isdigit() and line[1] == '.':
                        step_lines.append(line)
                    else:
                        step_lines.append(line)
            
            for step in step_lines:
                if step:
                    lines.append(step)
            lines.append("")
        
        # Tools used
        if tools_results:
            tools_used = [r["tool"] for r in tools_results if r.get("status") == "success"]
            if tools_used:
                lines.append("## TOOLS USED")
                for tool in tools_used:
                    lines.append(f"- `{tool}`")
                lines.append("")
        
        # Footer
        lines.append("---")
        lines.append(f"Query: {query} | Category: {category}")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def _extract_section(self, text: str, section_title: str) -> str:
        """
        Extracts a section from text based on markdown headers.
        
        @param text: The text to search in
        @param section_title: The title of the section to extract
        @return: Extracted section content, or empty string if not found
        """
        pattern = rf'##.*{section_title}.*\n(.*?)(?=\n##|\n--|$)'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def chat(self):
        """
        Starts an interactive chat session.
        
        Provides a command-line interface for users to submit diagnostic queries
        and receive formatted reports.
        """
        print("\n" + "=" * 80)
        print("  INTERACTIVE CHAT MODE")
        print("=" * 80)
        print("\nExample queries:")
        print("  - 'My app pods are restarting in a loop'")
        print("  - 'OpenSearch is returning 503 errors'")
        print("  - 'Redis has 500ms latency'")
        print("  - 'Kafka has lag on topic orders'")
        print("\nType 'quit' to exit")
        print("=" * 80 + "\n")
        
        while True:
            try:
                query = input("Enter your query: ").strip()
                if not query:
                    continue
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                print("\n[Processing...]")
                response = self.diagnose(query)
                print(response)
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def test_connections(self):
        """
        Tests all service connections.
        
        Verifies connectivity to MCP servers, LLM, and Qdrant,
        and reports the status of each.
        """
        print("\n" + "=" * 80)
        print("  CONNECTION TESTS")
        print("=" * 80)
        
        # Test MCP
        print("\n[1] MCP Servers...")
        for category, tools in self.mcp.tools.items():
            status = "OK" if tools else "FAILED"
            print(f"   [{status}] {category}: {len(tools)} tools")
        
        # Test LLM
        print("\n[2] LLM (Gemma4)...")
        try:
            response = self.llm.generate([
                {"role": "user", "content": "Say OK"}
            ])
            print(f"   [OK] Response: {response[:20]}")
        except Exception as e:
            print(f"   [FAILED] {e}")
        
        # Test Qdrant
        print("\n[3] Qdrant...")
        try:
            docs = self.qdrant.search("test", limit=1)
            print(f"   [OK] {len(docs)} results")
        except Exception as e:
            print(f"   [FAILED] {e}")
        
        print("\n" + "=" * 80)
    
    def close(self):
        """
        Closes all connections and cleans up resources.
        """
        self.mcp.close_all()
        self.llm.close()
