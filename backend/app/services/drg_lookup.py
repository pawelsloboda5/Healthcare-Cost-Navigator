"""
DRG Code Lookup Service
Translates free-text procedure phrases to DRG codes using vector-based semantic search
"""
import openai
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

class DRGLookupService:
    """Vector-based semantic search for DRG procedures"""
    
    def __init__(self):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.openai_client = openai.AsyncClient(api_key=openai_api_key)
        self.embedding_model = "text-embedding-3-small"
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI"""
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to get embedding for text: {text}, error: {e}")
            raise
    
    async def find_matching_drg_code(
        self, 
        session: AsyncSession, 
        phrase: str, 
        similarity_threshold: float = 0.5  # Lowered from 0.7 to 0.5 for better medical term matching
    ) -> Optional[str]:
        """
        Find DRG code using vector-based semantic search
        
        Args:
            session: Database session
            phrase: User's procedure description (e.g., "heart surgery")
            similarity_threshold: Minimum similarity score
            
        Returns:
            Best matching DRG code or None
        """
        if not phrase or not phrase.strip():
            return None
            
        try:
            # Get embedding for the user's phrase
            query_embedding = await self.get_embedding(phrase.strip())
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Vector similarity search on DRG descriptions
            query = text("""
                SELECT 
                    drg_code,
                    drg_description,
                    1 - (embedding <=> (:query_embedding)::vector) as similarity_score
                FROM drg_procedures
                WHERE embedding IS NOT NULL
                    AND 1 - (embedding <=> (:query_embedding)::vector) >= :threshold
                ORDER BY embedding <=> (:query_embedding)::vector
                LIMIT 1
            """)
            
            result = await session.execute(
                query,
                {
                    "query_embedding": embedding_str,
                    "threshold": similarity_threshold
                }
            )
            
            row = result.fetchone()
            if row:
                logger.info(f"DRG semantic lookup: '{phrase}' -> DRG {row.drg_code} "
                           f"({row.drg_description}) [similarity: {row.similarity_score:.3f}]")
                return row.drg_code
            else:
                logger.warning(f"DRG semantic lookup: no match found for '{phrase}' "
                             f"above threshold {similarity_threshold}")
                return None
                
        except Exception as e:
            logger.error(f"DRG semantic lookup failed for '{phrase}': {e}")
            # Fallback to trigram search if vector search fails
            return await self._fallback_trigram_search(session, phrase)
    
    async def _fallback_trigram_search(
        self, 
        session: AsyncSession, 
        phrase: str
    ) -> Optional[str]:
        """Fallback to trigram similarity search if vector search fails"""
        try:
            fallback_query = text("""
                SELECT drg_code
                FROM drg_procedures
                WHERE drg_description ILIKE '%' || :phrase || '%'
                ORDER BY similarity(drg_description, :phrase) DESC
                LIMIT 1
            """)
            
            result = await session.execute(fallback_query, {"phrase": phrase})
            row = result.fetchone()
            
            if row:
                logger.info(f"DRG fallback lookup: '{phrase}' -> DRG {row.drg_code}")
                return row.drg_code
            else:
                logger.warning(f"DRG fallback lookup: no match found for '{phrase}'")
                return None
                
        except Exception as e:
            logger.error(f"DRG fallback lookup failed for '{phrase}': {e}")
            return None
    
    async def find_similar_procedures(
        self,
        session: AsyncSession,
        phrase: str,
        limit: int = 20,  # Increased from 5 to 10 for more options
        similarity_threshold: float = 0.4  # Lowered from 0.6 to 0.4 for broader medical term matching
    ) -> List[Tuple[str, str, float]]:
        """
        Find multiple similar procedures for suggestion/debugging
        
        Returns:
            List of (drg_code, drg_description, similarity_score) tuples
        """
        if not phrase or not phrase.strip():
            return []
            
        try:
            query_embedding = await self.get_embedding(phrase.strip())
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            query = text("""
                SELECT 
                    drg_code,
                    drg_description,
                    1 - (embedding <=> (:query_embedding)::vector) as similarity_score
                FROM drg_procedures
                WHERE embedding IS NOT NULL
                    AND 1 - (embedding <=> (:query_embedding)::vector) >= :threshold
                ORDER BY embedding <=> (:query_embedding)::vector
                LIMIT :limit
            """)
            
            result = await session.execute(
                query,
                {
                    "query_embedding": embedding_str,
                    "threshold": similarity_threshold,
                    "limit": limit
                }
            )
            
            similar_procedures = []
            for row in result:
                similar_procedures.append((row.drg_code, row.drg_description, row.similarity_score))
            
            logger.info(f"Found {len(similar_procedures)} similar procedures for '{phrase}'")
            return similar_procedures
            
        except Exception as e:
            logger.error(f"Failed to find similar procedures for '{phrase}': {e}")
            return []

# Global instance for backward compatibility
_drg_lookup_service = None

async def drg_code_from_phrase(session: AsyncSession, phrase: str) -> Optional[str]:
    """
    Backward compatible function for DRG lookup using vector search
    """
    global _drg_lookup_service
    if _drg_lookup_service is None:
        _drg_lookup_service = DRGLookupService()
    
    return await _drg_lookup_service.find_matching_drg_code(session, phrase) 