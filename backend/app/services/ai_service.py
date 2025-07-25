"""
Enhanced AI Service with Structured Query Parsing
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
from .structured_query_parser import StructuredQueryParser, StructuredQuery, QueryType
from .drg_lookup import drg_code_from_phrase

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
    structured_params: Optional[StructuredQuery] = None

class EnhancedAIService:
    """
    Enhanced AI service with structured parsing, RAG, template matching, and safety validation
    """
    
    def __init__(self):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        self.openai_client = openai.AsyncClient(api_key=openai_api_key)
        self.template_service = TemplateService(self.openai_client)
        self.normalizer = SQLNormalizer()
        self.structured_parser = StructuredQueryParser(self.openai_client)
        
        # Healthcare-specific context
        self.healthcare_context = """
        You are working with a healthcare cost database containing:
        
        Tables and Columns:
        - providers: provider_id, provider_name, provider_city, provider_state, provider_zip_code, provider_address, provider_ruca, provider_ruca_description
        - drg_procedures: drg_code, drg_description  
        - provider_procedures: provider_id, drg_code, total_discharges, average_covered_charges, average_total_payments, average_medicare_payments, provider_state
        - provider_ratings: provider_id, overall_rating, quality_rating, safety_rating, patient_experience_rating
        
        PERFORMANCE OPTIMIZATION: Use provider_procedures.provider_state instead of joining to providers table for state filtering.
        
        Key relationships:
        - providers.provider_id → provider_procedures.provider_id
        - drg_procedures.drg_code → provider_procedures.drg_code
        - providers.provider_id → provider_ratings.provider_id
        
        IMPORTANT: Use exact column names and OPTIMIZED queries:
        - State filtering: 'pp.provider_state = ?' NOT 'p.provider_state = ?'
        - Avoid unnecessary JOINs to providers table when only state is needed
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
        Process natural language query with structured parsing and template matching
        
        Args:
            session: Database session
            user_query: User's natural language query
            use_template_matching: Whether to use template matching
            
        Returns:
            QueryResult with success status and results
        """
        try:
            logger.info(f"Processing NL query: {user_query}")
            
            # Step 1: Parse query into structured parameters
            structured_params = await self.structured_parser.parse_query(user_query)
            logger.info(f"Structured parsing result: {structured_params}")
            
            # Step 2: Try template matching with structured parameters
            if use_template_matching:
                template_result = await self._try_structured_template_matching(
                    session, user_query, structured_params
                )
                if template_result.success:
                    template_result.structured_params = structured_params
                    return template_result
            
            # Step 3: Fall back to structured RAG generation
            rag_result = await self._generate_with_structured_rag(
                session, user_query, structured_params
            )
            rag_result.structured_params = structured_params
            return rag_result
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return QueryResult(
                success=False,
                message=f"Query processing failed: {str(e)}"
            )
    
    async def _try_structured_template_matching(
        self,
        session: AsyncSession,
        user_query: str,
        structured_params: StructuredQuery
    ) -> QueryResult:
        """Try to match user query with templates using structured parameters"""
        try:
            # Generate SQL from structured parameters for template search
            search_sql = await self._generate_structured_sql(structured_params)
            if not search_sql:
                return QueryResult(success=False, message="Failed to generate search SQL")
            
            # Search for matching templates
            template_match, normalized_sql, constants = await self.template_service.normalize_and_search(
                session=session,
                sql_query=search_sql,
                confidence_threshold=0.7
            )
            
            if template_match:
                # Use structured parameters to create proper constants for template
                template_constants = await self._extract_template_constants(
                    session, structured_params, template_match.raw_sql)
                if not template_constants:
                    # We couldn't supply the required parameters – fall back to RAG
                    return QueryResult(success=False, message="Template not applicable")
                
                # Execute the matched template
                success, message, results = await self.template_service.validate_and_execute_template(
                    session=session,
                    template_match=template_match,
                    user_constants=template_constants
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
            logger.error(f"Structured template matching failed: {e}")
            return QueryResult(success=False, message="Template matching failed")
    
    async def _extract_template_constants(
        self,
        session: AsyncSession,
        structured_params: StructuredQuery,
        template_sql: str
    ) -> list[str]:
        """
        Return the constants to feed into template_loader.map_parameters
        in the **exact order** they appear in the template.
        """
        constants: list[str] = []

        tmpl = template_sql.lower()

        # --- 1. procedure or DRG --------------------------------------
        if "d.drg_code =" in tmpl:
            # template wants a numeric code
            code = (structured_params.drg_code or
                    await drg_code_from_phrase(session, structured_params.procedure or ""))
            if not code:
                # we can't satisfy this template – let the caller know
                return []
            constants.append(code)

        elif "d.drg_description" in tmpl:
            # For description matching, use semantic lookup to find the best DRG
            procedure_term = structured_params.procedure or ""
            
            # Try to find the best matching DRG via semantic search
            drg_code = await drg_code_from_phrase(session, procedure_term)
            if drg_code:
                # Get the actual DRG description for exact matching
                try:
                    from sqlalchemy import text
                    result = await session.execute(
                        text("SELECT drg_description FROM drg_procedures WHERE drg_code = :code"),
                        {"code": drg_code}
                    )
                    row = result.fetchone()
                    if row:
                        # Use the actual medical DRG description for better matching
                        constants.append(f"%{row.drg_description}%")
                    else:
                        constants.append(f"%{procedure_term}%")
                except Exception as e:
                    logger.warning(f"Failed to get DRG description for {drg_code}: {e}")
                    constants.append(f"%{procedure_term}%")
            else:
                # No semantic match found, use original term
                constants.append(f"%{procedure_term}%")

        # --- 2. geography ---------------------------------------------
        if "provider_state" in tmpl:
            constants.append(structured_params.state or "")
        if "provider_city"  in tmpl and "provider_city ilike" in tmpl:
            constants.append(f"%{structured_params.city or ''}%")

        # --- 3. LIMIT --------------------------------------------------
        if "$3" in tmpl or "limit $" in tmpl:
            constants.append(str(structured_params.limit or 10))

        logger.info("Extracted template constants: %s", constants)
        return constants
    
    async def _generate_structured_sql(self, structured_params: StructuredQuery) -> Optional[str]:
        """Generate SQL query from structured parameters for template matching"""
        try:
            # Build SQL based on query type and parameters
            if structured_params.query_type == QueryType.CHEAPEST_PROVIDER:
                # OPTIMIZED: Use denormalized provider_state to avoid expensive JOIN to providers table
                sql_parts = ["SELECT d.drg_description, pp.average_covered_charges, pp.provider_id"]
                sql_parts.append("FROM drg_procedures d")
                sql_parts.append("JOIN provider_procedures pp ON d.drg_code = pp.drg_code")
                
                where_conditions = []
                if structured_params.procedure:
                    where_conditions.append("d.drg_description ILIKE '%{}%'".format(structured_params.procedure))
                if structured_params.state:
                    where_conditions.append("pp.provider_state = '{}'".format(structured_params.state))
                    
                if where_conditions:
                    sql_parts.append("WHERE " + " AND ".join(where_conditions))
                    
                sql_parts.append("ORDER BY pp.average_covered_charges")
                sql_parts.append("LIMIT {}".format(structured_params.limit or 10))
                
            elif structured_params.query_type == QueryType.COST_COMPARISON:
                # OPTIMIZED: Use denormalized provider_state for cost comparisons
                sql_parts = ["SELECT d.drg_code, d.drg_description, AVG(pp.average_covered_charges) as avg_cost"]
                sql_parts.append("FROM drg_procedures d")
                sql_parts.append("JOIN provider_procedures pp ON d.drg_code = pp.drg_code")
                
                where_conditions = []
                if structured_params.procedure:
                    where_conditions.append("d.drg_description ILIKE '%{}%'".format(structured_params.procedure))
                if structured_params.state:
                    where_conditions.append("pp.provider_state = '{}'".format(structured_params.state))
                    
                if where_conditions:
                    sql_parts.append("WHERE " + " AND ".join(where_conditions))
                    
                sql_parts.append("GROUP BY d.drg_code, d.drg_description")
                sql_parts.append("ORDER BY avg_cost DESC")
                sql_parts.append("LIMIT {}".format(structured_params.limit or 10))
                
            elif structured_params.query_type == QueryType.HIGHEST_RATED:
                # Note: For ratings, we still need to join providers table
                sql_parts = ["SELECT p.provider_name, pr.overall_rating, p.provider_city, p.provider_state"]
                sql_parts.append("FROM providers p")
                sql_parts.append("JOIN provider_ratings pr ON p.provider_id = pr.provider_id")
                
                if structured_params.procedure:
                    sql_parts.append("JOIN provider_procedures pp ON p.provider_id = pp.provider_id")
                    sql_parts.append("JOIN drg_procedures d ON pp.drg_code = d.drg_code")
                
                where_conditions = []
                if structured_params.procedure:
                    where_conditions.append("d.drg_description ILIKE '%{}%'".format(structured_params.procedure))
                if structured_params.state:
                    where_conditions.append("p.provider_state = '{}'".format(structured_params.state))
                if structured_params.min_rating:
                    where_conditions.append("pr.overall_rating >= {}".format(structured_params.min_rating))
                    
                if where_conditions:
                    sql_parts.append("WHERE " + " AND ".join(where_conditions))
                    
                sql_parts.append("ORDER BY pr.overall_rating DESC")
                sql_parts.append("LIMIT {}".format(structured_params.limit or 10))
                
            else:
                # Default to cost comparison query (most common)
                return await self._generate_structured_sql(
                    StructuredQuery(query_type=QueryType.COST_COMPARISON, **structured_params.__dict__)
                )
            
            return " ".join(sql_parts)
            
        except Exception as e:
            logger.error(f"Structured SQL generation failed: {e}")
            return None
    
    async def _lookup_drg_code(self, session: AsyncSession, procedure_description: str) -> Optional[str]:
        """Look up DRG code from procedure description using database trigram search"""
        try:
            from sqlalchemy import text
            
            query = text("""
                SELECT drg_code, drg_description,
                       similarity(drg_description, :phrase) as sim_score
                FROM drg_procedures
                WHERE drg_description ILIKE '%' || :phrase || '%'
                ORDER BY similarity(drg_description, :phrase) DESC
                LIMIT 1
            """)
            
            result = await session.execute(query, {"phrase": procedure_description})
            row = result.fetchone()
            
            if row and row.sim_score > 0.3:  # Minimum similarity threshold
                logger.info(f"DRG lookup: '{procedure_description}' -> '{row.drg_code}' ({row.drg_description})")
                return row.drg_code
            
            logger.warning(f"No DRG match found for: {procedure_description}")
            return None
            
        except Exception as e:
            logger.error(f"DRG lookup failed: {e}")
            return None
    
    async def _generate_with_structured_rag(
        self,
        session: AsyncSession,
        user_query: str,
        structured_params: StructuredQuery,
        max_attempts: int = 3
    ) -> QueryResult:
        """Generate SQL using RAG with template examples, using structured parameters"""
        try:
            # Get template suggestions for context
            template_suggestions = await self.template_service.get_template_suggestions(
                session=session,
                user_query=user_query,
                limit=3
            )
            
            # Build RAG prompt with examples
            rag_prompt = self._build_rag_prompt(user_query, template_suggestions, structured_params)
            
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
            logger.error(f"Structured RAG generation failed: {e}")
            return QueryResult(success=False, message="Structured RAG generation failed")
    
    def _build_rag_prompt(self, user_query: str, template_suggestions: List[TemplateMatch], structured_params: StructuredQuery) -> str:
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
        Structured Parameters: {structured_params}
        
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
        """Execute SQL with safety measures and proper transaction handling"""
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
            # Rollback the transaction to prevent abort state
            try:
                await session.rollback()
            except Exception as rollback_error:
                logger.error(f"Transaction rollback failed: {rollback_error}")
            return False, f"Query execution failed: {str(e)}", None
    
    async def explain_query_results(
        self,
        user_query: str,
        sql_query: str,
        results: List[Dict]
    ) -> str:
        """Generate natural language explanation of query results using GPT-4o-mini for speed"""
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
            Be concise and helpful.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Result explanation failed: {e}")
            return "Query executed successfully but explanation generation failed."
