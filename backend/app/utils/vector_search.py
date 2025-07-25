"""
Vector Search Utility
Handles template similarity search using pgvector and OpenAI embeddings
"""
import asyncio
import openai
import numpy as np
from typing import List, Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TemplateMatch:
    """Represents a matched template with similarity score"""
    template_id: int
    canonical_sql: str
    raw_sql: str
    comment: str
    similarity_score: float
    edit_distance: Optional[int] = None

class VectorSearchEngine:
    """Handles vector-based template similarity search"""
    
    def __init__(self, openai_client: openai.AsyncClient):
        self.openai_client = openai_client
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536
        
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text using OpenAI
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        try:
            response = await self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Failed to get embedding for text: {text[:100]}..., error: {e}")
            raise
    
    async def search_similar_templates(
        self, 
        session: AsyncSession,
        query_sql: str,
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[TemplateMatch]:
        """
        Search for similar templates using vector similarity
        
        Args:
            session: Database session
            query_sql: Normalized SQL query to search for
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of TemplateMatch objects sorted by similarity
        """
        try:
            # Get embedding for the query
            query_embedding = await self.get_embedding(query_sql)
            
            # Convert to PostgreSQL array format
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Perform vector similarity search
            query = text("""
                SELECT 
                    template_id,
                    canonical_sql,
                    raw_sql,
                    comment,
                    1 - (embedding <=> (:query_embedding)::vector) as similarity_score
                FROM template_catalog
                WHERE 1 - (embedding <=> (:query_embedding)::vector) >= :threshold
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
            
            matches = []
            for row in result:
                match = TemplateMatch(
                    template_id=row.template_id,
                    canonical_sql=row.canonical_sql,
                    raw_sql=row.raw_sql,
                    comment=row.comment or "",
                    similarity_score=float(row.similarity_score)
                )
                matches.append(match)
                
            logger.info(f"Found {len(matches)} similar templates for query: {query_sql[:100]}...")
            return matches
            
        except Exception as e:
            logger.error(f"Vector search failed for query: {query_sql}, error: {e}")
            await session.rollback()
            return []
    
    async def find_best_template_match(
        self,
        session: AsyncSession,
        normalized_sql: str,
        original_sql: str,
        confidence_threshold: float = 0.7
    ) -> Optional[TemplateMatch]:
        """
        Find the best matching template with confidence scoring
        
        Args:
            session: Database session
            normalized_sql: Normalized SQL for vector search
            original_sql: Original SQL for additional validation
            confidence_threshold: Minimum confidence to return a match
            
        Returns:
            Best matching template or None if no confident match
        """
        try:
            # Search for similar templates
            matches = await self.search_similar_templates(
                session, 
                normalized_sql, 
                limit=3,
                similarity_threshold=0.6
            )
            
            if not matches:
                logger.info("No similar templates found")
                return None
                
            best_match = matches[0]
            
            # Calculate edit distance for additional validation
            from Levenshtein import distance
            best_match.edit_distance = distance(
                normalized_sql.lower(), 
                best_match.canonical_sql.lower()
            )
            
            # Combine similarity score with edit distance for confidence
            max_length = max(len(normalized_sql), len(best_match.canonical_sql))
            edit_distance_ratio = 1 - (best_match.edit_distance / max_length) if max_length > 0 else 0
            
            # Weighted confidence score
            confidence = (best_match.similarity_score * 0.7) + (edit_distance_ratio * 0.3)
            
            logger.info(f"Best template match - ID: {best_match.template_id}, "
                       f"Similarity: {best_match.similarity_score:.3f}, "
                       f"Edit Distance: {best_match.edit_distance}, "
                       f"Confidence: {confidence:.3f}")
            
            if confidence >= confidence_threshold:
                return best_match
            else:
                logger.info(f"No confident template match found (confidence: {confidence:.3f} < {confidence_threshold})")
                return None
                
        except Exception as e:
            logger.error(f"Template matching failed for SQL: {normalized_sql}, error: {e}")
            await session.rollback()
            return None
    
    async def add_template_to_catalog(
        self,
        session: AsyncSession,
        canonical_sql: str,
        raw_sql: str,
        comment: str = ""
    ) -> int:
        """
        Add a new template to the catalog with embedding
        
        Args:
            session: Database session
            canonical_sql: Normalized SQL template
            raw_sql: Original SQL with placeholders
            comment: Description of the template
            
        Returns:
            Template ID of the newly created template
        """
        try:
            # Get embedding for the canonical SQL
            embedding = await self.get_embedding(canonical_sql)
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            # Insert into catalog
            query = text("""
                INSERT INTO template_catalog (canonical_sql, raw_sql, comment, embedding)
                VALUES (:canonical_sql, :raw_sql, :comment, (:embedding)::vector)
                RETURNING template_id
            """)
            
            result = await session.execute(
                query,
                {
                    "canonical_sql": canonical_sql,
                    "raw_sql": raw_sql,
                    "comment": comment,
                    "embedding": embedding_str
                }
            )
            
            template_id = result.scalar()
            await session.commit()
            
            logger.info(f"Added new template to catalog - ID: {template_id}")
            return template_id
            
        except Exception as e:
            logger.error(f"Failed to add template to catalog: {e}")
            await session.rollback()
            raise
    
    async def get_template_statistics(self, session: AsyncSession) -> Dict:
        """
        Get statistics about the template catalog
        
        Returns:
            Dictionary with catalog statistics
        """
        try:
            query = text("""
                SELECT 
                    COUNT(*) as total_templates,
                    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as templates_with_embeddings,
                    AVG(LENGTH(canonical_sql)) as avg_sql_length
                FROM template_catalog
            """)
            
            result = await session.execute(query)
            row = result.first()
            
            return {
                "total_templates": row.total_templates,
                "templates_with_embeddings": row.templates_with_embeddings,
                "avg_sql_length": float(row.avg_sql_length) if row.avg_sql_length else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get template statistics: {e}")
            return {}
    
    def calculate_semantic_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norms = np.linalg.norm(vec1) * np.linalg.norm(vec2)
            
            if norms == 0:
                return 0.0
                
            similarity = dot_product / norms
            
            # Convert to 0-1 range (cosine similarity is -1 to 1)
            return (similarity + 1) / 2
            
        except Exception as e:
            logger.error(f"Failed to calculate semantic similarity: {e}")
            return 0.0
