"""
Provider Service
Healthcare-specific business logic and data operations
"""
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, and_, or_
import logging
from dataclasses import dataclass
from enum import Enum

from ..models.models import Provider, DRGProcedure, ProviderProcedure, ProviderRating

logger = logging.getLogger(__name__)

class SortOrder(Enum):
    ASC = "ASC"
    DESC = "DESC"

@dataclass
class ProviderSearchCriteria:
    """Criteria for searching providers"""
    state: Optional[str] = None
    city: Optional[str] = None
    zip_code: Optional[str] = None
    drg_code: Optional[str] = None
    min_rating: Optional[float] = None
    max_cost: Optional[float] = None
    min_volume: Optional[int] = None
    
@dataclass
class CostAnalysis:
    """Cost analysis results"""
    cheapest_provider: Dict
    most_expensive_provider: Dict
    average_cost: float
    median_cost: float
    cost_variance: float
    total_providers: int

class ProviderService:
    """
    Service for healthcare provider operations and business logic
    """
    
    def __init__(self):
        pass
    
    async def search_providers(
        self,
        session: AsyncSession,
        criteria: ProviderSearchCriteria,
        limit: int = 50
    ) -> List[Dict]:
        """
        Search providers based on multiple criteria
        
        Args:
            session: Database session
            criteria: Search criteria
            limit: Maximum results to return
            
        Returns:
            List of provider dictionaries
        """
        try:
            # Build dynamic query based on criteria
            base_query = """
                SELECT DISTINCT
                    p.provider_id,
                    p.provider_name,
                    p.provider_city,
                    p.provider_state,
                    p.provider_zip_code,
                    pr.overall_rating,
                    pr.quality_rating,
                    pr.safety_rating
                FROM providers p
                LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
            """
            
            where_conditions = []
            params = {}
            
            if criteria.state:
                where_conditions.append("p.provider_state = :state")
                params["state"] = criteria.state
                
            if criteria.city:
                where_conditions.append("p.provider_city ILIKE :city")
                params["city"] = f"%{criteria.city}%"
                
            if criteria.zip_code:
                where_conditions.append("p.provider_zip_code = :zip_code")
                params["zip_code"] = criteria.zip_code
                
            if criteria.min_rating:
                where_conditions.append("pr.overall_rating >= :min_rating")
                params["min_rating"] = criteria.min_rating
            
            # Add JOIN and conditions for DRG-specific criteria
            if criteria.drg_code or criteria.max_cost or criteria.min_volume:
                base_query += " JOIN provider_procedures pp ON p.provider_id = pp.provider_id"
                
                if criteria.drg_code:
                    where_conditions.append("pp.drg_code = :drg_code")
                    params["drg_code"] = criteria.drg_code
                    
                if criteria.max_cost:
                    where_conditions.append("pp.average_covered_charges <= :max_cost")
                    params["max_cost"] = criteria.max_cost
                    
                if criteria.min_volume:
                    where_conditions.append("pp.total_discharges >= :min_volume")
                    params["min_volume"] = criteria.min_volume
            
            # Add WHERE clause if conditions exist
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            base_query += f" ORDER BY pr.overall_rating DESC NULLS LAST LIMIT :limit"
            params["limit"] = limit
            
            result = await session.execute(text(base_query), params)
            
            providers = []
            for row in result:
                provider = {
                    "provider_id": row.provider_id,
                    "provider_name": row.provider_name,
                    "provider_city": row.provider_city,
                    "provider_state": row.provider_state,
                    "provider_zip_code": row.provider_zip_code,
                    "overall_rating": float(row.overall_rating) if row.overall_rating else None,
                    "quality_rating": float(row.quality_rating) if row.quality_rating else None,
                    "safety_rating": float(row.safety_rating) if row.safety_rating else None
                }
                providers.append(provider)
            
            logger.info(f"Found {len(providers)} providers matching criteria")
            return providers
            
        except Exception as e:
            logger.error(f"Provider search failed: {e}")
            return []
    
    async def get_cheapest_providers_for_procedure(
        self,
        session: AsyncSession,
        drg_code: str,
        state: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find cheapest providers for a specific procedure
        
        Args:
            session: Database session
            drg_code: DRG code for the procedure
            state: Optional state filter
            limit: Number of results to return
            
        Returns:
            List of provider cost information
        """
        try:
            query = """
                SELECT 
                    p.provider_id,
                    p.provider_name,
                    p.provider_city,
                    p.provider_state,
                    pp.average_covered_charges,
                    pp.average_total_payments,
                    pp.average_medicare_payments,
                    pp.total_discharges,
                    pr.overall_rating,
                    d.drg_description
                FROM providers p
                JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                JOIN drg_procedures d ON pp.drg_code = d.drg_code
                LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                WHERE pp.drg_code = :drg_code
            """
            
            params = {"drg_code": drg_code}
            
            if state:
                query += " AND p.provider_state = :state"
                params["state"] = state
            
            query += " ORDER BY pp.average_covered_charges ASC LIMIT :limit"
            params["limit"] = limit
            
            result = await session.execute(text(query), params)
            
            providers = []
            for row in result:
                provider = {
                    "provider_id": row.provider_id,
                    "provider_name": row.provider_name,
                    "provider_city": row.provider_city,
                    "provider_state": row.provider_state,
                    "average_covered_charges": float(row.average_covered_charges),
                    "average_total_payments": float(row.average_total_payments),
                    "average_medicare_payments": float(row.average_medicare_payments),
                    "total_discharges": int(row.total_discharges),
                    "overall_rating": float(row.overall_rating) if row.overall_rating else None,
                    "drg_description": row.drg_description
                }
                providers.append(provider)
            
            logger.info(f"Found {len(providers)} cheapest providers for DRG {drg_code}")
            return providers
            
        except Exception as e:
            logger.error(f"Cheapest provider search failed: {e}")
            return []
    
    async def get_highest_rated_providers(
        self,
        session: AsyncSession,
        state: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find highest rated providers in a geographic area
        
        Args:
            session: Database session
            state: Optional state filter
            city: Optional city filter
            limit: Number of results to return
            
        Returns:
            List of highest rated providers
        """
        try:
            query = """
                SELECT 
                    p.provider_id,
                    p.provider_name,
                    p.provider_city,
                    p.provider_state,
                    p.provider_zip_code,
                    pr.overall_rating,
                    pr.quality_rating,
                    pr.safety_rating,
                    pr.patient_experience_rating
                FROM providers p
                JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                WHERE pr.overall_rating IS NOT NULL
            """
            
            params = {}
            
            if state:
                query += " AND p.provider_state = :state"
                params["state"] = state
                
            if city:
                query += " AND p.provider_city ILIKE :city"
                params["city"] = f"%{city}%"
            
            query += " ORDER BY pr.overall_rating DESC LIMIT :limit"
            params["limit"] = limit
            
            result = await session.execute(text(query), params)
            
            providers = []
            for row in result:
                provider = {
                    "provider_id": row.provider_id,
                    "provider_name": row.provider_name,
                    "provider_city": row.provider_city,
                    "provider_state": row.provider_state,
                    "provider_zip_code": row.provider_zip_code,
                    "overall_rating": float(row.overall_rating),
                    "quality_rating": float(row.quality_rating) if row.quality_rating else None,
                    "safety_rating": float(row.safety_rating) if row.safety_rating else None,
                    "patient_experience_rating": float(row.patient_experience_rating) if row.patient_experience_rating else None
                }
                providers.append(provider)
            
            logger.info(f"Found {len(providers)} highest rated providers")
            return providers
            
        except Exception as e:
            logger.error(f"Highest rated provider search failed: {e}")
            return []
    
    async def analyze_procedure_costs(
        self,
        session: AsyncSession,
        drg_code: str,
        state: Optional[str] = None
    ) -> Optional[CostAnalysis]:
        """
        Analyze cost distribution for a procedure
        
        Args:
            session: Database session
            drg_code: DRG code to analyze
            state: Optional state filter
            
        Returns:
            Cost analysis results
        """
        try:
            base_query = """
                SELECT 
                    p.provider_name,
                    p.provider_city,
                    p.provider_state,
                    pp.average_covered_charges
                FROM providers p
                JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                WHERE pp.drg_code = :drg_code
            """
            
            params = {"drg_code": drg_code}
            
            if state:
                base_query += " AND p.provider_state = :state"
                params["state"] = state
            
            result = await session.execute(text(base_query), params)
            costs = [(row.average_covered_charges, row.provider_name, row.provider_city, row.provider_state) 
                    for row in result]
            
            if not costs:
                return None
            
            # Calculate statistics
            cost_values = [cost[0] for cost in costs]
            avg_cost = sum(cost_values) / len(cost_values)
            
            # Sort for median
            sorted_costs = sorted(costs, key=lambda x: x[0])
            median_idx = len(sorted_costs) // 2
            median_cost = sorted_costs[median_idx][0]
            
            # Variance calculation
            variance = sum((cost - avg_cost) ** 2 for cost in cost_values) / len(cost_values)
            
            # Cheapest and most expensive
            cheapest = sorted_costs[0]
            most_expensive = sorted_costs[-1]
            
            analysis = CostAnalysis(
                cheapest_provider={
                    "cost": float(cheapest[0]),
                    "provider_name": cheapest[1],
                    "provider_city": cheapest[2],
                    "provider_state": cheapest[3]
                },
                most_expensive_provider={
                    "cost": float(most_expensive[0]),
                    "provider_name": most_expensive[1],
                    "provider_city": most_expensive[2],
                    "provider_state": most_expensive[3]
                },
                average_cost=avg_cost,
                median_cost=median_cost,
                cost_variance=variance,
                total_providers=len(costs)
            )
            
            logger.info(f"Cost analysis completed for DRG {drg_code}: {analysis.total_providers} providers")
            return analysis
            
        except Exception as e:
            logger.error(f"Cost analysis failed: {e}")
            return None
    
    async def get_provider_details(
        self,
        session: AsyncSession,
        provider_id: str
    ) -> Optional[Dict]:
        """
        Get detailed information for a specific provider
        
        Args:
            session: Database session
            provider_id: Provider ID to look up
            
        Returns:
            Detailed provider information
        """
        try:
            query = """
                SELECT 
                    p.*,
                    pr.overall_rating,
                    pr.quality_rating,
                    pr.safety_rating,
                    pr.patient_experience_rating,
                    COUNT(pp.drg_code) as total_procedures,
                    AVG(pp.average_covered_charges) as avg_procedure_cost,
                    SUM(pp.total_discharges) as total_volume
                FROM providers p
                LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                LEFT JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                WHERE p.provider_id = :provider_id
                GROUP BY p.provider_id, pr.overall_rating, pr.quality_rating, 
                         pr.safety_rating, pr.patient_experience_rating
            """
            
            result = await session.execute(text(query), {"provider_id": provider_id})
            row = result.first()
            
            if not row:
                return None
            
            provider_details = {
                "provider_id": row.provider_id,
                "provider_name": row.provider_name,
                "provider_city": row.provider_city,
                "provider_state": row.provider_state,
                "provider_zip_code": row.provider_zip_code,
                "provider_address": row.provider_address,
                "provider_ruca": row.provider_ruca,
                "provider_ruca_description": row.provider_ruca_description,
                "overall_rating": float(row.overall_rating) if row.overall_rating else None,
                "quality_rating": float(row.quality_rating) if row.quality_rating else None,
                "safety_rating": float(row.safety_rating) if row.safety_rating else None,
                "patient_experience_rating": float(row.patient_experience_rating) if row.patient_experience_rating else None,
                "total_procedures": int(row.total_procedures) if row.total_procedures else 0,
                "avg_procedure_cost": float(row.avg_procedure_cost) if row.avg_procedure_cost else None,
                "total_volume": int(row.total_volume) if row.total_volume else 0
            }
            
            logger.info(f"Retrieved details for provider {provider_id}")
            return provider_details
            
        except Exception as e:
            logger.error(f"Provider detail lookup failed: {e}")
            return None
    
    async def get_procedure_volume_leaders(
        self,
        session: AsyncSession,
        drg_code: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find providers with highest volume for a procedure
        
        Args:
            session: Database session
            drg_code: DRG code to analyze
            limit: Number of results to return
            
        Returns:
            List of high-volume providers
        """
        try:
            query = """
                SELECT 
                    p.provider_id,
                    p.provider_name,
                    p.provider_city,
                    p.provider_state,
                    pp.total_discharges,
                    pp.average_covered_charges,
                    pr.overall_rating,
                    d.drg_description
                FROM providers p
                JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                JOIN drg_procedures d ON pp.drg_code = d.drg_code
                LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                WHERE pp.drg_code = :drg_code
                ORDER BY pp.total_discharges DESC
                LIMIT :limit
            """
            
            result = await session.execute(text(query), {"drg_code": drg_code, "limit": limit})
            
            providers = []
            for row in result:
                provider = {
                    "provider_id": row.provider_id,
                    "provider_name": row.provider_name,
                    "provider_city": row.provider_city,
                    "provider_state": row.provider_state,
                    "total_discharges": int(row.total_discharges),
                    "average_covered_charges": float(row.average_covered_charges),
                    "overall_rating": float(row.overall_rating) if row.overall_rating else None,
                    "drg_description": row.drg_description
                }
                providers.append(provider)
            
            logger.info(f"Found {len(providers)} volume leaders for DRG {drg_code}")
            return providers
            
        except Exception as e:
            logger.error(f"Volume leader search failed: {e}")
            return []
    
    def validate_drg_code(self, drg_code: str) -> bool:
        """Validate DRG code format"""
        try:
            # Basic validation - should be numeric
            int(drg_code)
            return True
        except ValueError:
            return False
    
    def validate_state_code(self, state_code: str) -> bool:
        """Validate US state code"""
        valid_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
            'DC'  # District of Columbia
        }
        return state_code.upper() in valid_states
