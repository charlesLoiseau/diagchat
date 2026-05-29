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
        print("  INFRASTRUCTURE ASSISTANT")
        print("  (Kubernetes, OpenSearch, Redis, Kafka)")
        print("=" * 80)
        
        self.mcp = MCPRegistry()
        self.qdrant = QdrantDiagnostic()
        self.llm = LLMAPI()
        
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
        
        category = self._identify_category(user_query)
        
        initial_diagnosis = self._quick_diagnose(user_query, category)
        
        tools_results = self._execute_relevant_tools(user_query, category, initial_diagnosis)
        
        docs = self._search_documentation(user_query, initial_diagnosis, tools_results)
        
        report = self._generate_final_report(
            user_query, category, initial_diagnosis, tools_results, docs
        )
        
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
    
    def _select_tools_with_llm(self, query: str, category: str, diagnosis: Dict,
                               all_tools: List[Dict]) -> List[Dict]:
        """
        Uses LLM to intelligently select which MCP tools to execute.

        @param query: The user query string
        @param category: The problem category
        @param diagnosis: Initial diagnosis dictionary
        @param all_tools: List of all available MCP tools
        @return: List of selected tools with metadata
        """
        # Build tool list for LLM with parameter information
        tools_text = []
        for i, tool in enumerate(all_tools):
            tool_line = f"{i+1}. [{tool['category']}] {tool['name']}: {tool['description']}"

            # Add parameter information if available
            input_schema = tool.get('inputSchema', {})
            if input_schema and 'properties' in input_schema:
                params = input_schema['properties']
                required = input_schema.get('required', [])

                param_strs = []
                for param_name, param_info in params.items():
                    is_required = "required" if param_name in required else "optional"
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    param_strs.append(f"{param_name} ({param_type}, {is_required}): {param_desc}")

                if param_strs:
                    tool_line += f"\n   Parameters: {', '.join(param_strs)}"

            tools_text.append(tool_line)

        prompt = f"""Given the user query and available MCP tools, select the 1-3 most relevant tools to execute.

USER QUERY: {query}
CATEGORY: {category}
PROBLEM: {diagnosis.get('problem', 'Not specified')}

AVAILABLE TOOLS:
{chr(10).join(tools_text)}

Select the most relevant tools to answer this query. Respond with ONLY the tool numbers (comma-separated).
Examples:
- "1,3,5"
- "2"
- "4,7"

If no tools are needed, respond with "NONE".

Your selection:"""

        try:
            response = self.llm.generate([
                {"role": "system", "content": "You are a tool selection expert. Select only the most relevant tools."},
                {"role": "user", "content": prompt}
            ], temperature=0.1)

            # Parse response
            response = response.strip().upper()
            if response == "NONE" or not response:
                return []

            # Extract tool indices
            selected_indices = []
            for part in response.replace(" ", "").split(","):
                try:
                    idx = int(part) - 1  # Convert to 0-based index
                    if 0 <= idx < len(all_tools):
                        selected_indices.append(idx)
                except ValueError:
                    continue

            # Build selected tools list
            selected_tools = []
            for idx in selected_indices:
                tool = all_tools[idx]
                selected_tools.append({
                    "category": tool["category"],
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool.get("inputSchema", {}),  # Keep full schema
                    "reason": f"Selected by LLM for {category}"
                })

            print(f"[TOOL SELECTION] LLM selected {len(selected_tools)} tools: {[t['name'] for t in selected_tools]}")
            return selected_tools

        except Exception as e:
            print(f"[TOOL SELECTION] LLM selection failed: {e}")
            # Fallback: select tools from matching category
            fallback = [t for t in all_tools if t['category'] == category][:2]
            return [{
                "category": t["category"],
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t.get("inputSchema", {}),  # Keep full schema
                "reason": f"Fallback selection for {category}"
            } for t in fallback]

    def _extract_arguments_with_llm(self, query: str, tool_info: Dict) -> Dict[str, Any]:
        """
        Uses LLM to extract parameter values from the user query for a specific tool.

        @param query: The user query string
        @param tool_info: Dictionary containing tool metadata and inputSchema
        @return: Dictionary of argument name -> value
        """
        # Get parameter schema from inputSchema
        input_schema = tool_info.get("inputSchema", {})
        properties = input_schema.get("properties", {})
        required_params = input_schema.get("required", [])

        if not properties:
            return {}

        # Build parameter description for LLM
        param_descriptions = []
        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "string")
            param_desc = param_schema.get("description", "")
            is_required = "REQUIRED" if param_name in required_params else "optional"
            param_descriptions.append(f"- {param_name} ({param_type}, {is_required}): {param_desc}")

        prompt = f"""Extract the parameter values from the user query for this MCP tool.

TOOL: {tool_info.get('name')}
DESCRIPTION: {tool_info.get('description')}

PARAMETERS:
{chr(10).join(param_descriptions)}

USER QUERY: {query}

Extract the parameter values from the query. Respond in strict JSON format:
{{
  "param_name": "value",
  "another_param": "value"
}}

Rules:
- Only include parameters that you can extract from the query
- For required parameters not found, use reasonable defaults or empty string
- For namespace parameters, default to "default" if not specified
- Return valid JSON only

Your JSON response:"""

        try:
            response = self.llm.generate([
                {"role": "system", "content": "You are a parameter extraction expert. Extract values from queries and return valid JSON only."},
                {"role": "user", "content": prompt}
            ], temperature=0.1)

            # Try to parse JSON response
            response = response.strip()

            # Remove markdown code blocks if present
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            arguments = json.loads(response)

            print(f"[ARGS] LLM extracted: {arguments}")
            return arguments

        except json.JSONDecodeError as e:
            print(f"[ARGS] JSON parse error: {e}, response was: {response[:200]}")
            # Fallback to regex extraction
            return self._extract_arguments_fallback(query, input_schema)
        except Exception as e:
            print(f"[ARGS] LLM extraction failed: {e}")
            return self._extract_arguments_fallback(query, input_schema)

    def _extract_arguments_fallback(self, query: str, input_schema: Dict) -> Dict[str, Any]:
        """
        Fallback method using regex when LLM extraction fails.

        @param query: The user query string
        @param input_schema: The inputSchema dictionary with properties and required fields
        @return: Dictionary of extracted arguments
        """
        properties = input_schema.get("properties", {})
        required_params = input_schema.get("required", [])

        arguments = {}
        for param_name, param_schema in properties.items():
            value = self._extract_param_from_query(query, param_name)
            if value:
                arguments[param_name] = value
            elif "default" in param_schema:
                arguments[param_name] = param_schema["default"]
            elif param_name in required_params:
                # Provide reasonable defaults for required params
                if param_name.lower() == "namespace":
                    arguments[param_name] = "default"
                else:
                    arguments[param_name] = ""
        return arguments

    def _execute_relevant_tools(self, query: str, category: str, diagnosis: Dict) -> List[Dict]:
        """
        Identifies and executes relevant MCP tools using LLM-based selection.

        @param query: The user query string
        @param category: The problem category
        @param diagnosis: Initial diagnosis dictionary
        @return: List of tool execution results
        """
        # Build a list of all available tools
        all_tools = []
        for cat, cat_tools in self.mcp.tools.items():
            for tool in cat_tools:
                all_tools.append({
                    "category": cat,
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {})
                })

        if not all_tools:
            print("[TOOL SELECTION] No MCP tools available")
            return []

        # Use LLM to select relevant tools
        tools_to_call = self._select_tools_with_llm(query, category, diagnosis, all_tools)

        if not tools_to_call:
            print("[TOOL SELECTION] No tools selected by LLM")
            return []

        # Limit to top 3 tools
        tools_to_call = tools_to_call[:3]
        
        results = []
        for tool_info in tools_to_call:
            try:
                # Use LLM to extract arguments from query
                arguments = self._extract_arguments_with_llm(query, tool_info)

                print(f"[TOOL] Executing: {tool_info['category']}/{tool_info['name']} with args: {arguments}")

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
        
        if param_lower in query_lower:
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
        matched_products = self.qdrant.match_products(query)
        
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
        prompt_parts = []
        
        prompt_parts.append("QUERY CONTEXT:")
        prompt_parts.append(f"User query: {query}")
        prompt_parts.append(f"Category: {category}")
        
        if isinstance(diagnosis, dict):
            prompt_parts.append("")
            prompt_parts.append("INITIAL DIAGNOSIS:")
            prompt_parts.append(f"- Problem: {diagnosis.get('problem', 'Not specified')}")
            prompt_parts.append(f"- Urgency: {diagnosis.get('urgency', 'medium')}")
            if diagnosis.get("key_elements"):
                prompt_parts.append(f"- Key elements: {', '.join(diagnosis['key_elements'])}")
        
        if tools_results:
            prompt_parts.append("")
            prompt_parts.append("TOOL RESULTS:")
            for result in tools_results:
                status = "SUCCESS" if result.get("status") == "success" else "FAILED"
                prompt_parts.append(f"- [{status}] {result['tool']}")
                if result.get("result"):
                    # Meilleure extraction des résultats MCP
                    result_data = result["result"]
                    if isinstance(result_data, dict):
                        # Extraire le contenu textuel des résultats MCP
                        if "content" in result_data and isinstance(result_data["content"], list):
                            for item in result_data["content"]:
                                if isinstance(item, dict) and "text" in item:
                                    # Afficher le texte complet (pas de limite de 200 caractères)
                                    text = item["text"].strip()
                                    if text:
                                        prompt_parts.append(f"    {text}")
                        else:
                            # Fallback : afficher tous les champs non-error
                            for k, v in result_data.items():
                                if k != "error" and k != "_error":
                                    # Afficher les valeurs complètes (supprimer la limite de 200)
                                    if isinstance(v, str):
                                        prompt_parts.append(f"    {k}: {v}")
                                    elif isinstance(v, (list, dict)):
                                        prompt_parts.append(f"    {k}: {str(v)[:1000]}...")  # Max 1000 chars pour structures
                                    else:
                                        prompt_parts.append(f"    {k}: {v}")
                    elif isinstance(result_data, str):
                        prompt_parts.append(f"    {result_data}")

                # Afficher les erreurs explicitement
                if result.get("error"):
                    prompt_parts.append(f"    ERROR: {result['error']}")
        
        if docs:
            prompt_parts.append("")
            prompt_parts.append("FOUND DOCUMENTATION:")
            for doc in docs:
                url_info = f" [LINK: {doc.source}]({doc.url})" if doc.url else f" [{doc.source}]"
                prompt_parts.append(f"- {doc.title} (score: {doc.score:.2f}){url_info}")
                prompt_parts.append(f"    > {doc.content[:200]}...")
        
        prompt_parts.append("")
        prompt_parts.append("INSTRUCTIONS:")
        prompt_parts.append("1. Carefully read the TOOL RESULTS - this is real, current data from the infrastructure")
        prompt_parts.append("2. Review the DOCUMENTATION found - this is internal team knowledge")
        prompt_parts.append("3. Answer the user's query using this information")
        prompt_parts.append("4. If this is a diagnostic query, provide:")
        prompt_parts.append("   - Clear problem identification")
        prompt_parts.append("   - Severity level (low, medium, high, critical)")
        prompt_parts.append("   - Numbered resolution steps")
        prompt_parts.append("   - Documentation references")
        prompt_parts.append("5. If this is an informational query, provide:")
        prompt_parts.append("   - Clear, helpful answer based on tool data and docs")
        prompt_parts.append("   - Examples or commands when relevant")
        prompt_parts.append("   - Documentation references if available")
        prompt_parts.append("")
        prompt_parts.append("IMPORTANT: Base your answer on the actual TOOL RESULTS provided above. Use the real data!")
        
        response = self.llm.generate([
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": "\n".join(prompt_parts)}
        ])
        
        return self._format_response(response, query, category, docs, tools_results)
    
    def _get_system_prompt(self) -> str:
        """
        Gets the specialized system prompt for the LLM.

        @return: System prompt string
        """
        return """You are a helpful infrastructure assistant specialized in Kubernetes, OpenSearch, Redis, and Kafka.

YOUR ROLE:
- Answer questions about infrastructure and operations
- Help with troubleshooting and diagnostics when needed
- Explain concepts and provide documentation references
- Use real-time data from MCP tools to give accurate, current information
- Provide guidance based on your team's internal documentation

YOUR CAPABILITIES:
- Access to live infrastructure data via MCP tools (Kubernetes, OpenSearch, Redis, Kafka)
- Access to your team's internal documentation database
- Technical analysis and correlation of information from multiple sources
- Conversational and helpful responses tailored to the user's question

GUIDELINES:
1. **Use the MCP tool results**: If tools were executed, USE the actual data in your response
2. **Be conversational**: Adapt your response style to the question (diagnostic, informational, explanatory, etc.)
3. **Reference documentation**: When relevant docs are found, mention them with their titles
4. **Be precise**: Use exact data from tool outputs (pod names, metrics, status, etc.)
5. **Format appropriately**:
   - For diagnostics: structured format with problem, severity, steps
   - For questions: clear, informative answers
   - For explanations: detailed but concise responses
6. **Use Markdown**: Format your responses with headers, lists, code blocks as appropriate

IMPORTANT: Always base your response on the TOOL RESULTS and DOCUMENTATION provided in the context. Don't ignore the real data!"""
    
    def _format_response(self, llm_response: str, query: str, category: str,
                        docs: List[DocumentationMatch], tools_results: List[Dict]) -> str:
        """
        Formats the final response.
        Handles both structured diagnostic reports and conversational responses.

        @param llm_response: Raw response from LLM
        @param query: Original user query
        @param category: Problem category
        @param docs: List of DocumentationMatch objects
        @param tools_results: List of tool execution results
        @return: Formatted response string
        """
        lines = []

        lines.append("=" * 80)

        # Check if this is a structured diagnostic response
        has_diagnostic_structure = (
            "## IDENTIFIED PROBLEM" in llm_response or
            "## SEVERITY" in llm_response or
            "## RESOLUTION STEPS" in llm_response
        )

        if has_diagnostic_structure:
            lines.append("  DIAGNOSTIC REPORT")
        else:
            lines.append("  INFRASTRUCTURE ASSISTANT")

        lines.append("=" * 80)
        lines.append("")

        # Simply include the LLM response as-is
        # The LLM will format it appropriately based on the query type
        lines.append(llm_response.strip())
        lines.append("")

        # Add metadata at the end
        metadata_added = False

        # Add tools used if not already mentioned in response
        if tools_results:
            tools_used = [r["tool"] for r in tools_results if r.get("status") == "success"]
            if tools_used and "TOOLS USED" not in llm_response:
                if not metadata_added:
                    lines.append("---")
                    lines.append("")
                    metadata_added = True
                lines.append("**Tools Used:**")
                for tool in tools_used:
                    lines.append(f"- `{tool}`")
                lines.append("")

        # Add documentation references if not already mentioned
        if docs and "RELEVANT DOCUMENTATION" not in llm_response and "DOCUMENTATION" not in llm_response:
            if not metadata_added:
                lines.append("---")
                lines.append("")
                metadata_added = True
            lines.append("**Related Documentation:**")
            for doc in docs[:3]:  # Top 3 docs
                url_part = f" - [Link]({doc.url})" if doc.url else ""
                lines.append(f"- {doc.title} (Score: {doc.score:.2f}){url_part}")
            lines.append("")

        if metadata_added:
            lines.append("---")
        else:
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
        print("  DIAGNOSTIC:")
        print("    - 'My app pods are restarting in a loop'")
        print("    - 'OpenSearch is returning 503 errors'")
        print("  INFORMATIONAL:")
        print("    - 'How many pods are running in production?'")
        print("    - 'What is the current status of our Kafka cluster?'")
        print("    - 'Show me Redis memory usage'")
        print("  DOCUMENTATION:")
        print("    - 'How do we handle Redis failover?'")
        print("    - 'What is our Kubernetes deployment process?'")
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
        
        Verifies connectivity to MCP servers, LLM, Embedding, and Qdrant,
        and reports the status of each with detailed error information.
        """
        print("\n" + "=" * 80)
        print("  CONNECTION TESTS")
        print("=" * 80)
        
        print("\n[1] MCP Servers...")
        for category, url in Config.MCP_SERVERS.items():
            tools = self.mcp.tools.get(category, [])
            status = "OK" if tools else "FAILED"
            mcp_url = f"{url}/mcp" if not url.endswith("/mcp") else url
            if tools:
                print(f"   [{status}] {category}: {len(tools)} tools loaded from {mcp_url}")
            else:
                print(f"   [{status}] {category}: Connection failed to {mcp_url}")
        
        print("\n[2] LLM (Gemma4)...")
        try:
            response = self.llm.generate([
                {"role": "user", "content": "Say OK"}
            ])
            print(f"   [OK] Model: {Config.LLM_MODEL}, URL: {Config.LLM_URL}")
        except Exception as e:
            print(f"   [FAILED] Model: {Config.LLM_MODEL}, URL: {Config.LLM_URL}")
            print(f"   Details: {e}")
        
        print("\n[3] Embedding (BGE-M3)...")
        try:
            if self.qdrant.embedding_client:
                test_vector = self.qdrant._get_embedding("test connection")
                print(f"   [OK] Model: {self.qdrant.embedding_model}, URL: {Config.EMBEDDING_URL}")
                print(f"   Vector dimension: {len(test_vector)}")
            else:
                print(f"   [FAILED] Embedding client not initialized")
        except Exception as e:
            print(f"   [FAILED] Model: {self.qdrant.embedding_model}, URL: {Config.EMBEDDING_URL}")
            print(f"   Details: {e}")
        
        print("\n[4] Qdrant...")
        try:
            docs = self.qdrant.search("test", limit=1)
            print(f"   [OK] Collection: {self.qdrant.collection}, Host: {Config.QDRANT_HOST}:{Config.QDRANT_PORT}")
            print(f"   Results: {len(docs)} documents found")
        except Exception as e:
            print(f"   [FAILED] Collection: {self.qdrant.collection}, Host: {Config.QDRANT_HOST}:{Config.QDRANT_PORT}")
            print(f"   Details: {e}")
        
        print("\n" + "=" * 80)
    
    def close(self):
        """
        Closes all connections and cleans up resources.
        """
        self.mcp.close_all()
        self.llm.close()
