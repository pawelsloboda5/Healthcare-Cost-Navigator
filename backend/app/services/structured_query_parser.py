"""
Structured Query Parser using OpenAI Responses API
Extracts structured parameters from natural language queries
"""
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum
import openai
import logging

logger = logging.getLogger(__name__)

class QueryType(Enum):
    CHEAPEST_PROVIDER = "cheapest_provider"
    HIGHEST_RATED = "highest_rated" 
    COST_COMPARISON = "cost_comparison"
    VOLUME_ANALYSIS = "volume_analysis"
    STATE_COMPARISON = "state_comparison"

@dataclass
class StructuredQuery:
    """Structured representation of a natural language query"""
    query_type: QueryType
    procedure: Optional[str] = None
    drg_code: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    states: Optional[List[str]] = None  # plural list for comparisons
    min_rating: Optional[float] = None
    max_cost: Optional[float] = None
    limit: Optional[int] = None
    # Derived flags (not required by upstream callers, but useful for routing)
    # cost_direction: "cheapest" | "expensive" | None – inferred in service

class StructuredQueryParser:
    """Parse natural language to structured query parameters using OpenAI function calling"""
    
    def __init__(self, openai_client: openai.AsyncClient):
        self.openai_client = openai_client
        
    async def parse_query(self, user_query: str) -> StructuredQuery:
        """
        Parse natural language query into structured parameters
        
        Args:
            user_query: Natural language query like "cheapest hip replacement in NY"
            
        Returns:
            StructuredQuery with extracted parameters
        """
        try:
            # Define the function schema for structured extraction
            function_schema = {
                "name": "extract_healthcare_query_parameters",
                "description": "Extract structured parameters from a healthcare cost/quality query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": [
                                "cheapest_provider",
                                "highest_rated",
                                "cost_comparison",
                                "volume_analysis",
                                "state_comparison"
                            ],
                            "description": "The type of healthcare query being made"
                        },
                        "procedure": {
                            "type": "string",
                            "description": "Medical procedure or treatment (e.g., 'hip replacement', 'heart surgery')"
                        },
                        "drg_code": {
                            "type": "string",
                            "description": "DRG code if specifically mentioned (e.g., '470')"
                        },
                        "state": {
                            "type": "string",
                            "description": "US state name or code (e.g., 'NY', 'New York', 'California')"
                        },
                        "city": {
                            "type": "string", 
                            "description": "City name (e.g., 'Los Angeles', 'Miami')"
                        },
                        "zip_code": {
                        "type": "string",
                        "description": "ZIP code if mentioned"
                        },
                        "states": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of state codes for comparison (e.g., ['NY','CA'])"
                        },
                        "min_rating": {
                            "type": "number",
                            "description": "Minimum quality rating if specified"
                        },
                        "max_cost": {
                            "type": "number",
                            "description": "Maximum cost limit if specified"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results requested (default: 10)"
                        }
                    },
                    "required": ["query_type"]
                }
            }
            
            # Use function calling to extract structured data
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a healthcare query parameter extractor. Extract structured information from natural language healthcare queries."
                    },
                    {
                        "role": "user",
                        "content": f"Extract parameters from this healthcare query: {user_query}"
                    }
                ],
                functions=[function_schema],
                function_call={"name": "extract_healthcare_query_parameters"},
                temperature=0.1
            )
            
            # Parse the function call result
            function_call = response.choices[0].message.function_call
            if function_call and function_call.name == "extract_healthcare_query_parameters":
                import json
                params = json.loads(function_call.arguments)
                
                # Normalize state names
                if params.get("state"):
                    params["state"] = self._normalize_state(params["state"])
                if params.get("states"):
                    params["states"] = [self._normalize_state(s) for s in params["states"]]
                
                # Force STATE_COMPARISON when comparing multiple states, unless it's explicitly a ratings query
                if params.get("states") and len(params["states"]) >= 2:
                    if params.get("query_type") != "highest_rated":
                        params["query_type"] = "state_comparison"

                # Ratings override by text cue (extra guard)
                text_lower = str(user_query).lower()
                if any(kw in text_lower for kw in ["highest rated", "top rated", "best rated"]):
                    params["query_type"] = "highest_rated"

                # Deterministic DRG code extraction as a guardrail for LLM misses
                if not params.get("drg_code") and isinstance(user_query, str):
                    import re as _re
                    m = _re.search(r"\b(?:DRG\s*)?(\d{3})\b", user_query, _re.IGNORECASE)
                    if m:
                        params["drg_code"] = m.group(1)

                # Set default limit
                if not params.get("limit"):
                    params["limit"] = 10
                    
                return StructuredQuery(
                    query_type=QueryType(params["query_type"]),
                    procedure=params.get("procedure"),
                    drg_code=params.get("drg_code"),
                    state=params.get("state"),
                    city=params.get("city"),
                    zip_code=params.get("zip_code"),
                    states=params.get("states"),
                    min_rating=params.get("min_rating"),
                    max_cost=params.get("max_cost"),
                    limit=params.get("limit", 10)
                )
            
            # Fallback if function calling fails
            logger.warning(f"Function calling failed for query: {user_query}")
            return StructuredQuery(query_type=QueryType.CHEAPEST_PROVIDER)
            
        except Exception as e:
            logger.error(f"Query parsing failed: {e}")
            return StructuredQuery(query_type=QueryType.CHEAPEST_PROVIDER)
    
    def _normalize_state(self, state: str) -> str:
        """Normalize state names to 2-letter codes"""
        state_mapping = {
            'new york': 'NY',
            'california': 'CA', 
            'florida': 'FL',
            'texas': 'TX',
            'illinois': 'IL',
            # Add more as needed
        }
        
        state_lower = state.lower()
        if state_lower in state_mapping:
            return state_mapping[state_lower]
        elif len(state) == 2:
            return state.upper()
        else:
            return state 