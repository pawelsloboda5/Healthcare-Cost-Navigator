"""
Enhanced AI Service
RAG-enhanced SQL generation with template matching and safety validation
"""
import openai
import os
from typing import List, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from dataclasses import dataclass

from ..utils.template_loader import TemplateService, ParameterMapping
from ..utils.sql_normalizer import SQLNormalizer
from ..utils.vector_search import TemplateMatch

logger = logging.getLogger(__name__)

@dataclass
class QueryResult:
    """Result of AI query processing"""
    success: bool
    message: str
    sql_query: Optional[str] = None
    results: Optional[List[Dict]] = None
    template_used: Optional[int] = None
    confidence_score: Optional[float] = None

class EnhancedAIService:
    """
    Enhanced AI service with RAG, template matching, and safety validation
    """
    
    def __init__(self):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        self.openai_client = openai.AsyncClient(api_key=openai_api_key)
        self.template_service = TemplateService(self.openai_client)
        self.normalizer = SQLNormalizer()
        
        # Healthcare-specific context
        self.healthcare_context = """
        You are working with a healthcare cost database containing:
        
        Tables and Columns:
        - providers: provider_id, provider_name, provider_city, provider_state, provider_zip_code, provider_address, provider_ruca, provider_ruca_description
        - drg_procedures: drg_code, drg_description  
        - provider_procedures: provider_id, drg_code, total_discharges, average_covered_charges, average_total_payments, average_medicare_payments
        - provider_ratings: provider_id, overall_rating, quality_rating, safety_rating, patient_experience_rating
        
        Key relationships:
        - providers.provider_id → provider_procedures.provider_id
        - drg_procedures.drg_code → provider_procedures.drg_code
        - providers.provider_id → provider_ratings.provider_id
        
        IMPORTANT: Use exact column names:
        - State column is 'provider_state' NOT 'state'  
        - DRG description is 'drg_description' NOT 'description'
        - Provider name is 'provider_name'
        - Costs are 'average_covered_charges', 'average_total_payments', 'average_medicare_payments'
        
        Common queries involve:
        - Finding cheapest/most expensive providers for procedures
        - Comparing costs across geographic regions
        - Finding highest rated providers
        - Volume analysis (total_discharges)
        """
    
    async def process_natural_language_query(
        self,
        session: AsyncSession,
        user_query: str,
        use_template_matching: bool = True
    ) -> QueryResult:
        """
        Process natural language query with RAG and template matching
        
        Args:
            session: Database session
            user_query: User's natural language query
            use_template_matching: Whether to use template matching
            
        Returns:
            QueryResult with success status and results
        """
        try:
            logger.info(f"Processing NL query: {user_query}")
            
            # First, try template matching if enabled
            if use_template_matching:
                template_result = await self._try_template_matching(session, user_query)
                if template_result.success:
                    return template_result
            
            # Fall back to RAG-enhanced generation
            rag_result = await self._generate_with_rag(session, user_query)
            return rag_result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return QueryResult(
                success=False,
                message=f"Query processing failed: {str(e)}"
            )
    
    async def _try_template_matching(
        self,
        session: AsyncSession,
        user_query: str
    ) -> QueryResult:
        """Try to match user query with existing templates"""
        try:
            # Generate initial SQL to normalize and search
            initial_sql = await self._generate_sql_from_nl(user_query)
            if not initial_sql:
                return QueryResult(success=False, message="Failed to generate initial SQL")
            
            # Search for matching templates
            template_match, normalized_sql, constants = await self.template_service.normalize_and_search(
                session=session,
                sql_query=initial_sql,
                confidence_threshold=0.75
            )
            
            if template_match:
                # Execute the matched template
                success, message, results = await self.template_service.validate_and_execute_template(
                    session=session,
                    template_match=template_match,
                    user_constants=constants
                )
                
                return QueryResult(
                    success=success,
                    message=f"Template match found. {message}",
                    sql_query=template_match.raw_sql,
                    results=results,
                    template_used=template_match.template_id,
                    confidence_score=template_match.similarity_score
                )
            
            return QueryResult(success=False, message="No confident template match found")
            
        except Exception as e:
            logger.error(f"Template matching failed: {e}")
            return QueryResult(success=False, message="Template matching failed")
    
    async def _generate_with_rag(
        self,
        session: AsyncSession,
        user_query: str,
        max_attempts: int = 3
    ) -> QueryResult:
        """Generate SQL using RAG with template examples"""
        try:
            # Get template suggestions for context
            template_suggestions = await self.template_service.get_template_suggestions(
                session=session,
                user_query=user_query,
                limit=3
            )
            
            # Build RAG prompt with examples
            rag_prompt = self._build_rag_prompt(user_query, template_suggestions)
            
            # Generate SQL with multiple attempts
            for attempt in range(max_attempts):
                try:
                    generated_sql = await self._generate_sql_with_prompt(rag_prompt)
                    
                    if not generated_sql:
                        continue
                    
                    # Validate safety
                    if not self.normalizer.validate_sql_safety(generated_sql):
                        logger.warning(f"Generated SQL failed safety check (attempt {attempt + 1}): {generated_sql}")
                        continue
                    
                    # Execute the query
                    success, message, results = await self._execute_sql_safely(
                        session, generated_sql
                    )
                    
                    if success:
                        # Learn from successful query
                        await self.template_service.learn_from_successful_query(
                            session=session,
                            original_query=user_query,
                            generated_sql=generated_sql,
                            was_successful=True
                        )
                        
                        return QueryResult(
                            success=True,
                            message=f"Query generated and executed successfully. {message}",
                            sql_query=generated_sql,
                            results=results
                        )
                    else:
                        logger.warning(f"Generated SQL execution failed (attempt {attempt + 1}): {message}")
                        
                except Exception as e:
                    logger.warning(f"SQL generation attempt {attempt + 1} failed: {e}")
                    continue
            
            return QueryResult(
                success=False,
                message=f"Failed to generate valid SQL after {max_attempts} attempts"
            )
            
        except Exception as e:
            logger.error(f"RAG generation failed: {e}")
            return QueryResult(success=False, message="RAG generation failed")
    
    def _build_rag_prompt(self, user_query: str, template_suggestions: List[TemplateMatch]) -> str:
        """Build RAG prompt with template examples"""
        prompt = f"""
        {self.healthcare_context}
        
        Similar query examples:
        """
        
        for i, template in enumerate(template_suggestions, 1):
            prompt += f"""
        Example {i}:
        SQL: {template.raw_sql}
        Description: {template.comment}
        
        """
        
        prompt += f"""
        User Query: {user_query}
        
        Generate a PostgreSQL SELECT query that answers the user's question.
        Requirements:
        - Use only SELECT statements
        - Use proper JOIN syntax when needed
        - Include appropriate WHERE clauses
        - Add ORDER BY and LIMIT as needed
        - Use exact table and column names from the schema
        - Return only the SQL query, no explanations
        
        SQL Query:"""
        
        return prompt
    
    async def _generate_sql_from_nl(self, user_query: str) -> Optional[str]:
        """Generate SQL from natural language (basic version)"""
        try:
            prompt = f"""
            {self.healthcare_context}
            
            User Query: {user_query}
            
            Generate a PostgreSQL SELECT query. Return only the SQL, no explanations.
            
            SQL Query:"""
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            sql = response.choices[0].message.content.strip()
            return self._clean_generated_sql(sql)
            
        except Exception as e:
            logger.error(f"Basic SQL generation failed: {e}")
            return None
    
    async def _generate_sql_with_prompt(self, prompt: str) -> Optional[str]:
        """Generate SQL using the provided prompt"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1
            )
            
            sql = response.choices[0].message.content.strip()
            return self._clean_generated_sql(sql)
            
        except Exception as e:
            logger.error(f"SQL generation with prompt failed: {e}")
            return None
    
    def _clean_generated_sql(self, sql: str) -> str:
        """Clean and validate generated SQL"""
        # Remove markdown formatting
        sql = sql.replace("```sql", "").replace("```", "")
        
        # Remove extra whitespace
        sql = sql.strip()
        
        # Ensure single statement
        if ';' in sql:
            sql = sql.split(';')[0].strip()
        
        return sql
    
    async def _execute_sql_safely(
        self,
        session: AsyncSession,
        sql: str,
        max_results: int = 100
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """Execute SQL with safety measures"""
        try:
            # Add LIMIT if not present
            if 'limit' not in sql.lower():
                sql += f" LIMIT {max_results}"
            
            from sqlalchemy import text
            result = await session.execute(text(sql))
            rows = result.fetchall()
            
            if rows:
                columns = result.keys()
                results = [dict(zip(columns, row)) for row in rows]
            else:
                results = []
            
            return True, f"Query executed successfully, returned {len(results)} results", results
            
        except Exception as e:
            logger.error(f"SQL execution failed: {e}")
            return False, f"Query execution failed: {str(e)}", None
    
    async def explain_query_results(
        self,
        user_query: str,
        sql_query: str,
        results: List[Dict]
    ) -> str:
        """Generate natural language explanation of query results"""
        try:
            results_summary = f"Found {len(results)} results"
            if results:
                # Sample first few results for context
                sample_results = results[:3]
                results_summary += f". Sample data: {sample_results}"
            
            prompt = f"""
            User asked: {user_query}
            SQL executed: {sql_query}
            Results: {results_summary}
            
            Provide a brief, natural language explanation of what these results show.
            Focus on answering the user's original question.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Result explanation failed: {e}")
            return "Query executed successfully but explanation generation failed."
