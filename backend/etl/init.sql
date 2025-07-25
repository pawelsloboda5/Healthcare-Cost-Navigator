/****************************************************************************************
  Healthcare Cost Navigator – Database Bootstrap
  ------------------------------------------------------------------
  • Creates all tables defined in backend/app/models/models.py
  • Enables PostGIS, pg_trgm, and pgvector extensions
  • Adds the indexes declared in the SQLAlchemy models
  • Pre-creates an optional template_catalog table for future vector search
****************************************************************************************/

-- -----------------------------------------------------------------
-- EXTENSIONS (enable once per database)
-- -----------------------------------------------------------------
-- Install extensions
CREATE EXTENSION IF NOT EXISTS postgis;      -- Add PostGIS manually
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram text search  
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector (should work now)

-- -----------------------------------------------------------------
-- TABLE: providers
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS providers (
    provider_id            VARCHAR(10)  PRIMARY KEY,
    provider_name          VARCHAR(200) NOT NULL,
    provider_city          VARCHAR(100) NOT NULL,
    provider_state         CHAR(2)      NOT NULL,
    provider_zip_code      VARCHAR(10)  NOT NULL,
    provider_address       VARCHAR(500),
    provider_state_fips    CHAR(2),
    provider_ruca          VARCHAR(10),
    provider_ruca_description TEXT,
    location               GEOMETRY(Point, 4326)  -- lon / lat
);

-- Indexes on providers
CREATE INDEX IF NOT EXISTS idx_provider_zip      ON providers(provider_zip_code);
CREATE INDEX IF NOT EXISTS idx_provider_state    ON providers(provider_state);
CREATE INDEX IF NOT EXISTS idx_provider_location ON providers USING GIST (location);

-- -----------------------------------------------------------------
-- TABLE: drg_procedures
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drg_procedures (
    drg_code        VARCHAR(10) PRIMARY KEY,
    drg_description TEXT        NOT NULL
);

-- Full-text trigram index on description
CREATE INDEX IF NOT EXISTS idx_drg_description
    ON drg_procedures
    USING GIN (drg_description gin_trgm_ops);

-- -----------------------------------------------------------------
-- TABLE: provider_procedures  (cost & volume per provider/DRG)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provider_procedures (
    id                        SERIAL       PRIMARY KEY,
    provider_id               VARCHAR(10)  NOT NULL,
    drg_code                  VARCHAR(10)  NOT NULL,
    total_discharges          INTEGER      NOT NULL,
    average_covered_charges   NUMERIC(12,2) NOT NULL,
    average_total_payments    NUMERIC(12,2) NOT NULL,
    average_medicare_payments NUMERIC(12,2) NOT NULL,
    CONSTRAINT fk_pp_provider FOREIGN KEY (provider_id)
        REFERENCES providers(provider_id),
    CONSTRAINT fk_pp_drg      FOREIGN KEY (drg_code)
        REFERENCES drg_procedures(drg_code)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_provider_drg
    ON provider_procedures(provider_id, drg_code);

CREATE INDEX IF NOT EXISTS idx_avg_covered_charges
    ON provider_procedures(average_covered_charges);

CREATE INDEX IF NOT EXISTS idx_pp_drg_code
    ON provider_procedures(drg_code);

-- PERFORMANCE OPTIMIZATIONS --
-- Composite covering index for optimal query performance (matches alembic migration)
CREATE INDEX IF NOT EXISTS idx_pp_state_drg_cost_inc
    ON provider_procedures (drg_code, provider_id)
    INCLUDE (average_covered_charges);

-- Add provider_state column for denormalization (will be populated by ETL)
ALTER TABLE provider_procedures 
ADD COLUMN IF NOT EXISTS provider_state CHAR(2);

-- Index on provider_state for direct filtering
CREATE INDEX IF NOT EXISTS idx_pp_provider_state 
    ON provider_procedures(provider_state);

-- Create trigger function to keep provider_state in sync
CREATE OR REPLACE FUNCTION trg_sync_provider_state() RETURNS trigger AS $$
BEGIN
    NEW.provider_state := (
        SELECT provider_state 
        FROM providers 
        WHERE provider_id = NEW.provider_id
    );
    RETURN NEW;
END $$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS provider_state_sync_trigger ON provider_procedures;
CREATE TRIGGER provider_state_sync_trigger
    BEFORE INSERT OR UPDATE OF provider_id
    ON provider_procedures
    FOR EACH ROW EXECUTE FUNCTION trg_sync_provider_state();

-- -----------------------------------------------------------------
-- TABLE: provider_ratings  (mock or real CMS ratings)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provider_ratings (
    id                         SERIAL PRIMARY KEY,
    provider_id                VARCHAR(10) NOT NULL,
    overall_rating             NUMERIC(3,1) NOT NULL,
    quality_rating             NUMERIC(3,1),
    safety_rating              NUMERIC(3,1),
    patient_experience_rating  NUMERIC(3,1),
    CONSTRAINT fk_rating_provider FOREIGN KEY (provider_id)
        REFERENCES providers(provider_id)
);

CREATE INDEX IF NOT EXISTS idx_provider_rating
    ON provider_ratings(provider_id);

CREATE INDEX IF NOT EXISTS idx_overall_rating
    ON provider_ratings(overall_rating);

-- -----------------------------------------------------------------
-- TABLE: csv_column_mappings  (ETL data dictionary)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS csv_column_mappings (
    id                     SERIAL       PRIMARY KEY,
    csv_column_name        VARCHAR(100) NOT NULL UNIQUE,
    normalized_field_name  VARCHAR(100) NOT NULL,
    table_name             VARCHAR(50)  NOT NULL,
    data_type              VARCHAR(50),
    description            TEXT
);

CREATE INDEX IF NOT EXISTS idx_csv_column
    ON csv_column_mappings(csv_column_name);

CREATE INDEX IF NOT EXISTS idx_normalized_field
    ON csv_column_mappings(normalized_field_name);

-- -----------------------------------------------------------------
-- OPTIONAL: template_catalog (SQL-template embeddings w/ pgvector)
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS template_catalog (
    template_id    SERIAL PRIMARY KEY,
    canonical_sql  TEXT           NOT NULL,
    raw_sql        TEXT           NOT NULL,
    embedding      VECTOR(1536),          -- pgvector column
    comment        TEXT,
    created_at     TIMESTAMP      DEFAULT NOW(),
    updated_at     TIMESTAMP      DEFAULT NOW()
);

-- Uncomment after first data load to build ANN index
-- CREATE INDEX idx_template_embedding
--     ON template_catalog
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

-- -----------------------------------------------------------------
-- MATERIALIZED VIEW: Pre-aggregated state costs (performance optimization)
-- -----------------------------------------------------------------
-- Note: This will be created by alembic migration after data is loaded
-- Uncomment after data load for fresh installs:
/*
CREATE MATERIALIZED VIEW mv_state_drg_avg_cost AS
SELECT 
    pp.provider_state,
    d.drg_code,
    d.drg_description,
    AVG(pp.average_covered_charges) AS avg_cost,
    COUNT(*) AS provider_count,
    MIN(pp.average_covered_charges) AS min_cost,
    MAX(pp.average_covered_charges) AS max_cost
FROM provider_procedures pp
JOIN drg_procedures d ON pp.drg_code = d.drg_code
WHERE pp.provider_state IS NOT NULL
GROUP BY pp.provider_state, d.drg_code, d.drg_description;

CREATE UNIQUE INDEX mv_state_drg_pk
ON mv_state_drg_avg_cost (provider_state, drg_code);

CREATE INDEX mv_state_drg_cost_desc
ON mv_state_drg_avg_cost (provider_state, avg_cost DESC);
*/

-- -----------------------------------------------------------------
-- Done
-- -----------------------------------------------------------------
