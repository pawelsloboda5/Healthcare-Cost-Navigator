# Embedding & RAG (Retrieval-Augmented Generation)

## Purpose
Explain how embeddings and RAG are used to improve GPT query generation and context understanding.

---

## Embedding Process
1. **Generate Embeddings:** Use OpenAI's `text-embedding-3-small` model.
2. **Store in Vector DB:** Save embeddings in Postgres using the `pgvector` extension.
3. **Attach Metadata:** Each embedding includes:
   - Template SQL
   - Canonical form
   - Description

---

## RAG Workflow
1. **User Query:** The NL input is embedded.
2. **Vector Search:** Find the most relevant templates or context from the database.
3. **Prompt GPT:** Provide the retrieved context/templates alongside the user question.
4. **Generate SQL:** GPT produces SQL using the context, increasing accuracy.

---

## Example RAG Prompt
System: Use these SQL templates as reference:

SELECT ... WHERE drg_code = $1;

SELECT ... WHERE provider_zip = $1 AND rating > $2;

User: Find the cheapest DRG 470 near 10001.

---

## Tools & Libraries
- **pgvector:** Vector indexing & similarity search.
- **OpenAI Embeddings:** `text-embedding-3-small` for fast, cost-efficient embeddings.
