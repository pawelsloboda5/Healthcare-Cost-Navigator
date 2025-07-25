"""
SQL Normalization Utility
Converts SQL queries to parameterized templates for vector search matching
"""
import re
import sqlglot
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SQLNormalizer:
    """Normalizes SQL queries for template matching by replacing constants with placeholders"""
    
    def __init__(self):
        # Patterns for different types of constants
        self.string_pattern = re.compile(r"'([^']*)'")
        self.number_pattern = re.compile(r'\b\d+(?:\.\d+)?\b')
        self.parameter_pattern = re.compile(r'\$\d+')
        
    def normalize_sql(self, sql: str) -> Tuple[str, List[str]]:
        """
        Normalize SQL by replacing constants with placeholders
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Tuple of (normalized_sql, extracted_constants)
        """
        try:
            # Parse SQL with sqlglot to ensure it's valid
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.postgres.Postgres)
            if not parsed:
                raise ValueError("Failed to parse SQL")
                
            # Convert back to normalized string format
            canonical_sql = parsed.sql(dialect=sqlglot.dialects.postgres.Postgres, pretty=False)
            
            # Extract constants and replace with placeholders
            normalized_sql, constants = self._extract_and_replace_constants(canonical_sql)
            
            # Additional normalization
            normalized_sql = self._apply_additional_normalization(normalized_sql)
            
            logger.debug(f"Normalized SQL: {sql} -> {normalized_sql}")
            return normalized_sql, constants
            
        except Exception as e:
            logger.warning(f"SQL normalization failed for: {sql}, error: {e}")
            # Fallback to basic normalization
            return self._basic_normalize(sql)
    
    def _extract_and_replace_constants(self, sql: str) -> Tuple[str, List[str]]:
        """Extract constants and replace with numbered placeholders"""
        constants = []
        normalized = sql
        placeholder_counter = 1
        
        # Replace string literals first
        def replace_string(match):
            nonlocal placeholder_counter
            # Extract the content inside the quotes
            string_value = match.group(1)
            constants.append(string_value)
            placeholder = f"${placeholder_counter}"
            placeholder_counter += 1
            return f"'{placeholder}'"
            
        normalized = self.string_pattern.sub(replace_string, normalized)
        
        # Replace numeric literals (but avoid existing placeholders)
        # Use a more robust pattern that doesn't match $n patterns
        number_pattern = re.compile(r'(?<!\$)\b\d+(?:\.\d+)?\b')
        
        def replace_number(match):
            nonlocal placeholder_counter
            number = match.group(0)
            constants.append(number)
            placeholder = f"${placeholder_counter}"
            placeholder_counter += 1
            return placeholder
            
        normalized = number_pattern.sub(replace_number, normalized)
        
        logger.debug(f"Constants extracted: {constants}")
        return normalized, constants
    
    def _apply_additional_normalization(self, sql: str) -> str:
        """Apply additional normalization rules"""
        # Convert to lowercase
        normalized = sql.lower()
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove extra spaces around operators
        normalized = re.sub(r'\s*([=<>!]+)\s*', r' \1 ', normalized)
        
        # Normalize ASC/DESC in ORDER BY
        normalized = re.sub(r'\border\s+by\s+([^,\s]+)\s+asc\b', r'ORDER BY \1', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def _basic_normalize(self, sql: str) -> Tuple[str, List[str]]:
        """Fallback basic normalization when sqlglot fails"""
        constants = []
        normalized = sql.lower()
        placeholder_counter = 1
        
        # Extract string constants
        def replace_string(match):
            nonlocal placeholder_counter
            constants.append(match.group(1))
            placeholder = f"${placeholder_counter}"
            placeholder_counter += 1
            return f"'{placeholder}'"
            
        normalized = self.string_pattern.sub(replace_string, normalized)
        
        # Extract numeric constants - use improved pattern to avoid $n placeholders
        number_pattern = re.compile(r'(?<!\$)\b\d+(?:\.\d+)?\b')
        def replace_number(match):
            nonlocal placeholder_counter
            constants.append(match.group(0))
            placeholder = f"${placeholder_counter}"
            placeholder_counter += 1
            return placeholder
            
        normalized = number_pattern.sub(replace_number, normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        logger.debug(f"Basic normalize - Constants extracted: {constants}")
        return normalized, constants
    
    def validate_sql_safety(self, sql: str) -> bool:
        """
        Basic safety validation - ensure SQL is read-only
        
        Args:
            sql: SQL query to validate
            
        Returns:
            True if safe, False otherwise
        """
        try:
            # Parse SQL
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.postgres.Postgres)
            if not parsed:
                return False
                
            # Check if it's a SELECT statement
            if not isinstance(parsed, sqlglot.expressions.Select):
                logger.warning(f"Non-SELECT query rejected: {sql}")
                return False
                
            # Check for forbidden patterns in raw SQL
            sql_lower = sql.lower()
            forbidden_keywords = [
                'insert', 'update', 'delete', 'drop', 'truncate', 
                'alter', 'create', 'grant', 'revoke', 'copy', 'execute'
            ]
            
            for keyword in forbidden_keywords:
                if f' {keyword} ' in f' {sql_lower} ':
                    logger.warning(f"Forbidden keyword '{keyword}' found in: {sql}")
                    return False
                    
            # Check for multiple statements
            if ';' in sql.rstrip(';'):
                logger.warning(f"Multiple statements detected in: {sql}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"SQL safety validation failed for: {sql}, error: {e}")
            return False
    
    def extract_table_references(self, sql: str) -> List[str]:
        """Extract table names referenced in the SQL query"""
        try:
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.postgres.Postgres)
            if not parsed:
                return []
                
            tables = []
            for table in parsed.find_all(sqlglot.expressions.Table):
                if table.name:
                    tables.append(table.name.lower())
                    
            return list(set(tables))  # Remove duplicates
            
        except Exception as e:
            logger.warning(f"Table extraction failed for: {sql}, error: {e}")
            return []
    
    def complexity_score(self, sql: str) -> int:
        """
        Calculate a complexity score for the SQL query
        
        Returns:
            Integer score (higher = more complex)
        """
        try:
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.postgres.Postgres)
            if not parsed:
                return 100  # High score for unparseable queries
                
            score = 0
            
            # Count JOINs
            joins = list(parsed.find_all(sqlglot.expressions.Join))
            score += len(joins) * 10
            
            # Count subqueries
            subqueries = list(parsed.find_all(sqlglot.expressions.Subquery))
            score += len(subqueries) * 15
            
            # Count aggregations
            aggregates = list(parsed.find_all(sqlglot.expressions.Func))
            score += len(aggregates) * 5
            
            # Count WHERE conditions
            where_conditions = list(parsed.find_all(sqlglot.expressions.Where))
            score += len(where_conditions) * 3
            
            return score
            
        except Exception as e:
            logger.warning(f"Complexity scoring failed for: {sql}, error: {e}")
            return 50  # Medium score for problematic queries
