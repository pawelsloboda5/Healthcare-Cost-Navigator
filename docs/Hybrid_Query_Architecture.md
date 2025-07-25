# Hybrid Query Architecture

## Purpose
This document explains the **hybrid architecture** that combines a **template-first approach** with a **free-form GPT SQL fallback**. This design optimizes speed, accuracy, and safety.

---

## Overview
The hybrid query process follows two paths:
1. **Step A: Template Retriever → GPT Tool Choice**
   - The system retrieves **10–20 known query templates**.
   - GPT selects the best template based on user NL input.
   - This path handles **80–90% of queries** with **low latency**.
2. **Step B: Free-form NL→SQL → Fuzzy Match**
   - For queries that do not fit a template, GPT generates SQL directly.
   - The query undergoes normalization, fingerprinting, and vector search to find the closest template.
   - If no match is found, the SQL is validated and executed safely.

---

## Architecture Diagram
User NL
├─► Step A: Template Retriever → GPT tool-choice
│ └─► Template ⇒ Execute
│
└─► Step B: NL→SQL→fuzzy-match (slow path)
├─► Match success ⇒ Execute ⇒ promote if popular
└─► Match fail ⇒ lint + run read-only / graceful error


---

## Benefits of Hybrid Approach
- **Fastest response** for common queries (template catalog).
- **Flexibility** for uncommon NL inputs.
- **Self-optimizing:** Popular free-form queries get promoted to templates over time.

---

## Implementation Notes
- Template catalog uses **pgvector** embeddings and similarity search.
- Fallback path uses **sqlglot/pglast** for normalization and edit-distance filtering.
- Safety checks and parameter mapping are consistent between both paths.



