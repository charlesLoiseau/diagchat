#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QDRANT CLIENT MODULE
====================

Qdrant client optimized for documentation search.
Handles connection to Qdrant vector database and performs
semantic search on documentation collection.
"""

from typing import Optional, List, Set
import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from agent.config import Config
from agent.models import DocumentationMatch


class QdrantDiagnostic:
    """
    Qdrant client optimized for documentation search.
    
    Handles connection to Qdrant vector database and performs
    semantic search on documentation collection.
    
    @attribute client: QdrantClient instance
    @attribute collection: Name of the collection to search in
    """
    
    def __init__(self):
        """
        Initializes the Qdrant client and detects the collection.
        Loads the list of available products from the collection payloads.
        Initializes the embedding client for BGE-M3 or similar models.
        
        @throws Exception: If connection to Qdrant or embedding service fails
        """
        try:
            self.client = QdrantClient(
                host=Config.QDRANT_HOST,
                port=Config.QDRANT_PORT,
                timeout=Config.QDRANT_TIMEOUT
            )
            self.collection = self._detect_collection()
            print(f"[Qdrant] Collection detected: {self.collection}")
            self.products = self._load_products()
            print(f"[Qdrant] Loaded {len(self.products)} products: {self.products}")
        except Exception as e:
            print(f"[Qdrant] Error: {e}")
            self.client = None
            self.collection = Config.QDRANT_COLLECTION
            self.products = []
        
        embedding_api_key = Config.EMBEDDING_API_KEY or Config.LLM_API_KEY
        try:
            self.embedding_client = openai.OpenAI(
                api_key=embedding_api_key,
                base_url=Config.EMBEDDING_URL,
                timeout=Config.EMBEDDING_TIMEOUT
            )
            self.embedding_model = Config.EMBEDDING_MODEL
            print(f"[Embedding] Model: {self.embedding_model}")
        except Exception as e:
            print(f"[Embedding] Error: {e}")
            self.embedding_client = None
            self.embedding_model = "bge-m3"
    
    def _detect_collection(self) -> str:
        """
        Detects the first available collection in Qdrant.
        
        @return: Name of the first collection, or default from config
        """
        try:
            collections = self.client.get_collections()
            if collections and collections.collections:
                return collections.collections[0].name
        except:
            pass
        return Config.QDRANT_COLLECTION

    def _load_products(self) -> List[str]:
        """
        Loads the list of unique products from Qdrant collection payloads.
        Extracts values from the 'product' field in all points.
        
        @return: List of unique product names found in the collection
        """
        if not self.client:
            return []
        
        try:
            products: Set[str] = set()
            points, _ = self.client.scroll(
                collection_name=self.collection,
                limit=10000,
                with_payload=True
            )
            
            for point in points:
                payload = point.payload
                if payload and 'product' in payload:
                    product = payload['product']
                    if isinstance(product, str):
                        products.add(product)
            
            return sorted(list(products))
        except Exception as e:
            print(f"[Qdrant] Error loading products: {e}")
            return []

    def match_products(self, query: str) -> List[str]:
        """
        Identifies which products from the collection match the user query.
        Performs case-insensitive partial matching against product names.
        
        @param query: The user query string
        @return: List of matching product names from the collection
        """
        if not self.products:
            return []
        
        query_lower = query.lower()
        matched = []
        
        for product in self.products:
            if query_lower in product.lower():
                matched.append(product)
        
        return matched
    
    def search(self, query: str, limit: int = 5, products: Optional[List[str]] = None) -> List[DocumentationMatch]:
        """
        Searches Qdrant for relevant documentation.
        
        @param query: The search query string
        @param limit: Maximum number of results to return
        @param products: Optional list of product names to filter by
        @return: List of DocumentationMatch objects sorted by relevance score
        @throws Exception: If search operation fails
        """
        if not self.client:
            return []
        
        try:
            embedding = self._get_embedding(query)
            
            search_filter = None
            if products:
                search_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="product",
                            match=models.MatchAny(any=products)
                        )
                    ]
                )
            
            results = self.client.query_points(
                collection_name=self.collection,
                query=[embedding],
                limit=limit,
                with_payload=True,
                query_filter=search_filter
            )
            
            matches = []
            for r in results:
                payload = r.payload
                content = payload.get("text", payload.get("content", ""))
                url = payload.get("url", payload.get("link", 
                            payload.get("metadata", {}).get("url")))
                source = payload.get("source", 
                            payload.get("metadata", {}).get("source", "unknown"))
                title = payload.get("title", content[:50])
                
                matches.append(DocumentationMatch(
                    title=title,
                    content=content,
                    url=url,
                    source=source,
                    score=r.score
                ))
            
            matches.sort(key=lambda x: x.score, reverse=True)
            return matches
            
        except Exception as e:
            print(f"[Qdrant Search] Error: {e}")
            return []
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Gets the embedding vector for a text using the BGE-M3 model via OpenAI-compatible API.
        
        @param text: Input text to embed
        @return: Vector of floats representing the embedding
        @throws Exception: If embedding service is not available
        """
        if not self.embedding_client:
            raise Exception("Embedding client not initialized")
        
        response = self.embedding_client.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        return response.data[0].embedding
