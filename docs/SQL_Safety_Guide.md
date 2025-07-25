# SQL Safety Guide

## Purpose
Outline safety measures for handling AI-generated SQL queries.

---

## Key Principles
- **Read-only enforcement:** Use dedicated read-only DB user roles.
- **Whitelist commands:** Only `SELECT` queries are allowed.
- **Parameter binding:** Replace all constants with placeholders (`$1, $2, ...`) to prevent SQL injection.

---

## Validation Pipeline
1. **Syntax Parsing:** Validate SQL with `sqlglot` or `pglast`.
2. **Whitelist Check:** Ensure query starts with `SELECT`.
3. **Edit-Distance Filter:** Confirm similarity with a known template (if applicable).
4. **Parameter Extraction:** Map constants safely.

---

## Forbidden Patterns
- No `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, or `ALTER`.
- No multi-statement queries (`;` separated).
- No `COPY` or `EXECUTE` commands.

---

## Safe Execution Strategy
- Use **prepared statements** with parameters (avoiding string concatenation).
- Maintain **audit logs** for all executed queries.

