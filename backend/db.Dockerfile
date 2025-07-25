# Custom PostgreSQL image with PostGIS and pgvector
FROM postgres:17

# Install PostGIS and pgvector extensions
RUN apt-get update \
 && apt-get install -y postgresql-17-postgis-3 postgresql-17-postgis-3-scripts \
                       postgresql-17-pgvector --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# Copy performance configuration script
COPY etl/configure_postgres.sh /docker-entrypoint-initdb.d/99-configure-postgres.sh
RUN chmod +x /docker-entrypoint-initdb.d/99-configure-postgres.sh

# Set default database settings
ENV POSTGRES_DB=healthcare_cost_navigator
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=Warmia50587 