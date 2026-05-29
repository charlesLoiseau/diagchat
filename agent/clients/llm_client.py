#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM CLIENT MODULE
=================

Client for interacting with Gemma4 LLM.
Handles communication with the LLM API endpoint and manages
request/response formatting.
"""

import httpx
from typing import List, Dict, Optional
from agent.config import Config


class LLMAPI:
    """
    Client for interacting with Gemma4 LLM.
    
    Handles communication with the LLM API endpoint and manages
    request/response formatting.
    
    @attribute client: HTTP client for LLM API communication
    """
    
    def __init__(self):
        """
        Initializes the LLM client.
        
        Creates an HTTP client with optional Bearer token authentication
        if LLM_API_KEY is configured in environment variables.
        
        @throws Exception: If client initialization fails
        """
        headers = {}
        if Config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {Config.LLM_API_KEY}"
        
        self.client = httpx.Client(
            timeout=Config.LLM_TIMEOUT,
            headers=headers
        )
        self.api_key = Config.LLM_API_KEY
    
    def generate(self, messages: List[Dict], temperature: float = 0.3) -> str:
        """
        Generates a response from the LLM.
        
        @param messages: List of message dictionaries (role, content)
        @param temperature: Sampling temperature (0.0 to 1.0)
        @return: Generated text response from the LLM
        @throws Exception: If LLM request fails
        """
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
            "stream": False
        }
        
        try:
            response = self.client.post(Config.LLM_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract response based on API format
            if 'choices' in data:
                return data['choices'][0]['message']['content']
            elif 'response' in data:
                return data['response']
            elif 'generation' in data:
                return data['generation']
            else:
                return str(data)
                
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return f"LLM Error: {e}"
    
    def close(self):
        """
        Closes the HTTP client connection.
        """
        self.client.close()
