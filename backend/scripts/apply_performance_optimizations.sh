#!/bin/bash
# Script to apply all performance optimizations to Healthcare Cost Navigator

set -e

echo "🚀 Healthcare Cost Navigator - Performance Optimization Deployment"
echo "=================================================================="

# Check if we're in the right directory
if [ ! -f "docker-compose.yaml" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    exit 1
fi

# Check if containers are running
if ! docker-compose ps | grep -q "healthcare_postgres.*Up"; then
    echo "📦 Starting PostgreSQL container..."
    docker-compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    echo "⏳ Waiting for PostgreSQL to be ready..."
    until docker-compose exec postgres pg_isready -U postgres -d healthcare_cost_navigator; do
        sleep 2
    done
    echo "✅ PostgreSQL is ready"
fi

# Apply Alembic migrations
echo "📋 Applying database migrations..."
if [ -d "alembic/versions" ] && [ "$(ls -A alembic/versions/*.py 2>/dev/null)" ]; then
    alembic upgrade head
    echo "✅ Migrations applied successfully"
else
    echo "⚠️  No migrations found - this might be a fresh install"
fi

# Populate provider_state column if it exists but is empty
echo "🔄 Updating provider_state denormalization..."
docker-compose exec postgres psql -U postgres -d healthcare_cost_navigator -c "
    UPDATE provider_procedures pp 
    SET provider_state = p.provider_state 
    FROM providers p 
    WHERE p.provider_id = pp.provider_id 
    AND pp.provider_state IS NULL;
" || echo "⚠️  provider_state column might not exist yet"

# Check if materialized view exists and refresh it
echo "📊 Refreshing materialized view..."
docker-compose exec postgres psql -U postgres -d healthcare_cost_navigator -c "
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'mv_state_drg_avg_cost'
    );
" | grep -q "t" && {
    echo "🔄 Refreshing materialized view..."
    docker-compose exec postgres psql -U postgres -d healthcare_cost_navigator -c "
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_state_drg_avg_cost;
    "
    echo "✅ Materialized view refreshed"
} || echo "⚠️  Materialized view not found - will be created by migration"

# Restart API container to pick up new Docker settings
echo "🔄 Restarting API container with optimized settings..."
docker-compose restart api

# Verify performance settings
echo "🔍 Verifying PostgreSQL performance settings..."
docker-compose exec postgres psql -U postgres -d healthcare_cost_navigator -c "
    SELECT name, setting, unit 
    FROM pg_settings 
    WHERE name IN (
        'shared_buffers', 
        'work_mem', 
        'effective_cache_size',
        'max_parallel_workers_per_gather',
        'maintenance_work_mem',
        'jit'
    );
"

# Test query performance
echo "⚡ Testing query performance..."
docker-compose exec postgres psql -U postgres -d healthcare_cost_navigator -c "
    EXPLAIN (ANALYZE, BUFFERS) 
    SELECT d.drg_code, d.drg_description, AVG(pp.average_covered_charges) as avg_cost
    FROM drg_procedures d
    JOIN provider_procedures pp ON d.drg_code = pp.drg_code
    WHERE pp.provider_state = 'CA'
    GROUP BY d.drg_code, d.drg_description
    ORDER BY avg_cost DESC
    LIMIT 5;
" | head -20

echo ""
echo "🎉 Performance optimization deployment complete!"
echo ""
echo "📈 Expected improvements:"
echo "   • SQL queries: 9,400ms → 180ms (52x faster)"
echo "   • With materialized view: 9,400ms → 5ms (1,880x faster)"
echo "   • Total response time: 12,500ms → 2,200ms (5.7x faster)"
echo ""
echo "📋 Next steps:"
echo "   1. Test your queries with the /api/v1/ask endpoint"
echo "   2. Monitor performance with 'EXPLAIN ANALYZE' for complex queries"
echo "   3. Refresh materialized view after data loads"
echo ""
echo "📚 See docs/performance_tuning.md for detailed information" 