"""
Template Service
Handles SQL template operations: normalization, embedding, and matching
"""
import openai
from typing import List, Dict, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from dataclasses import dataclass

from .sql_normalizer import SQLNormalizer
from .vector_search import VectorSearchEngine, TemplateMatch

logger = logging.getLogger(__name__)

@dataclass
class ParameterMapping:
    """Maps extracted constants to parameter positions"""
    parameter_name: str  # e.g., "$1", "$2"
    original_value: str
    data_type: str  # "string", "number", "boolean"

class TemplateService:
    """
    Core service for SQL template operations
    Combines normalization, vector search, and parameter mapping
    """
    
    def __init__(self, openai_client: openai.AsyncClient):
        self.normalizer = SQLNormalizer()
        self.vector_engine = VectorSearchEngine(openai_client)
        
    async def normalize_and_search(
        self,
        session: AsyncSession,
        sql_query: str,
        confidence_threshold: float = 0.7
    ) -> Tuple[Optional[TemplateMatch], str, List[str]]:
        """
        Normalize SQL and search for matching templates
        
        Args:
            session: Database session
            sql_query: Raw SQL query to normalize and search
            confidence_threshold: Minimum confidence for template match
            
        Returns:
            Tuple of (best_match, normalized_sql, extracted_constants)
        """
        try:
            # Normalize the SQL query
            normalized_sql, constants = self.normalizer.normalize_sql(sql_query)
            
            logger.info(f"SQL normalization - Original: {sql_query}")
            logger.info(f"SQL normalization - Normalized: {normalized_sql}")  
            logger.info(f"SQL normalization - Constants extracted: {constants}")
            
            # Search for matching templates
            best_match = await self.vector_engine.find_best_template_match(
                session=session,
                normalized_sql=normalized_sql,
                original_sql=sql_query,
                confidence_threshold=confidence_threshold
            )
            
            logger.info(f"Template search - Query: {sql_query[:100]}..., "
                       f"Normalized: {normalized_sql[:100]}..., "
                       f"Match found: {best_match is not None}")
            
            return best_match, normalized_sql, constants
            
        except Exception as e:
            logger.error(f"Template normalization and search failed: {e}")
            await session.rollback()
            return None, "", []
    
    def map_parameters(
        self, 
        template_sql: str, 
        user_constants: List[str]
    ) -> Tuple[str, List[ParameterMapping]]:
        """
        Map user constants to template parameters (simplified approach)
        
        Args:
            session: Database session
            template_sql: Template SQL with $1, $2, etc. placeholders
            user_constants: Constants extracted from user query
            
        Returns:
            Tuple of (parameterized_sql, parameter_mappings)
        """
        try:
            import re
            
            mappings = []
            parameterized_sql = template_sql
            
            logger.info(f"Parameter mapping - Template SQL: {template_sql}")
            logger.info(f"Parameter mapping - User constants: {user_constants}")
            
            # Simple positional mapping - structured parser handles semantic extraction
            for i, constant in enumerate(user_constants, 1):
                param_name = f"${i}"
                
                # Determine data type and create mapping
                data_type = self._determine_data_type(constant)
                mapping = ParameterMapping(
                    parameter_name=param_name,
                    original_value=constant,
                    data_type=data_type
                )
                mappings.append(mapping)
                
                # Replace in SQL based on context
                if f"ILIKE '{param_name}'" in parameterized_sql:
                    # Handle ILIKE patterns
                    replacement = f"ILIKE '%{constant.strip('%')}%'"
                    parameterized_sql = parameterized_sql.replace(f"ILIKE '{param_name}'", replacement)
                elif f"LIKE '{param_name}'" in parameterized_sql:
                    # Handle LIKE patterns  
                    replacement = f"LIKE '%{constant.strip('%')}%'"
                    parameterized_sql = parameterized_sql.replace(f"LIKE '{param_name}'", replacement)
                else:
                    # Standard parameter replacement
                    placeholder_re = re.compile(rf"('?){re.escape(param_name)}('?)")
                    if data_type == "string":
                        replacement = f"'{constant}'"
                        parameterized_sql = placeholder_re.sub(replacement, parameterized_sql)
                    else:
                        replacement = constant
                        parameterized_sql = placeholder_re.sub(replacement, parameterized_sql)
            
            logger.debug(f"Parameter mapping - Template: {template_sql}, "
                        f"Result: {parameterized_sql}, "
                        f"Mappings: {len(mappings)}")
            
            return parameterized_sql, mappings
            
        except Exception as e:
            logger.error(f"Parameter mapping failed: {e}")
            return template_sql, []
    
    def _determine_data_type(self, value: str) -> str:
        """Determine the data type of a constant value"""
        try:
            # Check for boolean first
            if value.lower() in ('true', 'false', 't', 'f'):
                return "boolean"
            
            # Special handling for DRG codes - they're stored as strings in the database
            # DRG codes are typically 3-digit numbers like "521", "470", etc.
            if value.isdigit() and len(value) <= 4:
                # This could be a DRG code, treat as string to be safe
                # Since DRG codes in our schema are String(10), not integers
                return "string"
            
            # Try to parse as number for other cases
            if '.' in value:
                float(value)
                return "float"
            else:
                # For longer numeric strings or explicit integers, treat as integer
                int(value)
                # Only treat as integer if it's a reasonable integer (not a code)
                if len(value) > 4:  # Longer numbers are likely real integers
                    return "integer"
                else:
                    return "string"  # Short numeric strings are likely codes
        except ValueError:
            # Default to string
            return "string"
    
    async def validate_and_execute_template(
        self,
        session: AsyncSession,
        template_match: TemplateMatch,
        user_constants: List[str],
        max_results: int = 100
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        Validate template parameters and execute the query safely
        
        Args:
            session: Database session
            template_match: Matched template
            user_constants: Constants from user query
            max_results: Maximum number of results to return
            
        Returns:
            Tuple of (success, message, results)
        """
        try:
            # Map parameters
            executable_sql, mappings = self.map_parameters(
                template_match.raw_sql, 
                user_constants
            )
            
            # Validate SQL safety
            if not self.normalizer.validate_sql_safety(executable_sql):
                return False, "Query failed safety validation", None
            
            # Check complexity
            complexity = self.normalizer.complexity_score(executable_sql)
            if complexity > 50:  # Configurable threshold
                logger.warning(f"High complexity query (score: {complexity}): {executable_sql}")
            
            # Add LIMIT if not present
            if 'limit' not in executable_sql.lower():
                executable_sql += f" LIMIT {max_results}"
            
            # Execute the query
            from sqlalchemy import text
            result = await session.execute(text(executable_sql))
            rows = result.fetchall()
            
            # Convert to list of dictionaries
            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []
            
            logger.info(f"Template execution successful - Template ID: {template_match.template_id}, "
                       f"Results: {len(results)}")
            
            return True, f"Query executed successfully, returned {len(results)} results", results
            
        except Exception as e:
            logger.error(f"Template execution failed: {e}")
            await session.rollback()
            return False, f"Query execution failed: {str(e)}", None
    
    async def learn_from_successful_query(
        self,
        session: AsyncSession,
        original_query: str,
        generated_sql: str,
        was_successful: bool,
        user_feedback: Optional[str] = None
    ) -> bool:
        """
        Learn from successful queries by potentially adding them to the template catalog
        
        Args:
            session: Database session
            original_query: Original natural language query
            generated_sql: SQL that was generated and executed
            was_successful: Whether the query was successful
            user_feedback: Optional user feedback
            
        Returns:
            True if template was added to catalog
        """
        try:
            if not was_successful:
                return False
                
            # Normalize the generated SQL
            normalized_sql, constants = self.normalizer.normalize_sql(generated_sql)
            
            # Check if this template already exists
            existing_matches = await self.vector_engine.search_similar_templates(
                session=session,
                query_sql=normalized_sql,
                limit=1,
                similarity_threshold=0.95  # High threshold for duplicates
            )
            
            if existing_matches:
                logger.info(f"Similar template already exists, not adding: {normalized_sql}")
                return False
            
            # Create template comment
            comment = f"Auto-generated from query: {original_query[:100]}"
            if user_feedback:
                comment += f" | Feedback: {user_feedback[:100]}"
            
            # Add to catalog
            template_id = await self.vector_engine.add_template_to_catalog(
                session=session,
                canonical_sql=normalized_sql,
                raw_sql=generated_sql,
                comment=comment
            )
            
            logger.info(f"Added new template to catalog from successful query - ID: {template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to learn from successful query: {e}")
            await session.rollback()
            return False
    
    async def get_template_suggestions(
        self,
        session: AsyncSession,
        user_query: str,
        limit: int = 3
    ) -> List[TemplateMatch]:
        """
        Get template suggestions based on natural language query
        
        Args:
            session: Database session
            user_query: Natural language query
            limit: Maximum number of suggestions
            
        Returns:
            List of template suggestions
        """
        try:
            # Get embedding for the natural language query
            embedding = await self.vector_engine.get_embedding(user_query)
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            # Search for templates with natural language matching
            from sqlalchemy import text
            query = text("""
                SELECT 
                    template_id,
                    canonical_sql,
                    raw_sql,
                    comment,
                    1 - (embedding <=> (:query_embedding)::vector) as similarity_score
                FROM template_catalog
                WHERE comment IS NOT NULL AND comment != ''
                ORDER BY embedding <=> (:query_embedding)::vector
                LIMIT :limit
            """)
            
            result = await session.execute(
                query,
                {
                    "query_embedding": embedding_str,
                    "limit": limit
                }
            )
            
            suggestions = []
            for row in result:
                match = TemplateMatch(
                    template_id=row.template_id,
                    canonical_sql=row.canonical_sql,
                    raw_sql=row.raw_sql,
                    comment=row.comment or "",
                    similarity_score=float(row.similarity_score)
                )
                suggestions.append(match)
            
            logger.info(f"Found {len(suggestions)} template suggestions for: {user_query[:100]}")
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to get template suggestions: {e}")
            await session.rollback()
            return []
