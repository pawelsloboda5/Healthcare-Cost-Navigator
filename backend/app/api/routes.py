"""
API Routes for Healthcare Cost Navigator
Enhanced routes with RAG-powered AI assistant and comprehensive provider search
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
import logging

from ..core.database import get_db
from ..services.ai_service import EnhancedAIService, QueryResult
from ..services.provider_service import ProviderService, ProviderSearchCriteria, CostAnalysis
from ..core.config import settings

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Initialize services
ai_service = EnhancedAIService()
provider_service = ProviderService()

# Pydantic models
class ProviderResponse(BaseModel):
    provider_id: str
    provider_name: str
    provider_city: str
    provider_state: str
    provider_zip_code: str
    distance_km: Optional[float] = None
    
    # Procedure info (when applicable)
    drg_code: Optional[str] = None
    drg_description: Optional[str] = None
    total_discharges: Optional[int] = None
    average_covered_charges: Optional[float] = None
    average_total_payments: Optional[float] = None
    average_medicare_payments: Optional[float] = None
    
    # Ratings
    overall_rating: Optional[float] = None
    quality_rating: Optional[float] = None
    safety_rating: Optional[float] = None
    patient_experience_rating: Optional[float] = None

class ProviderSearchRequest(BaseModel):
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    drg_code: Optional[str] = None
    min_rating: Optional[float] = Field(None, ge=1.0, le=10.0)
    max_cost: Optional[float] = Field(None, gt=0)
    min_volume: Optional[int] = Field(None, gt=0)
    limit: Optional[int] = Field(20, le=settings.MAX_QUERY_LIMIT)

class AskRequest(BaseModel):
    question: str = Field(..., description="Natural language question about healthcare costs or quality")
    use_template_matching: bool = Field(True, description="Whether to use template matching for faster responses")

class AskResponse(BaseModel):
    success: bool
    answer: str
    sql_query: Optional[str] = None
    results: Optional[List[dict]] = None
    template_used: Optional[int] = None
    confidence_score: Optional[float] = None
    execution_time_ms: Optional[int] = None

class CostAnalysisResponse(BaseModel):
    drg_code: str
    drg_description: Optional[str] = None
    cheapest_provider: dict
    most_expensive_provider: dict
    average_cost: float
    median_cost: float
    cost_variance: float
    total_providers: int

# Health and status endpoints
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Healthcare Cost Navigator API"}

@router.get("/template-stats")
async def get_template_statistics(db: AsyncSession = Depends(get_db)):
    """Get template catalog statistics"""
    try:
        from ..utils.vector_search import VectorSearchEngine
        import openai
        
        openai_client = openai.AsyncClient(api_key=settings.OPENAI_API_KEY)
        vector_engine = VectorSearchEngine(openai_client)
        
        stats = await vector_engine.get_template_statistics(db)
        return {"template_statistics": stats}
        
    except Exception as e:
        logger.error(f"Failed to get template statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve template statistics")

# Enhanced AI assistant endpoint
@router.post("/ask", response_model=AskResponse)
async def ask_ai_assistant(
    request: AskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Enhanced natural language interface for healthcare cost and quality queries
    Uses RAG with template matching and comprehensive safety validation
    """
    import time
    start_time = time.time()
    
    try:
        # Process the query using enhanced AI service
        result: QueryResult = await ai_service.process_natural_language_query(
            session=db,
            user_query=request.question,
            use_template_matching=request.use_template_matching
        )
        
        # Generate natural language explanation if successful
        explanation = ""
        if result.success and result.results:
            explanation = await ai_service.explain_query_results(
                user_query=request.question,
                sql_query=result.sql_query or "",
                results=result.results
            )
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return AskResponse(
            success=result.success,
            answer=explanation if explanation else result.message,
            sql_query=result.sql_query,
            results=result.results,
            template_used=result.template_used,
            confidence_score=result.confidence_score,
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        logger.error(f"Error in AI assistant: {e}")
        execution_time = int((time.time() - start_time) * 1000)
        
        return AskResponse(
            success=False,
            answer="I'm sorry, I encountered an error while processing your question. Please try rephrasing your question.",
            execution_time_ms=execution_time
        )

# Provider search endpoints
@router.post("/providers/search", response_model=List[ProviderResponse])
async def search_providers_advanced(
    request: ProviderSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Advanced provider search with multiple criteria
    """
    try:
        criteria = ProviderSearchCriteria(
            state=request.state,
            city=request.city,
            zip_code=request.zip_code,
            drg_code=request.drg_code,
            min_rating=request.min_rating,
            max_cost=request.max_cost,
            min_volume=request.min_volume
        )
        
        providers = await provider_service.search_providers(
            session=db,
            criteria=criteria,
            limit=request.limit or settings.DEFAULT_QUERY_LIMIT
        )
        
        return [ProviderResponse(**provider) for provider in providers]
        
    except Exception as e:
        logger.error(f"Provider search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Provider search failed: {str(e)}")

@router.get("/providers/cheapest/{drg_code}", response_model=List[ProviderResponse])
async def get_cheapest_providers(
    drg_code: str,
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(10, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db)
):
    """Find cheapest providers for a specific DRG procedure"""
    try:
        if not provider_service.validate_drg_code(drg_code):
            raise HTTPException(status_code=400, detail="Invalid DRG code format")
        
        providers = await provider_service.get_cheapest_providers_for_procedure(
            session=db,
            drg_code=drg_code,
            state=state,
            limit=limit
        )
        
        if not providers:
            raise HTTPException(status_code=404, detail=f"No providers found for DRG {drg_code}")
        
        return [ProviderResponse(**provider) for provider in providers]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cheapest providers search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to find cheapest providers")

@router.get("/providers/highest-rated", response_model=List[ProviderResponse])
async def get_highest_rated_providers(
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(10, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db)
):
    """Find highest rated providers in a geographic area"""
    try:
        if state and not provider_service.validate_state_code(state):
            raise HTTPException(status_code=400, detail="Invalid state code")
        
        providers = await provider_service.get_highest_rated_providers(
            session=db,
            state=state,
            city=city,
            limit=limit
        )
        
        return [ProviderResponse(**provider) for provider in providers]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Highest rated providers search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to find highest rated providers")

@router.get("/providers/volume-leaders/{drg_code}", response_model=List[ProviderResponse])
async def get_volume_leaders(
    drg_code: str,
    limit: int = Query(10, le=50, description="Number of results"),
    db: AsyncSession = Depends(get_db)
):
    """Find providers with highest volume for a specific procedure"""
    try:
        if not provider_service.validate_drg_code(drg_code):
            raise HTTPException(status_code=400, detail="Invalid DRG code format")
        
        providers = await provider_service.get_procedure_volume_leaders(
            session=db,
            drg_code=drg_code,
            limit=limit
        )
        
        if not providers:
            raise HTTPException(status_code=404, detail=f"No providers found for DRG {drg_code}")
        
        return [ProviderResponse(**provider) for provider in providers]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Volume leaders search failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to find volume leaders")

@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider_details(
    provider_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information for a specific provider"""
    try:
        provider = await provider_service.get_provider_details(
            session=db,
            provider_id=provider_id
        )
        
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
        
        return ProviderResponse(**provider)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Provider details lookup failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve provider details")

# Cost analysis endpoints
@router.get("/analysis/costs/{drg_code}", response_model=CostAnalysisResponse)
async def analyze_procedure_costs(
    drg_code: str,
    state: Optional[str] = Query(None, description="Filter by state"),
    db: AsyncSession = Depends(get_db)
):
    """Analyze cost distribution for a specific procedure"""
    try:
        if not provider_service.validate_drg_code(drg_code):
            raise HTTPException(status_code=400, detail="Invalid DRG code format")
        
        if state and not provider_service.validate_state_code(state):
            raise HTTPException(status_code=400, detail="Invalid state code")
        
        analysis = await provider_service.analyze_procedure_costs(
            session=db,
            drg_code=drg_code,
            state=state
        )
        
        if not analysis:
            raise HTTPException(status_code=404, detail=f"No cost data found for DRG {drg_code}")
        
        return CostAnalysisResponse(
            drg_code=drg_code,
            **analysis.__dict__
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cost analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Cost analysis failed")

# Legacy endpoint for backward compatibility
@router.get("/providers", response_model=List[ProviderResponse])
async def search_providers_legacy(
    drg: str = Query(..., description="DRG code or description to search for"),
    zip: str = Query(..., description="ZIP code for location-based search"),
    radius_km: float = Query(50.0, description="Search radius in kilometers"),
    limit: int = Query(20, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy provider search endpoint for backward compatibility
    """
    try:
        # Convert legacy parameters to new search criteria
        criteria = ProviderSearchCriteria()
        
        # Handle DRG code or description
        if drg.isdigit():
            criteria.drg_code = drg
        # For description search, we'll use the enhanced AI service
        
        # Simplified ZIP-based location search
        if zip and len(zip) >= 3:
            criteria.zip_code = zip[:5] if len(zip) == 5 else None
            # For broader search, use state from ZIP (simplified)
        
        providers = await provider_service.search_providers(
            session=db,
            criteria=criteria,
            limit=limit
        )
        
        # Convert to legacy format
        legacy_providers = []
        for provider in providers:
            legacy_provider = ProviderResponse(**provider)
            legacy_providers.append(legacy_provider)
        
        return legacy_providers
        
    except Exception as e:
        logger.error(f"Legacy provider search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
