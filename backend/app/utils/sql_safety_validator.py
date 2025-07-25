"""
SQL Safety Validator
Comprehensive safety validation for AI-generated SQL queries
"""
import sqlglot
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ValidationResult(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    WARNING = "warning"

@dataclass
class ValidationIssue:
    """Represents a validation issue found in SQL"""
    severity: ValidationResult
    category: str
    message: str
    sql_fragment: Optional[str] = None

@dataclass
class SafetyReport:
    """Complete safety validation report"""
    is_safe: bool
    overall_score: float  # 0-1, higher is safer
    issues: List[ValidationIssue]
    recommendations: List[str]
    complexity_score: int
    table_references: List[str]

class SQLSafetyValidator:
    """
    Comprehensive SQL safety validator implementing healthcare security standards
    """
    
    def __init__(self):
        # SQL keywords that are forbidden
        self.forbidden_keywords = {
            'insert', 'update', 'delete', 'drop', 'truncate', 'alter',
            'create', 'grant', 'revoke', 'copy', 'execute', 'call',
            'merge', 'replace', 'upsert', 'pg_', 'dblink'
        }
        
        # Allowed SQL functions (whitelist approach)
        self.allowed_functions = {
            # Aggregation functions
            'count', 'sum', 'avg', 'min', 'max', 'stddev', 'variance',
            # String functions
            'upper', 'lower', 'trim', 'ltrim', 'rtrim', 'substring', 'length',
            'concat', 'coalesce', 'nullif', 'ilike', 'like',
            # Date functions
            'now', 'current_date', 'current_timestamp', 'extract', 'date_part',
            'age', 'date_trunc',
            # Math functions
            'abs', 'ceil', 'floor', 'round', 'power', 'sqrt',
            # Type conversion
            'cast', 'to_char', 'to_date', 'to_number'
        }
        
        # Healthcare-specific table whitelist
        self.allowed_tables = {
            'providers', 'drg_procedures', 'provider_procedures', 
            'provider_ratings', 'template_catalog', 'csv_column_mappings'
        }
        
        # Complexity thresholds
        self.max_joins = 5
        self.max_subqueries = 3
        self.max_where_conditions = 10
        self.max_result_limit = 1000
    
    def validate_sql(self, sql: str) -> SafetyReport:
        """
        Perform comprehensive safety validation on SQL query
        
        Args:
            sql: SQL query to validate
            
        Returns:
            Complete safety report
        """
        try:
            issues = []
            recommendations = []
            
            # Clean and prepare SQL
            sql = self._clean_sql(sql)
            
            # Basic syntax validation
            syntax_issues = self._validate_syntax(sql)
            issues.extend(syntax_issues)
            
            # Parse SQL for detailed analysis
            try:
                parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.PostgreSQL)
                if not parsed:
                    issues.append(ValidationIssue(
                        ValidationResult.UNSAFE,
                        "syntax",
                        "Failed to parse SQL query"
                    ))
                    return self._create_unsafe_report(issues, recommendations)
                
                # Perform detailed validations
                issues.extend(self._validate_statement_type(parsed))
                issues.extend(self._validate_keywords(sql))
                issues.extend(self._validate_functions(parsed))
                issues.extend(self._validate_tables(parsed))
                issues.extend(self._validate_complexity(parsed))
                issues.extend(self._validate_injection_patterns(sql))
                issues.extend(self._validate_data_exposure(parsed))
                
                # Get table references and complexity
                table_references = self._extract_table_references(parsed)
                complexity_score = self._calculate_complexity(parsed)
                
                # Generate recommendations
                recommendations = self._generate_recommendations(issues, complexity_score)
                
                # Calculate overall safety score
                safety_score = self._calculate_safety_score(issues, complexity_score)
                is_safe = safety_score >= 0.7 and not any(issue.severity == ValidationResult.UNSAFE for issue in issues)
                
                return SafetyReport(
                    is_safe=is_safe,
                    overall_score=safety_score,
                    issues=issues,
                    recommendations=recommendations,
                    complexity_score=complexity_score,
                    table_references=table_references
                )
                
            except Exception as e:
                logger.error(f"SQL parsing failed: {e}")
                issues.append(ValidationIssue(
                    ValidationResult.UNSAFE,
                    "parsing",
                    f"SQL parsing failed: {str(e)}"
                ))
                return self._create_unsafe_report(issues, recommendations)
                
        except Exception as e:
            logger.error(f"SQL validation failed: {e}")
            return self._create_unsafe_report([
                ValidationIssue(ValidationResult.UNSAFE, "error", f"Validation failed: {str(e)}")
            ], [])
    
    def _clean_sql(self, sql: str) -> str:
        """Clean and normalize SQL query"""
        # Remove comments
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql)
        
        # Remove trailing semicolons
        sql = sql.rstrip(';').strip()
        
        return sql
    
    def _validate_syntax(self, sql: str) -> List[ValidationIssue]:
        """Basic syntax validation"""
        issues = []
        
        # Check for multiple statements
        if ';' in sql:
            issues.append(ValidationIssue(
                ValidationResult.UNSAFE,
                "syntax",
                "Multiple SQL statements detected",
                sql
            ))
        
        # Check for empty query
        if not sql.strip():
            issues.append(ValidationIssue(
                ValidationResult.UNSAFE,
                "syntax",
                "Empty SQL query"
            ))
        
        # Check for excessively long queries
        if len(sql) > 5000:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                "syntax",
                "SQL query is very long and may be complex"
            ))
        
        return issues
    
    def _validate_statement_type(self, parsed) -> List[ValidationIssue]:
        """Validate that only SELECT statements are allowed"""
        issues = []
        
        if not isinstance(parsed, sqlglot.expressions.Select):
            issues.append(ValidationIssue(
                ValidationResult.UNSAFE,
                "statement_type",
                f"Only SELECT statements are allowed, found: {type(parsed).__name__}",
                str(parsed)
            ))
        
        return issues
    
    def _validate_keywords(self, sql: str) -> List[ValidationIssue]:
        """Check for forbidden SQL keywords"""
        issues = []
        sql_lower = sql.lower()
        
        for keyword in self.forbidden_keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_lower):
                issues.append(ValidationIssue(
                    ValidationResult.UNSAFE,
                    "forbidden_keyword",
                    f"Forbidden keyword detected: {keyword}",
                    keyword
                ))
        
        return issues
    
    def _validate_functions(self, parsed) -> List[ValidationIssue]:
        """Validate SQL functions against whitelist"""
        issues = []
        
        for func in parsed.find_all(sqlglot.expressions.Func):
            func_name = func.this.lower() if func.this else str(func).split('(')[0].lower()
            
            if func_name not in self.allowed_functions:
                issues.append(ValidationIssue(
                    ValidationResult.WARNING,
                    "function",
                    f"Non-whitelisted function used: {func_name}",
                    str(func)
                ))
        
        return issues
    
    def _validate_tables(self, parsed) -> List[ValidationIssue]:
        """Validate table references against whitelist"""
        issues = []
        
        for table in parsed.find_all(sqlglot.expressions.Table):
            table_name = table.name.lower() if table.name else str(table).lower()
            
            if table_name not in self.allowed_tables:
                issues.append(ValidationIssue(
                    ValidationResult.UNSAFE,
                    "table_access",
                    f"Access to non-whitelisted table: {table_name}",
                    str(table)
                ))
        
        return issues
    
    def _validate_complexity(self, parsed) -> List[ValidationIssue]:
        """Validate query complexity"""
        issues = []
        
        # Count JOINs
        joins = list(parsed.find_all(sqlglot.expressions.Join))
        if len(joins) > self.max_joins:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                "complexity",
                f"Too many JOINs: {len(joins)} (max: {self.max_joins})"
            ))
        
        # Count subqueries
        subqueries = list(parsed.find_all(sqlglot.expressions.Subquery))
        if len(subqueries) > self.max_subqueries:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                "complexity",
                f"Too many subqueries: {len(subqueries)} (max: {self.max_subqueries})"
            ))
        
        # Check LIMIT clause
        limit_clause = parsed.find(sqlglot.expressions.Limit)
        if limit_clause:
            try:
                limit_value = int(str(limit_clause.expression))
                if limit_value > self.max_result_limit:
                    issues.append(ValidationIssue(
                        ValidationResult.WARNING,
                        "complexity",
                        f"LIMIT too high: {limit_value} (max: {self.max_result_limit})"
                    ))
            except (ValueError, AttributeError):
                pass
        else:
            issues.append(ValidationIssue(
                ValidationResult.WARNING,
                "complexity",
                "No LIMIT clause specified - query may return too many results"
            ))
        
        return issues
    
    def _validate_injection_patterns(self, sql: str) -> List[ValidationIssue]:
        """Check for SQL injection patterns"""
        issues = []
        
        # Common injection patterns
        injection_patterns = [
            r"'\s*or\s+'",  # 'OR' injection
            r"'\s*and\s+'", # 'AND' injection
            r"--",          # Comment injection
            r"/\*.*\*/",    # Block comment injection
            r";\s*drop\s+", # Drop injection
            r"union\s+select", # UNION injection
            r"exec\s*\(",   # Exec injection
        ]
        
        sql_lower = sql.lower()
        for pattern in injection_patterns:
            if re.search(pattern, sql_lower):
                issues.append(ValidationIssue(
                    ValidationResult.UNSAFE,
                    "injection",
                    f"Potential SQL injection pattern detected: {pattern}",
                    re.search(pattern, sql_lower).group() if re.search(pattern, sql_lower) else None
                ))
        
        return issues
    
    def _validate_data_exposure(self, parsed) -> List[ValidationIssue]:
        """Check for potential data exposure risks"""
        issues = []
        
        # Check for SELECT *
        for select in parsed.find_all(sqlglot.expressions.Select):
            for expression in select.expressions:
                if isinstance(expression, sqlglot.expressions.Star):
                    issues.append(ValidationIssue(
                        ValidationResult.WARNING,
                        "data_exposure",
                        "SELECT * may expose sensitive data - specify columns explicitly"
                    ))
        
        return issues
    
    def _extract_table_references(self, parsed) -> List[str]:
        """Extract all table references from the query"""
        tables = []
        for table in parsed.find_all(sqlglot.expressions.Table):
            if table.name:
                tables.append(table.name.lower())
        return list(set(tables))
    
    def _calculate_complexity(self, parsed) -> int:
        """Calculate query complexity score"""
        score = 0
        
        # Base score for SELECT
        score += 1
        
        # JOINs add complexity
        joins = list(parsed.find_all(sqlglot.expressions.Join))
        score += len(joins) * 2
        
        # Subqueries add complexity
        subqueries = list(parsed.find_all(sqlglot.expressions.Subquery))
        score += len(subqueries) * 3
        
        # WHERE conditions add complexity
        where_conditions = list(parsed.find_all(sqlglot.expressions.Where))
        score += len(where_conditions)
        
        # Functions add complexity
        functions = list(parsed.find_all(sqlglot.expressions.Func))
        score += len(functions)
        
        # ORDER BY adds complexity
        order_by = list(parsed.find_all(sqlglot.expressions.Order))
        score += len(order_by)
        
        return score
    
    def _calculate_safety_score(self, issues: List[ValidationIssue], complexity: int) -> float:
        """Calculate overall safety score (0-1)"""
        base_score = 1.0
        
        # Deduct points for issues
        for issue in issues:
            if issue.severity == ValidationResult.UNSAFE:
                base_score -= 0.5
            elif issue.severity == ValidationResult.WARNING:
                base_score -= 0.1
        
        # Deduct points for high complexity
        if complexity > 20:
            base_score -= 0.2
        elif complexity > 10:
            base_score -= 0.1
        
        return max(0.0, base_score)
    
    def _generate_recommendations(self, issues: List[ValidationIssue], complexity: int) -> List[str]:
        """Generate recommendations based on found issues"""
        recommendations = []
        
        # Issue-specific recommendations
        for issue in issues:
            if issue.category == "complexity" and "LIMIT" in issue.message:
                recommendations.append("Add a reasonable LIMIT clause to prevent excessive results")
            elif issue.category == "data_exposure":
                recommendations.append("Specify column names explicitly instead of using SELECT *")
            elif issue.category == "function":
                recommendations.append("Review non-standard functions for security implications")
        
        # General recommendations
        if complexity > 15:
            recommendations.append("Consider simplifying the query to reduce complexity")
        
        if not any(issue.category == "injection" for issue in issues):
            recommendations.append("Use parameterized queries to prevent SQL injection")
        
        return list(set(recommendations))  # Remove duplicates
    
    def _create_unsafe_report(self, issues: List[ValidationIssue], recommendations: List[str]) -> SafetyReport:
        """Create a safety report for unsafe queries"""
        return SafetyReport(
            is_safe=False,
            overall_score=0.0,
            issues=issues,
            recommendations=recommendations,
            complexity_score=100,  # High complexity for failed queries
            table_references=[]
        )
    
    def is_query_safe(self, sql: str) -> bool:
        """Quick safety check - returns True if query is safe"""
        report = self.validate_sql(sql)
        return report.is_safe
    
    def get_safety_summary(self, sql: str) -> str:
        """Get a human-readable safety summary"""
        report = self.validate_sql(sql)
        
        if report.is_safe:
            return f"Query is SAFE (score: {report.overall_score:.2f})"
        else:
            unsafe_count = sum(1 for issue in report.issues if issue.severity == ValidationResult.UNSAFE)
            warning_count = sum(1 for issue in report.issues if issue.severity == ValidationResult.WARNING)
            return f"Query is UNSAFE (score: {report.overall_score:.2f}, {unsafe_count} errors, {warning_count} warnings)" 