#!/usr/bin/env python3
"""
Seed Template Catalog with Initial SQL Templates
Populates the template_catalog table with healthcare query templates
"""
import asyncio
import sys
import os
from pathlib import Path
import re
import logging

import openai
import sqlglot
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ─── App imports -------------------------------------------------------------
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

from app.core.database import AsyncSessionLocal, init_db
from app.models.models import TemplateCatalog

# ─── Logging ----------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Seeder -----------------------------------------------------------------
class TemplateSeeder:
    def __init__(self) -> None:
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # ────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────
    def normalize_sql(self, sql: str) -> str:
        """
        Use SQLGlot to pretty-print / canonicalise the query,
        then replace literals with numbered placeholders ($1, $2, …).
        """
        try:
            # 1. Parse & pretty-print
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.Postgres)
            normalized = parsed.sql(dialect=sqlglot.dialects.Postgres, pretty=True)

            # 2. Parameterise (simple regex fallback)
            param_counter = 1

            def repl_string(match):
                nonlocal param_counter
                placeholder = f"${param_counter}"
                param_counter += 1
                return f"'{placeholder}'"

            def repl_number(match):
                nonlocal param_counter
                placeholder = f"${param_counter}"
                param_counter += 1
                return placeholder

            normalized = re.sub(r"'([^']*)'", repl_string, normalized)
            normalized = re.sub(r"\b\d+\.?\d*\b", repl_number, normalized)

            return normalized.lower().strip()

        except Exception as e:  # pragma: no cover
            logger.warning(
                f"SQLGlot parsing failed, falling back to naive normalisation: {e}"
            )
            return re.sub(r"\s+", " ", sql.strip()).lower()

    async def get_embedding(self, text: str) -> list[float]:
        """Fetch embedding from OpenAI; returns [] on failure."""
        try:
            resp = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return resp.data[0].embedding
        except Exception as e:  # pragma: no cover
            logger.error(f"Embedding generation error: {e}")
            return []

    # ────────────────────────────────────────────────────────────────────
    # Templates
    # ────────────────────────────────────────────────────────────────────
    def get_initial_templates(self) -> list[dict]:
        """
        Initial catalogue based on PLAN.md & common healthcare queries.
        Each entry gets normalised + embedded before insertion.
        """
        return [
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d       ON pp.drg_code    = d.drg_code
                    WHERE d.drg_code = $1
                      AND p.provider_state = $2
                    ORDER BY pp.average_covered_charges
                    LIMIT $3;
                """,
                "comment": "Find cheapest providers for a DRG in a state",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pr.overall_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    WHERE p.provider_city ILIKE $1
                    ORDER BY pr.overall_rating DESC
                    LIMIT $2;
                """,
                "comment": "Highest-rated providers in a city",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           p.provider_city,
                           p.provider_state,
                           p.provider_zip_code
                    FROM providers p
                    WHERE p.provider_zip_code LIKE $1
                    LIMIT $2;
                """,
                "comment": "Providers near a ZIP-code prefix",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.total_discharges,
                           pp.average_covered_charges,
                           d.drg_description
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE pp.drg_code = $1
                    ORDER BY pp.total_discharges DESC
                    LIMIT $2;
                """,
                "comment": "High-volume providers for a procedure",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           pp.average_total_payments,
                           pr.overall_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d       ON pp.drg_code    = d.drg_code
                    LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY pp.average_covered_charges
                    LIMIT $3;
                """,
                "comment": "Providers by procedure description in a state",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pr.overall_rating,
                           pr.quality_rating,
                           pr.safety_rating,
                           pr.patient_experience_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    WHERE pr.overall_rating >= $1
                      AND p.provider_state = $2
                    ORDER BY pr.overall_rating DESC
                    LIMIT $3;
                """,
                "comment": "Providers above rating threshold in a state",
            },
            {
                "raw_sql": """
                    SELECT d.drg_code,
                           d.drg_description,
                           COUNT(*)                        AS provider_count,
                           AVG(pp.average_covered_charges) AS avg_cost
                    FROM drg_procedures d
                    JOIN provider_procedures pp ON d.drg_code = pp.drg_code
                    JOIN providers p           ON pp.provider_id = p.provider_id
                    WHERE p.provider_state = $1
                    GROUP BY d.drg_code, d.drg_description
                    ORDER BY avg_cost
                    LIMIT $2;
                """,
                "comment": "Most affordable procedures in a state",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           pp.average_medicare_payments,
                           (pp.average_covered_charges - pp.average_medicare_payments)
                               AS patient_cost,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE pp.drg_code = $1
                      AND p.provider_zip_code LIKE $2
                    ORDER BY patient_cost
                    LIMIT $3;
                """,
                "comment": "Lowest patient out-of-pocket providers for a procedure",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           pr.overall_rating,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state,
                           (pp.average_covered_charges * 0.3 +
                            (10 - pr.overall_rating) * 1000) AS cost_quality_score
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN provider_ratings pr    ON p.provider_id = pr.provider_id
                    JOIN drg_procedures d       ON pp.drg_code = d.drg_code
                    WHERE pp.drg_code = $1
                      AND p.provider_state = $2
                    ORDER BY cost_quality_score
                    LIMIT $3;
                """,
                "comment": "Best cost-quality balance for a procedure",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           COUNT(DISTINCT pp.drg_code) AS procedure_count,
                           AVG(pr.overall_rating)       AS avg_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    WHERE p.provider_city ILIKE $1
                    GROUP BY p.provider_id, p.provider_name,
                             p.provider_city, p.provider_state
                    HAVING COUNT(DISTINCT pp.drg_code) >= $2
                    ORDER BY avg_rating DESC
                    LIMIT $3;
                """,
                "comment": "Multi-procedure providers in a city with good ratings",
            },
        ]

    # ────────────────────────────────────────────────────────────────────
    # Main seeding routine
    # ────────────────────────────────────────────────────────────────────
    async def seed_templates(self) -> None:
        logger.info("Seeding template catalog…")
        await init_db()

        templates = self.get_initial_templates()

        async with AsyncSessionLocal() as session:
            try:
                # Start fresh
                await session.execute(text("DELETE FROM template_catalog"))

                for idx, tpl in enumerate(templates, 1):
                    logger.info("Processing template %d/%d", idx, len(templates))

                    raw_sql = tpl["raw_sql"].strip()
                    comment = tpl["comment"]

                    canonical_sql = self.normalize_sql(raw_sql)
                    embedding = await self.get_embedding(canonical_sql)

                    if not embedding:
                        logger.warning("Skipping template %d (embedding failed)", idx)
                        continue

                    session.add(
                        TemplateCatalog(
                            canonical_sql=canonical_sql,
                            raw_sql=raw_sql,
                            embedding=embedding,
                            comment=comment,
                        )
                    )

                await session.commit()
                logger.info("Inserted %d templates", len(templates))

                # Create vector index (if pgvector installed)
                await session.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS idx_template_embedding
                    ON template_catalog
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100);
                    """
                    )
                )
                await session.commit()
                logger.info("Vector similarity index ensured")

            except Exception as exc:  # pragma: no cover
                await session.rollback()
                logger.error("Seeding failed: %s", exc)
                raise


# ─── Entrypoint --------------------------------------------------------------
async def main() -> None:
    await TemplateSeeder().seed_templates()


if __name__ == "__main__":
    asyncio.run(main())
