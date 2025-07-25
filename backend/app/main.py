#!/usr/bin/env python3
"""
Healthcare Cost Navigator - FastAPI Application
Main API endpoints for provider search and AI assistant
"""

import os
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import List, Optional
import openai
from database import get_db, init_db
from models import Provider, DRGProcedure, ProviderProcedure, ProviderRating
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Healthcare Cost Navigator",
    description="API for searching hospital costs and getting AI-powered healthcare insights",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI client
openai_client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Pydantic models for API
class ProviderResponse(BaseModel):
    provider_id: str
    provider_name: str
    provider_city: str
    provider_state: str
    provider_zip_code: str
    distance_km: Optional[float] = None
    
    # Procedure info
    drg_code: str
    drg_description: str
    total_discharges: int
    average_covered_charges: float
    average_total_payments: float
    average_medicare_payments: float
    
    # Ratings
    overall_rating: Optional[float] = None
    quality_rating: Optional[float] = None
    safety_rating: Optional[float] = None
    patient_experience_rating: Optional[float] = None

class AskRequest(BaseModel):
    question: str = Field(..., description="Natural language question about healthcare costs or quality")

class AskResponse(BaseModel):
    answer: str
    sql_query: Optional[str] = None
    data_used: Optional[dict] = None

# Utility functions
async def geocode_zip(zip_code: str) -> Optional[tuple]:
    """Get coordinates for a ZIP code using PostGIS/geocoding"""
    # For MVP, we'll use a simple lookup or return None
    # In production, integrate with a geocoding service
    return None

def build_radius_query(zip_code: str, radius_km: float):
    """Build SQL for radius-based search"""
    # For now, we'll search by ZIP code similarity
    # In production with geocoding, we'd use ST_DWithin
    return text(f"provider_zip_code LIKE '{zip_code[:3]}%'")

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Healthcare Cost Navigator API", "status": "healthy"}

@app.get("/providers", response_model=List[ProviderResponse])
async def search_providers(
    drg: str = Query(..., description="DRG code or description to search for"),
    zip: str = Query(..., description="ZIP code for location-based search"),
    radius_km: float = Query(50.0, description="Search radius in kilometers"),
    limit: int = Query(20, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search for hospitals offering a specific DRG procedure within a radius
    Returns hospitals sorted by average covered charges (lowest first)
    """
    try:
        # Build query to find providers with the specified DRG
        # Support both exact DRG code match and description search
        
        # Check if drg is a numeric code or description
        if drg.isdigit():
            # Exact DRG code match
            drg_condition = DRGProcedure.drg_code == drg
        else:
            # Text search in description using ILIKE
            drg_condition = DRGProcedure.drg_description.ilike(f"%{drg}%")
        
        # Build the main query
        query = (
            select(
                Provider,
                ProviderProcedure,
                DRGProcedure,
                ProviderRating
            )
            .select_from(Provider)
            .join(ProviderProcedure, Provider.provider_id == ProviderProcedure.provider_id)
            .join(DRGProcedure, ProviderProcedure.drg_code == DRGProcedure.drg_code)
            .outerjoin(ProviderRating, Provider.provider_id == ProviderRating.provider_id)
            .where(drg_condition)
        )
        
        # Add location filter (simplified for MVP - using ZIP prefix matching)
        if zip and len(zip) >= 3:
            query = query.where(Provider.provider_zip_code.like(f"{zip[:3]}%"))
        
        # Order by cost (lowest first) and limit results
        query = query.order_by(ProviderProcedure.average_covered_charges.asc()).limit(limit)
        
        result = await db.execute(query)
        rows = result.all()
        
        # Transform results
        providers = []
        for provider, procedure, drg, rating in rows:
            provider_data = ProviderResponse(
                provider_id=provider.provider_id,
                provider_name=provider.provider_name,
                provider_city=provider.provider_city,
                provider_state=provider.provider_state,
                provider_zip_code=provider.provider_zip_code,
                drg_code=drg.drg_code,
                drg_description=drg.drg_description,
                total_discharges=procedure.total_discharges,
                average_covered_charges=float(procedure.average_covered_charges),
                average_total_payments=float(procedure.average_total_payments),
                average_medicare_payments=float(procedure.average_medicare_payments),
                overall_rating=float(rating.overall_rating) if rating else None,
                quality_rating=float(rating.quality_rating) if rating else None,
                safety_rating=float(rating.safety_rating) if rating else None,
                patient_experience_rating=float(rating.patient_experience_rating) if rating else None
            )
            providers.append(provider_data)
        
        return providers
        
    except Exception as e:
        logger.error(f"Error searching providers: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/ask", response_model=AskResponse)
async def ask_ai_assistant(
    request: AskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Natural language interface for healthcare cost and quality queries
    Uses OpenAI to convert natural language to database queries
    """
    try:
        # Check if question is healthcare-related
        if not is_healthcare_related(request.question):
            return AskResponse(
                answer="I can only help with hospital pricing and quality information. Please ask about medical procedures, costs, or hospital ratings."
            )
        
        # Generate SQL query using OpenAI
        sql_query = await generate_sql_from_question(request.question)
        
        if not sql_query:
            return AskResponse(
                answer="I couldn't understand your question. Please try asking about specific procedures, costs, or hospital ratings."
            )
        
        # Execute the generated query safely
        query_result = await execute_safe_query(db, sql_query)
        
        # Generate natural language response
        answer = await generate_natural_response(request.question, query_result, sql_query)
        
        return AskResponse(
            answer=answer,
            sql_query=sql_query,
            data_used=query_result
        )
        
    except Exception as e:
        logger.error(f"Error in AI assistant: {e}")
        return AskResponse(
            answer="I'm sorry, I encountered an error while processing your question. Please try rephrasing your question."
        )

def is_healthcare_related(question: str) -> bool:
    """Check if question is related to healthcare/medical topics"""
    healthcare_keywords = [
        'hospital', 'procedure', 'surgery', 'cost', 'price', 'drg', 'rating',
        'quality', 'safety', 'medicare', 'medical', 'treatment', 'doctor',
        'patient', 'clinic', 'discharge', 'payment', 'cheap', 'expensive',
        'best', 'worst', 'near', 'location'
    ]
    
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in healthcare_keywords)

async def generate_sql_from_question(question: str) -> Optional[str]:
    """Use OpenAI to convert natural language to SQL query"""
    
    system_prompt = """
    You are an expert SQL query generator for a healthcare cost database. 
    
    Database Schema:
    - providers: provider_id, provider_name, provider_city, provider_state, provider_zip_code
    - drg_procedures: drg_code, drg_description
    - provider_procedures: provider_id, drg_code, total_discharges, average_covered_charges, average_total_payments, average_medicare_payments
    - provider_ratings: provider_id, overall_rating, quality_rating, safety_rating, patient_experience_rating
    
    Generate a safe SQL SELECT query based on the user's question. 
    - Only use SELECT statements
    - Include appropriate JOINs between tables
    - Use LIMIT to restrict results (max 20)
    - For cost queries, order by average_covered_charges ASC (cheapest first)
    - For quality queries, order by overall_rating DESC (best first)
    - Use ILIKE for text matching
    
    Return only the SQL query, no explanation.
    """
    
    try:
        response = await openai_client.chat.completions.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=300,
            temperature=0.1
        )
        
        sql_query = response.choices[0].message.content.strip()
        
        # Basic safety check - only allow SELECT queries
        if not sql_query.lower().strip().startswith('select'):
            return None
            
        return sql_query
        
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        return None

async def execute_safe_query(db: AsyncSession, sql_query: str) -> dict:
    """Execute SQL query safely and return results"""
    try:
        # Additional safety check
        if not sql_query.lower().strip().startswith('select'):
            raise ValueError("Only SELECT queries are allowed")
        
        result = await db.execute(text(sql_query))
        rows = result.fetchall()
        columns = result.keys()
        
        # Convert to list of dictionaries
        data = []
        for row in rows:
            row_dict = {col: row[i] for i, col in enumerate(columns)}
            data.append(row_dict)
        
        return {
            "rows": data,
            "count": len(data),
            "columns": list(columns)
        }
        
    except Exception as e:
        logger.error(f"Error executing query: {e}")
        return {"error": str(e), "rows": [], "count": 0}

async def generate_natural_response(question: str, query_result: dict, sql_query: str) -> str:
    """Generate natural language response from query results"""
    
    if "error" in query_result:
        return "I encountered an error while searching the database. Please try rephrasing your question."
    
    if query_result["count"] == 0:
        return "I couldn't find any matching results for your question. Please try a different search."
    
    # Use OpenAI to generate a natural response
    system_prompt = """
    You are a helpful healthcare cost assistant. Based on the user's question and the database results, 
    provide a clear, helpful answer. Focus on the most relevant information and present it in a 
    conversational tone. Include specific numbers when available.
    """
    
    context = f"""
    User Question: {question}
    
    Database Results: {query_result}
    
    Please provide a helpful answer based on this data.
    """
    
    try:
        response = await openai_client.chat.completions.acreate(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        # Fallback to basic response
        if query_result["count"] > 0:
            return f"I found {query_result['count']} results for your question. Here's what I found: {query_result['rows'][0]}"
        return "I found some results but couldn't generate a detailed response."

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Starting Healthcare Cost Navigator API")
    await init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 