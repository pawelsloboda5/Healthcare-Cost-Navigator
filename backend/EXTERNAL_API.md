# External API Access

## Quick Reference

The `/api/v1/query` endpoint provides access to Medicare hospital cost data for external applications.

### Endpoint
```
POST /api/v1/query
```

**Production:** `https://34-239-131-85.sslip.io/api/v1/query`  
**Alternative:** `https://34-239-131-85.sslip.io/api/v1/ask?explain=false`

### Request
```json
{
  "question": "What are the cheapest providers for heart surgery in California?",
  "limit": 10
}
```

### Response
```json
{
  "success": true,
  "data": [{"provider_name": "...", "average_covered_charges": 45000}],
  "sql": "SELECT...",
  "count": 10,
  "message": "Query executed successfully"
}
```

### CORS Configuration
- `http://localhost:3001` (SIE Wellness dev)
- `https://www.sie2.com` (SIE Wellness prod)

### Authentication
None required - public Medicare data.

### Integration Guide
See `docs/SIE_Integration.md` for complete OpenAI tool integration examples.

### Features
- Natural language to SQL conversion
- Template matching for fast responses (~200-500ms)
- RAG fallback for complex queries
- Safety validation (read-only)
- Full data table results

### Data Coverage
- 100,000+ Medicare providers
- All US states
- Cost, quality, and volume data
- Current as of latest CMS data release

