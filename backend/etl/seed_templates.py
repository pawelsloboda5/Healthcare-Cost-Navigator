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
from dotenv import load_dotenv

# ─── Load environment variables ---------------------------------------------
env_path = Path(__file__).parent.parent / ".env"
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)

# ─── Check environment variables ---------------------------------------------
database_url = os.getenv('DATABASE_URL')
openai_api_key = os.getenv('OPENAI_API_KEY')

print(f"DATABASE_URL: {'SET' if database_url else 'NOT SET'}")
print(f"OPENAI_API_KEY: {'SET' if openai_api_key else 'NOT SET'}")

if not database_url:
    print("ERROR: DATABASE_URL environment variable is not set!")
    print("Please create a .env file in the backend directory with:")
    print("DATABASE_URL=postgresql+asyncpg://postgres:Warmia50587@localhost:5432/healthcare_cost_navigator")
    sys.exit(1)

if not openai_api_key:
    print("ERROR: OPENAI_API_KEY environment variable is not set!")
    print("Please add your OpenAI API key to the .env file")
    sys.exit(1)

# ─── App imports -------------------------------------------------------------
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

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
        Preserves existing parameter placeholders.
        """
        try:
            # 1. Parse & pretty-print
            parsed = sqlglot.parse_one(sql, dialect=sqlglot.dialects.Postgres)
            normalized = parsed.sql(dialect=sqlglot.dialects.Postgres, pretty=True)

            # 2. Check if template already has parameters - if so, preserve them
            import re
            existing_params = re.findall(r'\$\d+', normalized)
            if existing_params:
                # Template already parameterized, just normalize formatting
                return normalized.lower().strip()

            # 3. Parameterise only if no existing parameters (simple regex fallback)
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
        Comprehensive catalogue covering all common healthcare query patterns.
        Each entry gets normalised + embedded before insertion.
        """
        return [
            # ═══════════════════════════════════════════════════════════════
            # CHEAPEST PROVIDERS - Core patterns
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $3;
                """,
                "comment": "Cheapest providers for a procedure by description in a state",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_code = $1
                      AND p.provider_state = $2
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $3;
                """,
                "comment": "Cheapest providers for a DRG in a state",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state,
                           pp.total_discharges
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $2;
                """,
                "comment": "Cheapest providers nationwide for any procedure by description",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_city ILIKE $2
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $3;
                """,
                "comment": "Cheapest providers for a procedure in a city",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # MOST EXPENSIVE PROVIDERS - Missing pattern
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY pp.average_covered_charges DESC
                    LIMIT $3;
                """,
                "comment": "Most expensive providers for a procedure by description in a state",
            },
            {
                "raw_sql": """
                    SELECT d.drg_code,
                           d.drg_description,
                           AVG(pp.average_covered_charges) AS avg_cost,
                           MAX(pp.average_covered_charges) AS max_cost,
                           COUNT(*) AS provider_count
                    FROM drg_procedures d
                    JOIN provider_procedures pp ON d.drg_code = pp.drg_code
                    JOIN providers p ON pp.provider_id = p.provider_id
                    WHERE p.provider_state = $1
                    GROUP BY d.drg_code, d.drg_description
                    ORDER BY avg_cost DESC
                    LIMIT $2;
                """,
                "comment": "Most expensive procedures in a state by average cost",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # HIGHEST RATED PROVIDERS - Enhanced patterns
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pr.overall_rating,
                           pr.quality_rating,
                           pr.safety_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                    ORDER BY pr.overall_rating DESC
                    LIMIT $2;
                """,
                "comment": "Highest rated providers for a specific procedure",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pr.overall_rating,
                           pr.quality_rating,
                           pr.safety_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY pr.overall_rating DESC
                    LIMIT $3;
                """,
                "comment": "Highest rated providers for a procedure in a state",
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
            
            # ═══════════════════════════════════════════════════════════════
            # VOLUME LEADERS - Enhanced patterns
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.total_discharges,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE pp.drg_code = $1
                    ORDER BY pp.total_discharges DESC
                    LIMIT $2;
                """,
                "comment": "Volume leaders for a specific DRG code",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.total_discharges,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                    ORDER BY pp.total_discharges DESC
                    LIMIT $2;
                """,
                "comment": "Volume leaders for a procedure by description",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.total_discharges,
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY pp.total_discharges DESC
                    LIMIT $3;
                """,
                "comment": "Volume leaders for a procedure in a state",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # STATE COMPARISONS - New critical pattern
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT p.provider_state,
                           AVG(pp.average_covered_charges) AS avg_cost,
                           MIN(pp.average_covered_charges) AS min_cost,
                           MAX(pp.average_covered_charges) AS max_cost,
                           COUNT(*) AS provider_count
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state IN ($2, $3)
                    GROUP BY p.provider_state
                    ORDER BY avg_cost ASC;
                """,
                "comment": "Compare costs for a procedure between two states",
            },
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           pp.average_covered_charges,
                           p.provider_state,
                           p.provider_city,
                           d.drg_description
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state IN ($2, $3)
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $4;
                """,
                "comment": "Cheapest providers for procedure across multiple states",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # COST-QUALITY BALANCE
            # ═══════════════════════════════════════════════════════════════
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
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY cost_quality_score ASC
                    LIMIT $3;
                """,
                "comment": "Best cost-quality balance for a procedure in a state",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # PATIENT OUT-OF-POCKET COSTS
            # ═══════════════════════════════════════════════════════════════
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
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_state = $2
                    ORDER BY patient_cost ASC
                    LIMIT $3;
                """,
                "comment": "Lowest patient out-of-pocket costs for a procedure in a state",
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
                    ORDER BY patient_cost ASC
                    LIMIT $3;
                """,
                "comment": "Lowest patient out-of-pocket providers for a DRG near ZIP code",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # GEOGRAPHIC QUERIES
            # ═══════════════════════════════════════════════════════════════
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
                           pp.average_covered_charges,
                           d.drg_description,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    JOIN drg_procedures d ON pp.drg_code = d.drg_code
                    WHERE d.drg_description ILIKE $1
                      AND p.provider_zip_code LIKE $2
                    ORDER BY pp.average_covered_charges ASC
                    LIMIT $3;
                """,
                "comment": "Cheapest providers for procedure near ZIP code",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # MULTI-PROCEDURE PROVIDERS
            # ═══════════════════════════════════════════════════════════════
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
            {
                "raw_sql": """
                    SELECT p.provider_name,
                           COUNT(DISTINCT pp.drg_code) AS procedure_count,
                           AVG(pp.average_covered_charges) AS avg_cost,
                           AVG(pr.overall_rating) AS avg_rating,
                           p.provider_city,
                           p.provider_state
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    WHERE p.provider_state = $1
                    GROUP BY p.provider_id, p.provider_name,
                             p.provider_city, p.provider_state
                    HAVING COUNT(DISTINCT pp.drg_code) >= $2
                    ORDER BY procedure_count DESC
                    LIMIT $3;
                """,
                "comment": "Multi-procedure providers in a state ranked by variety",
            },
            
            # ═══════════════════════════════════════════════════════════════
            # AGGREGATED STATISTICS
            # ═══════════════════════════════════════════════════════════════
            {
                "raw_sql": """
                    SELECT d.drg_code,
                           d.drg_description,
                           COUNT(*) AS provider_count,
                           AVG(pp.average_covered_charges) AS avg_cost,
                           MIN(pp.average_covered_charges) AS min_cost,
                           MAX(pp.average_covered_charges) AS max_cost
                    FROM drg_procedures d
                    JOIN provider_procedures pp ON d.drg_code = pp.drg_code
                    JOIN providers p ON pp.provider_id = p.provider_id
                    WHERE p.provider_state = $1
                    GROUP BY d.drg_code, d.drg_description
                    ORDER BY avg_cost ASC
                    LIMIT $2;
                """,
                "comment": "Most affordable procedures in a state with statistics",
            },
            {
                "raw_sql": """
                    SELECT p.provider_state,
                           COUNT(DISTINCT p.provider_id) AS provider_count,
                           COUNT(DISTINCT pp.drg_code) AS procedure_count,
                           AVG(pp.average_covered_charges) AS avg_cost,
                           AVG(pr.overall_rating) AS avg_rating
                    FROM providers p
                    JOIN provider_procedures pp ON p.provider_id = pp.provider_id
                    LEFT JOIN provider_ratings pr ON p.provider_id = pr.provider_id
                    GROUP BY p.provider_state
                    ORDER BY avg_cost ASC
                    LIMIT $1;
                """,
                "comment": "State-level healthcare statistics ranked by cost",
            },
        ]

    # ────────────────────────────────────────────────────────────────────
    # DRG Embeddings for Semantic Search
    # ────────────────────────────────────────────────────────────────────
    async def populate_drg_embeddings(self) -> None:
        """
        Generate and populate embeddings for DRG procedure descriptions
        to enable semantic search (e.g., "heart surgery" -> "CORONARY BYPASS")
        """
        logger.info("Populating DRG procedure embeddings for semantic search...")
        await init_db()

        async with AsyncSessionLocal() as session:
            try:
                # Get all DRG procedures without embeddings
                result = await session.execute(
                    text("SELECT drg_code, drg_description FROM drg_procedures WHERE embedding IS NULL ORDER BY drg_code")
                )
                procedures = result.fetchall()
                
                if not procedures:
                    logger.info("All DRG procedures already have embeddings")
                    return

                logger.info(f"Generating embeddings for {len(procedures)} DRG procedures...")
                
                # Process in batches to avoid overwhelming OpenAI API
                batch_size = 20
                processed = 0
                
                for i in range(0, len(procedures), batch_size):
                    batch = procedures[i:i + batch_size]
                    
                    for proc in batch:
                        try:
                            # Generate embedding for the DRG description
                            embedding = await self.get_embedding(proc.drg_description)
                            
                            if embedding:
                                # Update the procedure with its embedding
                                await session.execute(
                                    text("""
                                        UPDATE drg_procedures 
                                        SET embedding = (:embedding)::vector 
                                        WHERE drg_code = :drg_code
                                    """),
                                    {
                                        "embedding": '[' + ','.join(map(str, embedding)) + ']',
                                        "drg_code": proc.drg_code
                                    }
                                )
                                processed += 1
                                
                                if processed % 10 == 0:
                                    logger.info(f"Processed {processed}/{len(procedures)} DRG embeddings...")
                            else:
                                logger.warning(f"Failed to generate embedding for DRG {proc.drg_code}")
                                
                        except Exception as e:
                            logger.error(f"Error processing DRG {proc.drg_code}: {e}")
                            continue
                    
                    # Commit batch
                    await session.commit()
                    
                    # Small delay to respect API rate limits
                    if i + batch_size < len(procedures):
                        await asyncio.sleep(1)

                logger.info(f"Successfully populated embeddings for {processed} DRG procedures")

                # Create vector index for DRG embeddings
                try:
                    await session.execute(
                        text("""
                            CREATE INDEX IF NOT EXISTS idx_drg_embedding
                            ON drg_procedures
                            USING ivfflat (embedding vector_cosine_ops)
                            WITH (lists = 100);
                        """)
                    )
                    await session.commit()
                    logger.info("Created vector index for DRG embeddings")
                except Exception as e:
                    logger.warning(f"Failed to create DRG vector index (may already exist): {e}")

            except Exception as exc:  # pragma: no cover
                await session.rollback()
                logger.error("DRG embedding population failed: %s", exc)
                raise

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

    async def clean_template_catalog(self) -> None:
        """Remove all templates and re-seed with only original templates"""
        logger.info("Cleaning template catalog - removing all existing templates...")
        await init_db()

        async with AsyncSessionLocal() as session:
            try:
                # Get count before cleanup
                result = await session.execute(text("SELECT COUNT(*) FROM template_catalog"))
                before_count = result.scalar()
                logger.info(f"Found {before_count} existing templates")
                
                # Delete all existing templates
                await session.execute(text("DELETE FROM template_catalog"))
                logger.info("Deleted all existing templates")
                
                # Re-seed with only original templates
                templates = self.get_initial_templates()
                
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
                logger.info("Re-inserted %d original templates", len(templates))

                # Recreate vector index
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
                logger.info("Vector similarity index recreated")

            except Exception as exc:
                await session.rollback()
                logger.error("Template cleanup failed: %s", exc)
                raise


# ─── Entrypoint --------------------------------------------------------------
async def main() -> None:
    import argparse
    
    parser = argparse.ArgumentParser(description="Seed template catalog and DRG embeddings")
    parser.add_argument(
        "--mode", 
        choices=["templates", "drg-embeddings", "both", "clean"], 
        default="both",
        help="What to populate: templates, drg-embeddings, both, or clean (default: both)"
    )
    
    args = parser.parse_args()
    seeder = TemplateSeeder()
    
    if args.mode == "clean":
        logger.info("Cleaning template catalog...")
        await seeder.clean_template_catalog()
    elif args.mode in ["templates", "both"]:
        logger.info("Seeding SQL templates...")
        await seeder.seed_templates()
    
    if args.mode in ["drg-embeddings", "both"]:
        logger.info("Populating DRG embeddings for semantic search...")
        await seeder.populate_drg_embeddings()
    
    logger.info("Operation complete!")


if __name__ == "__main__":
    asyncio.run(main())
