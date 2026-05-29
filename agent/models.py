#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DATA MODELS MODULE
==================

Defines the data structures used by the diagnostic agent.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class DocumentationMatch:
    """
    Represents a documentation entry found in Qdrant.
    
    @attribute title: The title of the documentation entry
    @attribute content: The content text of the documentation
    @attribute url: Optional URL to the documentation source
    @attribute source: The source of the documentation
    @attribute score: Relevance score from Qdrant search (0.0 to 1.0)
    """
    title: str
    content: str
    url: Optional[str]
    source: str
    score: float


@dataclass 
class DiagnosticReport:
    """
    Complete diagnostic report structure.
    
    @attribute problem: Description of the identified problem
    @attribute category: Category of the issue (kubernetes, opensearch, redis, kafka, general)
    @attribute severity: Severity level (low, medium, high, critical)
    @attribute documentation: List of relevant DocumentationMatch objects
    @attribute solution_steps: List of actionable resolution steps
    @attribute tools_used: List of MCP tools that were executed
    @attribute raw_data: Dictionary containing raw diagnostic data
    """
    problem: str
    category: str
    severity: str
    documentation: List[DocumentationMatch]
    solution_steps: List[str]
    tools_used: List[str]
    raw_data: Dict[str, Any]
