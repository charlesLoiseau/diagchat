#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLI ENTRY POINT
==============

Main entry point for the diagnostic agent CLI application.
Launches the DiagnosticAgent in interactive chat mode.
Loads configuration from .env file if present.
"""

from dotenv import load_dotenv

load_dotenv()

from agent.diagnostic_agent import DiagnosticAgent


if __name__ == "__main__":
    agent = DiagnosticAgent()
    
    agent.test_connections()
    
    agent.chat()
    
    agent.close()
