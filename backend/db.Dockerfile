# Custom PostgreSQL 16 with PostGIS + pgvector
FROM postgres:17

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      postgresql-17-postgis-3 postgresql-17-postgis-3-scripts \
      postgresql-17-pgvector \
 && rm -rf /var/lib/apt/lists/*

COPY etl/configure_postgres.sh /docker-entrypoint-initdb.d/99-configure-postgres.sh
RUN chmod +x /docker-entrypoint-initdb.d/99-configure-postgres.sh

ENV POSTGRES_DB=healthcare_cost_navigator
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=Warmia50587 