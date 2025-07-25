# Parameter Extraction & Mapping

## Purpose
Explain how constants from GPT-generated SQL are **detected, normalized, and mapped** to template placeholders (`$1, $2, ...`).

---

## Example Mapping
**Template (stored in catalog):**  
```sql
SELECT * FROM hospitals
WHERE ms_drg = $1 AND provider_zip = $2;

GPT SQL (raw):
SELECT * FROM hospitals
WHERE ms_drg = '470' AND provider_zip = '10001';

Mapping Result:

$1 → '470'

$2 → '10001'
Extraction Process
Parse SQL: Use sqlglot or pglast to parse GPT SQL into an AST.

Identify Constants:

Numbers (470) → $const.

Strings ('10001') → $const.

Generate Canonical SQL: Replace all constants with $1, $2, ... in the order they appear.

Parameter Array: Store the mapping of placeholders to actual values:
{
  "$1": "470",
  "$2": "10001"
}

Implementation with sqlglot (Example)
import sqlglot
from sqlglot import exp

def normalize_sql(sql: str):
    parsed = sqlglot.parse_one(sql)
    params = []
    counter = 1

    def replace_constants(node):
        nonlocal counter
        if isinstance(node, exp.Literal):
            params.append(node.this)
            return exp.Var(this=f"${counter}")
            counter += 1
        return node

    normalized = parsed.transform(replace_constants)
    return normalized.sql(), params

sql = "SELECT * FROM hospitals WHERE ms_drg = '470' AND provider_zip = '10001';"
canonical, params = normalize_sql(sql)
print(canonical)  # SELECT * FROM hospitals WHERE ms_drg = $1 AND provider_zip = $2
print(params)     # ['470', '10001']

Edge Cases
Repeated Constants:
WHERE drg_code = '470' OR drg_code = '470'

Both map to $1.
IN Clauses:
WHERE drg_code IN ('470','471')
 $1 = ['470','471'].

 Benefits of Parameterization
One template covers all values (no need to add DRG 470, 291, etc. separately).

Safer execution: Parameters are bound via prepared statements.

Efficient matching: Vector search & fingerprinting ignore values and focus on query structure.