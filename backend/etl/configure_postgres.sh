#!/bin/bash
# Configure PostgreSQL performance settings from environment variables

# Apply configuration settings if they exist
if [ ! -z "$POSTGRES_SHARED_BUFFERS" ]; then
    echo "shared_buffers = $POSTGRES_SHARED_BUFFERS" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_WORK_MEM" ]; then
    echo "work_mem = $POSTGRES_WORK_MEM" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_EFFECTIVE_CACHE_SIZE" ]; then
    echo "effective_cache_size = $POSTGRES_EFFECTIVE_CACHE_SIZE" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER" ]; then
    echo "max_parallel_workers_per_gather = $POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_MAINTENANCE_WORK_MEM" ]; then
    echo "maintenance_work_mem = $POSTGRES_MAINTENANCE_WORK_MEM" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_JIT" ]; then
    echo "jit = $POSTGRES_JIT" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_RANDOM_PAGE_COST" ]; then
    echo "random_page_cost = $POSTGRES_RANDOM_PAGE_COST" >> /var/lib/postgresql/data/postgresql.conf
fi

if [ ! -z "$POSTGRES_EFFECTIVE_IO_CONCURRENCY" ]; then
    echo "effective_io_concurrency = $POSTGRES_EFFECTIVE_IO_CONCURRENCY" >> /var/lib/postgresql/data/postgresql.conf
fi

echo "PostgreSQL performance configuration applied" 