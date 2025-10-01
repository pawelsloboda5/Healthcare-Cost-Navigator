# SIE Wellness Integration Guide

Quick integration guide for connecting SIE Wellness AI Copilot to the Healthcare Cost Navigator public hospital data API.

## Endpoint

```
POST https://34-239-131-85.sslip.io/api/v1/query
```

**Dev:** `http://localhost:8000/api/v1/query`  
**Prod:** `https://34-239-131-85.sslip.io/api/v1/query`

## Request

```json
{
  "question": "What are the cheapest providers for knee replacement in California?",
  "limit": 10
}
```

## Response

```json
{
  "success": true,
  "data": [
    {
      "provider_name": "Memorial Hospital",
      "provider_state": "CA",
      "average_covered_charges": 45000.50,
      "drg_description": "Major Joint Replacement"
    }
  ],
  "sql": "SELECT...",
  "count": 10,
  "message": "Query executed successfully"
}
```

## OpenAI Tool Definition

For your AI chatbot using OpenAI Responses API with structured outputs and streaming:

```typescript
const tools = [{
  type: "function",
  function: {
    name: "query_public_hospital_data",
    description: "Query public Medicare hospital cost data across all US states. Returns actual provider names, costs, locations, and ratings. Use this to answer questions about hospital costs, cheapest providers, procedure pricing comparisons, and provider quality ratings.",
    parameters: {
      type: "object",
      properties: {
        question: {
          type: "string",
          description: "Natural language question about hospital costs or providers. Examples: 'cheapest hospitals for heart surgery in Texas', 'highest rated providers for knee replacement in Florida', 'compare hip replacement costs between NY and CA'"
        },
        limit: {
          type: "integer",
          description: "Max results to return (default: 10, max: 100)",
          default: 10
        }
      },
      required: ["question"]
    }
  }
}];
```

## Implementation

```typescript
// lib/hospitalDataApi.ts
const API_URL = process.env.NEXT_PUBLIC_HOSPITAL_API_URL || 
  (process.env.NODE_ENV === 'production' 
    ? 'https://34-239-131-85.sslip.io/api/v1/query'
    : 'http://localhost:8000/api/v1/query');

export async function queryHospitalData(question: string, limit = 10) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, limit })
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
```

## Chatbot Integration

```typescript
// app/api/chat/route.ts or your existing chat handler
import OpenAI from 'openai';
import { queryHospitalData } from '@/lib/hospitalDataApi';

const openai = new OpenAI();

export async function POST(req: Request) {
  const { messages } = await req.json();

  // First call - get tool calls
  const response = await openai.chat.completions.create({
    model: 'gpt-4.1',
    messages: messages,
    tools: tools,
    stream: false  // Get tool calls first, then stream final response
  });

  const toolCall = response.choices[0].message.tool_calls?.[0];

  if (toolCall?.function.name === 'query_public_hospital_data') {
    const args = JSON.parse(toolCall.function.arguments);
    
    // Call your hospital API
    const hospitalData = await queryHospitalData(args.question, args.limit);
    
    // Add tool result to messages
    messages.push(response.choices[0].message);
    messages.push({
      role: 'tool',
      tool_call_id: toolCall.id,
      content: JSON.stringify({
        success: hospitalData.success,
        count: hospitalData.count,
        data: hospitalData.data
      })
    });

    // Stream final response
    const stream = await openai.chat.completions.create({
      model: 'gpt-4.1',
      messages: messages,
      stream: true
    });

    return new Response(stream.toReadableStream());
  }

  // No tool calls - regular streaming response
  const stream = await openai.chat.completions.create({
    model: 'gpt-4.1',
    messages: messages,
    stream: true
  });

  return new Response(stream.toReadableStream());
}
```

## Structured Outputs Version

If using structured outputs for consistent formatting:

```typescript
const responseFormat = {
  type: "json_schema",
  json_schema: {
    name: "hospital_results",
    strict: true,
    schema: {
      type: "object",
      properties: {
        summary: { type: "string" },
        providers: {
          type: "array",
          items: {
            type: "object",
            properties: {
              name: { type: "string" },
              location: { type: "string" },
              cost: { type: "number" },
              recommendation: { type: "string" }
            },
            required: ["name", "location", "cost", "recommendation"]
          }
        }
      },
      required: ["summary", "providers"]
    }
  }
};

const finalResponse = await openai.chat.completions.create({
  model: 'gpt-4.1',
  messages: messages,
  response_format: responseFormat,
  stream: true
});
```

## Environment Variables

```bash
# .env.local (dev)
NEXT_PUBLIC_HOSPITAL_API_URL=http://localhost:8000/api/v1/query

# .env.production
NEXT_PUBLIC_HOSPITAL_API_URL=https://34-239-131-85.sslip.io/api/v1/query
```

## Alternative: Use Existing `/ask` Endpoint

You can also use the existing `/ask` endpoint with `explain=false`:

```typescript
// Same functionality, different response structure
const API_URL = 'https://34-239-131-85.sslip.io/api/v1/ask?explain=false';

const response = await fetch(API_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    question: question,
    use_template_matching: true
  })
});

// Response structure:
// { success, answer: "", sql_query, results, template_used, confidence_score, execution_time_ms }
```

**Difference:**
- `/query` - Cleaner response: `{ success, data, sql, count, message }`
- `/ask?explain=false` - Original response: `{ success, answer: "", sql_query, results, ... }`

Both work perfectly! Use whichever fits your existing code better.

## AWS EC2 Deployment Notes

### CORS Already Configured
- ✅ `http://localhost:3001` (dev)
- ✅ `https://www.sie2.com` (prod)

### No Authentication Required
Public Medicare data - no API key needed.

### API Capabilities

**Works for:**
- Cost comparisons by state/city
- Procedure searches (by name or DRG code)
- Provider quality ratings
- Multi-state cost comparisons
- Geographic filtering

**Data includes:**
- Provider names, locations
- Average costs (covered charges, total payments, Medicare payments)
- Procedure codes and descriptions
- Quality/safety ratings
- Discharge volumes

**Example queries your copilot can handle:**
```
"What are the cheapest providers for heart surgery in California?"
"Compare knee replacement costs between Texas and Florida"
"Show me the highest rated hospitals for hip replacement"
"Find affordable providers for diabetes care in New York"
"What hospitals in Virginia have the best safety ratings?"
```

## Testing

```bash
# Test from command line
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the 5 cheapest providers for heart surgery in Texas?",
    "limit": 5
  }'

# Test from your Next.js app
# Just run both servers and your chatbot will have access
```

## Performance

- **Template matching:** ~200-500ms (most queries)
- **RAG fallback:** ~1-3s (complex/novel queries)  
- **Rate limiting:** None currently - add if needed

## System Prompt Suggestion

Add to your SIE Copilot system prompt:

```
You have access to a tool that queries public Medicare hospital cost data covering all 
US states. Use it when users ask about hospital costs, procedure pricing, provider 
comparisons, or healthcare affordability. The data includes actual provider names, 
precise costs, locations, and quality ratings.

When presenting hospital cost data:
- Show actual provider names and specific prices
- Highlight the cheapest options
- Mention location and contact info if available
- Note that these are Medicare rates (actual costs may vary)
- Suggest calling providers to confirm current pricing
```

## Support

Questions? Issues? Check API docs at:
- Dev: `http://localhost:8000/docs`
- Prod: `https://34-239-131-85.sslip.io/docs`

