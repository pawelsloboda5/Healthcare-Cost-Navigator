# Template Catalog & Vector Search

## Purpose
To manage SQL templates as reusable, **parameterized query patterns** and perform semantic matching using vector search. Templates must be **value-agnostic**, meaning constants (numbers, strings, etc.) are replaced with placeholders like `$1`, `$2`.

---

## Parameterized Templates
- A single template can handle multiple variations of the same query structure.
- Example:
  - User NL: "Cheapest DRG 470 in NY"
  - User NL: "Cheapest DRG 291 in NY"
  - **Both map to the same template**:
    ```sql
    SELECT provider_name, avg_covered_charges
    FROM hospitals
    WHERE ms_drg = $1 AND state = $2
    ORDER BY avg_covered_charges ASC
    LIMIT 1;
    ```

---

## Embedding Templates
- At build time, each template SQL is:
  1. **Normalized:** 
     - Lowercased.
     - Constants replaced with placeholders (`$1, $2`).
     - Whitespace stripped.
  2. **Embedded:** Use `text-embedding-3-small` to generate a 1536-dimensional vector.
  3. **Stored:** Save `canonical_sql`, `raw_sql` (with placeholders), and embedding in Postgres.

---

## Vector Search Logic
1. Take GPT-generated SQL and **normalize it**:
   - Replace constants (e.g., `'470'` or `10001`) with `$const`.
2. Embed the normalized SQL.
3. Search for the **top 3–5 closest templates** in the `template_catalog` using cosine similarity.
4. Apply **edit-distance filtering** (see `Edit_Distance_Filtering.md`) to verify the structural match.
5. If match is confident:
   - Extract the original constants and map them to `$1`, `$2`, etc. (see `Parameter_Extraction_Mapping.md`).

---

## Tools & Libraries
- **Embeddings:** `openai` Python SDK with `text-embedding-3-small`.
- **Vector DB:** PostgreSQL with `pgvector` extension.
- **Parsing & Normalization:** `sqlglot` or `pglast` for AST parsing.

---

## Catalog Table Schema
**Table: `template_catalog`**
| Column          | Type           | Description                             |
|-----------------|----------------|-----------------------------------------|
| template_id     | SERIAL         | Primary key for template                |
| canonical_sql   | TEXT           | Normalized SQL template                 |
| raw_sql         | TEXT           | Original SQL with placeholders          |
| embedding       | VECTOR(1536)   | Embedding vector (pgvector)             |
| comment         | TEXT           | Human-readable description of template  |

---

## Key Advantage
With parameterization, the catalog remains **small and efficient**. Instead of adding separate templates for DRG 470 or 291, one template covers all variations.
