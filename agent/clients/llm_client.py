#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM CLIENT MODULE
=================

Client for interacting with OpenAI-compatible LLM API.
Handles communication with the LLM API endpoint using the OpenAI client.
"""

from typing import List, Dict
import openai
from agent.config import Config


class LLMAPI:
    """
    Client for interacting with OpenAI-compatible LLM API.
    
    Uses the official OpenAI Python client to communicate with
    OpenAI-compatible endpoints (including local LLM servers).
    
    @attribute client: OpenAI client instance
    @attribute model: Model name to use for completions
    """
    
    def __init__(self):
        """
        Initializes the LLM client.
        
        Creates an OpenAI client configured with the API key and base URL
        from environment variables. Supports multiple models on the same endpoint.
        
        @throws Exception: If client initialization fails
        """
        self.client = openai.OpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_URL,
            timeout=Config.LLM_TIMEOUT
        )
        self.model = Config.LLM_MODEL
    
    def generate(self, messages: List[Dict], temperature: float = 0.3) -> str:
        """
        Generates a response from the LLM using OpenAI-compatible API.
        
        @param messages: List of message dictionaries (role, content)
        @param temperature: Sampling temperature (0.0 to 1.0)
        @return: Generated text response from the LLM
        @throws Exception: If LLM request fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,
                stream=False
            )
            
            return response.choices[0].message.content
                
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return f"LLM Error: {e}"
    
    def close(self):
        """
        Closes the OpenAI client connection.
        """
        self.client.close()
