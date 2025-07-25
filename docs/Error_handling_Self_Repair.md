# Error Handling & Self-Repair

## Purpose
Define how errors are detected, reported, and corrected in the GPT SQL generation pipeline.

---

## Types of Errors
1. **Syntax Errors:** SQL parser (e.g., `pglast`) detects invalid SQL.
2. **Execution Errors:** Postgres returns errors (e.g., unknown columns).
3. **Semantic Errors:** Query executes but returns unexpected structure.

---

## Error Recovery Steps
1. **Validation:** Every query is parsed before execution.
2. **Self-Repair:** 
   - If syntax error: send the error back to GPT with a hint.
   - Example:
     ```
     GPT: SELECT * FROM hospitl WHERE drg_code = '470';
     Error: relation "hospitl" does not exist.
     GPT (retry): SELECT * FROM hospitals WHERE drg_code = '470';
     ```
3. **Fallback:** If self-repair fails, gracefully return an error message to the user.

---

## Logging & Monitoring
- All errors are logged with:
  - NL input
  - GPT SQL
  - Error message
- These logs are reviewed to refine prompts or add new templates.

---

## Safe Execution
- Queries run on **read-only connections**.
- No modifications (DDL/DML) are ever allowed.
