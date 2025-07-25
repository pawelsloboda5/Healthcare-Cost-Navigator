# Catalog Growth Strategy

## Purpose
Describe how the SQL template catalog evolves over time based on free-form queries.

---

## Auto-Promotion of Templates
- **Observation:** If a free-form query pattern is requested repeatedly (e.g., ≥ 5 times), it is **reviewed and added as a template**.
- **Benefit:** Moves traffic from slow NL→SQL path to fast template execution.

---

## Workflow
1. **Monitor Logs:** Track free-form queries and their normalized fingerprints.
2. **Cluster Similar Queries:** Group queries that differ only by constants.
3. **Template Creation:** Extract a generic template (e.g., `WHERE drg_code = $1`).
4. **Embed & Store:** Add to `template_catalog` with embeddings.

---

## Continuous Improvement
- Regularly prune unused templates.
- Optimize prompts by adding examples from new templates.
- Use feedback (user queries or errors) to create new reusable patterns.

---




