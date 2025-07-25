# AI SQL Generation

## Purpose
This document explains our approach to GPT-driven SQL generation. It focuses on leveraging GPT models (e.g., GPT-4.1) to generate SQL queries based on user natural language (NL) inputs, while keeping the process **safe and schema-aware**.

---

## GPT with Schema + Examples
We provide GPT with:
- A **thin prompt** containing:
  - The **full database schema** (table names, columns, types).
  - **1–2 example NL → SQL mappings** for context.

**Example Prompt (Pseudo-code):**
System: You are a SQL assistant for a PostgreSQL database (read-only).
User: Tables:
hospitals(provider_id, provider_name, city, zip_code, rating)
procedures(ms_drg, drg_desc, avg_covered_charges)

Example 1:
Q: Who has the cheapest DRG 470 within 25 miles of 10001?
A: SELECT provider_name, avg_covered_charges
FROM hospitals h JOIN procedures p ON h.provider_id = p.provider_id
WHERE ms_drg = '470' AND zip_code = '10001'
ORDER BY avg_covered_charges ASC
LIMIT 1;

Now convert: "List top 5 hospitals by rating near 10032."


---

## Example Thin Prompt and Response
**NL Query:**
> "Show all DRG 291 procedures in NY with cost below 20,000."

**GPT Response:**
```sql
SELECT provider_name, avg_covered_charges
FROM hospitals h
JOIN procedures p ON h.provider_id = p.provider_id
WHERE p.ms_drg = '291'
  AND h.state = 'NY'
  AND avg_covered_charges < 20000;

Safety Considerations
Read-Only: We enforce that GPT must not use INSERT, UPDATE, DELETE, or DDL statements.

Validation: Every generated SQL query passes through:

A parser (e.g., sqlglot or pglast) for syntactic checks.

A safety filter to ensure only SELECT statements are executed.

Error Handling: If GPT generates invalid SQL, we:

Return a safe error message or

Ask GPT once to self-correct, with error feedback.


---

### **SQL_Normalization_Fingerprinting.md**
```markdown
# SQL Normalization & Fingerprinting

## Purpose
This document describes how SQL queries are normalized and fingerprinted for reliable template matching and caching.

---

## Steps for Normalization
1. **Lower-case:** Convert all SQL keywords and identifiers to lowercase.
2. **Whitespace Stripping:** Remove redundant spaces, newlines, and formatting.
3. **Constant Replacement:** Replace all literal values (e.g., numbers, strings) with `$const`.

---

## Canonical Predicate Ordering
- We use `sqlglot` or `pglast` to parse and reassemble queries.
- **Example:**
  ```sql
  SELECT * FROM hospitals WHERE zip = '10001' AND drg_code = '470';
Normalizes to:
select * from hospitals where drg_code = $const and zip = $const;
Predicates (e.g., AND clauses) are ordered alphabetically for consistency.
Hashing/Encoding
The canonical query string is hashed (e.g., SHA256 or MD5).

This fingerprint is used as a unique key for:

Catalog lookups.

Caching vector embeddings.

Identifying duplicate queries.


---

### **Template_Catalog_Vector_Search.md**
```markdown
# Template Catalog & Vector Search

## Purpose
To manage SQL templates as reusable query patterns and perform semantic matching using vector search.

---

## Embedding Templates
- At build time, each **template SQL** is:
  1. Normalized to a canonical form.
  2. Embedded using OpenAI's `text-embedding-3-small` model.
  3. Stored in a **pgvector index** within PostgreSQL.

---

## Vector Search Logic
1. For a generated SQL query, compute its normalized fingerprint.
2. Embed the canonical SQL string.
3. Perform **cosine similarity search** in `pgvector` to retrieve the **3–5 nearest templates**.
4. Select the best candidate using edit-distance filtering (see next doc).

---

## Tools & Libraries
- **Embeddings:** `openai` Python SDK (model: `text-embedding-3-small`).
- **Vector DB:** PostgreSQL with `pgvector` extension.
- **Search:** SQL query:
  ```sql
  SELECT template_id, 1 - (embedding <=> query_embedding) AS similarity
  FROM template_catalog
  ORDER BY similarity DESC
  LIMIT 5;
Data Structure of Catalog
Table: template_catalog

Column	Type	Description
template_id	SERIAL	Primary key for template
canonical_sql	TEXT	Normalized SQL template
raw_sql	TEXT	Original SQL with placeholders
embedding	VECTOR(1536)	Embedding vector (pgvector)
comment	TEXT	Human-readable description of template


---

### **Edit_Distance_Filtering.md**
```markdown
# Edit Distance Filtering

## Purpose
To refine template matching by ensuring that the GPT-generated SQL is **semantically close** to a known template before execution.

---

## Similarity Metrics
- **Levenshtein Distance:** Measures character-level edits between queries.
- **Token-level Jaccard Similarity:** Compares overlap of SQL tokens.

---

## Recommended Threshold
- Accept match if:

distance < θ (θ ≈ 0.15)
where distance is normalized Levenshtein (0 = identical, 1 = totally different).

---

## Example
**Template:**  
```sql
select * from hospitals where drg_code = $1;

Generated SQL:
select * from hospitals where drg_code = '470';
Token-level difference is minimal (≈0.0), so it is a match.
Rejected Example:
delete from hospitals where drg_code = '470';
Different command (DELETE vs SELECT) → fails safety & distance check.

---

### **Parameter_Extraction_Mapping.md**
```markdown
# Parameter Extraction & Mapping

## Purpose
Explain how constants from GPT-generated SQL are extracted and mapped to template placeholders.

---

## Example Mapping
**Template:**  
```sql
select * from hospitals where drg_code = $1 and provider_zip = $2;

GPT SQL:
select * from hospitals where drg_code = '470' and provider_zip = '10001';

Mapping Result:

$1 → '470'

$2 → '10001'

Extraction Process
Parse GPT SQL using sqlglot or pglast.

Identify literal constants in the WHERE clause.

Replace constants with placeholder positions ($1, $2, …).

Build a parameter array to bind during execution.

Handling Multiple Constants
For repeated values:

e.g., WHERE drg_code = '470' OR drg_code = '470'

Map both to the same placeholder $1.

Edge cases:

Constants in IN clauses are extracted as arrays (e.g., $1 = ['10001','10002']).


