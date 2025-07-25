# OpenAI Responses API for Streaming and RAG

# Integration

## Overview of GPT-4.1 Models and the Responses API

OpenAI’s _Responses API_ is a new unified interface for generating model outputs (replacing older completion/
chat endpoints). It supports the latest GPT-4.1 series models and features built-in tools and function calling
for advanced use cases. Notably, the GPT-4.1 family comes in multiple sizes: **GPT-4.1** , **GPT-4.1 Mini** ,
and **GPT-4.1 Nano**. These models offer major improvements in coding, instruction-following, and support
extremely large context windows (up to **1 million tokens** of context).

GPT-4.1 Mini is a smaller, faster version that **matches or exceeds** the original GPT-4 in many benchmarks
while **reducing latency by nearly half and cost by 83%**. In practice, you might use GPT-4.1 for the best
quality, and GPT-4.1 Mini when you need faster responses or lower cost. All GPT-4.1 models have an
updated knowledge cutoff (June 2024) , making them more aware of recent information.

The Responses API itself is _stateful_ , meaning it can manage conversation history server-side if desired (via a
previous_response_id parameter). It blends the capabilities of Chat Completions with new features in
one interface. In short, the Responses API simplifies how you call models by allowing flexible input
formats (single prompt strings or structured messages), and returns a rich Response object that includes
the final text as well as any tool usage or function call data.

**Key features of the Responses API:**

```
Unified Prompt Format: You can provide a simple prompt string or a list of messages with roles
(system/developer/user) as input. For quick tasks, a single input string is sufficient (no need to
wrap it in a messages list).
Direct Output Text: The result text is easily accessible via response.output_text (no more
digging through choices[0].message.content).
Stateful Conversations: By default, the API can store conversation state so you can ask follow-up
questions without resending full history. Pass previous_response_id in a new request to
continue from a prior response’s context.
Tools and Function Calling: You can supply tools (including custom functions or built-in operations
like web search or file lookup) that the model can invoke to fetch information. This can be used
to implement actions or Retrieval-Augmented Generation seamlessly (more on this later).
Large Context & Structured Output: With the huge context window of GPT-4.1, you can include
extensive background text. The API also supports function calling and JSON schema outputs for
structured data, using parameters like tools or response_model to parse output into objects.
```
```

6 7
```
- 7 • 8 • 2 •


## Basic Usage of the Responses API

Using the Responses API in code is straightforward. In Python, you’ll typically initialize an OpenAI client and
call client.responses.create() with the desired parameters. For example:

```
fromopenai importOpenAI
client = OpenAI(api_key="YOUR_API_KEY") # Initialize client with your API key
```
```
response= client.responses.create(
model="gpt-4.1",
input="Tell me a three sentence bedtime story about a unicorn."
)
print(response.output_text)
```
This will send the prompt to the GPT-4.1 model and print the resulting story. Under the hood, the OpenAI
Python SDK handles making a request to the POST /v1/responses endpoint. The Responses API **unifies
text and image inputs** and can produce text or JSON outputs depending on instructions , but in this
simple case it just returns the story text.

**Differences from older APIs:** If you’ve used the older Chat Completion API, note that here we didn’t need
to wrap the prompt in a messages list – a plain string was accepted. The returned response object has
properties like response.output_text for the full text, and response.output which contains a list of
message objects (useful if the model function-called or produced multiple messages). The Responses API is
designed to be more convenient: for example, the above code directly gives the story via output_text
instead of requiring response.choices[0].message.content indexing.

You can also provide a structured message history or additional instructions. For instance, you might
separate system instructions from user input:

```
response= client.responses.create(
model="gpt-4.1-mini",
instructions="You are a friendly assistant.",
input="How do I install Docker on Ubuntu?"
)
print(response.output_text)
```
Here, instructions act like a system prompt (high-level guidance), while input contains the user’s
query. You can even mix roles in input if needed, e.g. provide a list of message dicts with roles "system",
"developer", "user" to fine-tune behavior. The GPT-4.1 models also support the developer role
which can override system instructions if used (for instance, a "developer" role message can tell the model
not to follow the system instruction). This hierarchy can be useful for controlling responses.

```


## Streaming Responses in Real-Time

One of the **critical features** for our project is streaming, since we want partial responses to appear quickly.
The OpenAI Responses API supports streaming results as they are generated. To use streaming, you set
stream=True in the request. Instead of waiting for the entire answer, the API will return a stream
(iterator) of events/tokens.

When streaming is enabled, the server uses **Server-Sent Events (SSE)** to push data incrementally. In
practice, the OpenAI SDK abstracts this so that you can iterate over the response object in Python or await
new chunks in JavaScript. According to the documentation, _“when you create a Response with stream set to
true, the server will emit server-sent events to the client as the Response is generated.”_. This means you can
start processing or displaying the answer token-by-token, reducing perceived latency for the end user.

**Python streaming example:** (from the OpenAI SDK usage)

```
stream = client.responses.create(
model="gpt-4.1",
input="Say 'double bubble bath' ten times fast.",
stream=True
)
forevent instream:
# Each event may contain a partial piece of the output
if hasattr(event, "type") and"text.delta" inevent.type:
print(event.delta, end="", flush=True) # print partial text
```
In this example, as each chunk of text (event.delta) arrives, we print it out immediately. The
condition if "text.delta" in event.type filters to only text-producing events. By the end of the
loop, the entire response will have been printed in real-time. (The SDK represents different event types, but
for basic text output we focus on the "text.delta" events which carry the streaming content.)

**Integrating streaming with a web interface:** Since our front-end is a raw JavaScript app, we need a way to
send these streamed tokens from the back-end to the browser. OpenAI’s API itself uses SSE over HTTP;
however, browsers can consume SSE or WebSocket messages to receive streaming data. Two common
approaches are:

```
HTTP SSE to the browser: You can implement an API endpoint on your server that proxies the
OpenAI stream to the client. For example, using a framework like FastAPI or Express, have an
endpoint that sets Content-Type: text/event-stream and writes events as they come from
OpenAI. The browser JavaScript can open an EventSource to this endpoint and append incoming
text to the UI. This leverages SSE natively (no extra libraries needed on client side).
WebSocket streaming: Alternatively, you can use a WebSocket. When the user submits a question,
open a WebSocket connection (or reuse an existing one) to your server. The server will start the
OpenAI streaming call, and as each chunk arrives, send it over the WebSocket to the client. The client
listens for messages on the socket and updates the UI progressively. WebSockets are bi-directional,
which isn’t strictly necessary for one-way streaming, but they work well for interactive apps and are
```



```
widely supported. In our case, using WebSockets is perfectly fine and is a common choice for real-
time token streams.
```
**Which to choose?** Both methods can achieve our goal of real-time updates. SSE is slightly simpler if you
only need one-way communication (server -> client updates), and it automatically handles reconnection and
order of events. WebSockets give you more flexibility (e.g., the client could also send cancellation signals or
other messages mid-stream). Given the question “Just WebSockets or what works best?”, using WebSockets
is a robust solution for our use case. We can proceed with a WebSocket-based design for clarity, since it
integrates well with a custom JS frontend. The key is that the back-end will capture the stream from
client.responses.create(..., stream=True) and forward each chunk to the front-end promptly.

## Retrieval-Augmented Generation (RAG) with Postgres Vector DB

Our project also needs to incorporate **Retrieval-Augmented Generation (RAG)**. RAG is a technique to
improve the model’s answers by providing **external context** at runtime. In other words, rather than
relying solely on the model’s built-in knowledge, we **retrieve relevant data** (e.g. from our documents or
database) and include it in the prompt so the model can generate a more informed response. This is
especially valuable for domain-specific queries or up-to-date information that the model might not know by
itself.

In our case, the external data is stored in a Postgres database (with a vector index, likely using the pgvector
extension) running on Docker. We have presumably pre-processed and embedded our knowledge base into
this DB. Here’s how a RAG pipeline works, simplified:

_Basic RAG workflow:_ The user’s query triggers the LLM to retrieve relevant context from a data source (our
Postgres vector DB) before answering. The LLM consumes the prompt **plus** the retrieved context to
generate its final response.

The RAG implementation for our project involves a few steps:

```
Question Embedding: First, take the user’s query and convert it into an embedding (a high-
dimensional numeric vector). This can be done with OpenAI’s embedding models (e.g., text-embedding-3-small)  The embedding represents the semantic
meaning of the question.
```

Vector Search in Postgres: Using the query embedding, perform a similarity search in the Postgres
database to find the most relevant pieces of information. Our database likely contains embeddings
of documents or text chunks (with pgvector, we can do efficient nearest-neighbor search). This is the
semantic search step: it finds content that is conceptually related to the query, not just keyword
matches. The result is a set of top-ranked text chunks (e.g. relevant paragraphs from our
docs).
```
```
Retrieve Context: Fetch the actual text of those top chunks from the database. For example, we
might retrieve the top 3 passages that best match the query.
```
```
Compose the Prompt with Context: Now, we build the prompt for the model by combining the
retrieved context with the user’s question. There are a few ways to do this:
```
```
Prepend a system instruction like “Use the following information to answer the question. Info: {{retrieved
text}}. Question: {{user question}}”.
Or include the context as part of the user message (e.g. User: "Question ... [with some context
provided]" ). The exact format can be tuned, but the goal is to supply those retrieved facts to the
model. Since GPT-4.1 supports a huge context window, we can include fairly large text chunks if
needed. However, it’s still wise to keep only the most relevant info to avoid diluting the
prompt.
```
```
Example prompt construction: If a user asks "How does our product’s pricing model work?", and
we retrieved a relevant FAQ paragraph about pricing, we might formulate:
```
```
Context: Our product uses a tiered subscription pricing... (details)
User question: How does our product’s pricing model work?
```
```
Then send this as the input to the Responses API call.
```
```
Generate Answer with the Model: Finally, call the OpenAI Responses API with the composed
prompt (which now includes the external context). The model will take the context into account and
produce a more accurate answer. This is the augmented generation part of RAG. We will likely do
this call with stream=True to get the answer streaming back.
```
```
Return/Stream the Answer: As the model’s answer comes in, stream it to the user through the
WebSocket, as discussed earlier.
```
All of these steps should be done efficiently. **“Fast async RAG”** means we want minimal latency overhead
from the retrieval process. Some tips to achieve this: - Perform the embedding and database query quickly.
Ensure the embedding model call (if using OpenAI for embeddings) is fast or possibly cached. Using a
smaller embedding model or caching past queries can help. - Use asynchronous calls where possible. For
example, if our backend is Python, we might use asyncio to concurrently handle the database I/O and
the API call. The OpenAI Python SDK does not natively provide an async method for
responses.create, but you can run it in a thread executor or use an async-compatible HTTP client
under the hood. If using Node.js, the OpenAI Node SDK (or direct HTTP fetch) is naturally async with
await. - If multiple pieces of context need to be fetched from the database, perform those fetches in



parallel. In our case, a single vector search can return the top N chunks in one SQL query, so that’s usually
fast. If you then needed to, say, make additional OpenAI calls (for example, summarizing each chunk), you
could parallelize those – but in our architecture we likely avoid that complexity and directly feed the chunks
to the final prompt. - Stream the output so the user sees the answer as soon as possible, even while later
parts of the answer are still being generated. This dramatically improves perceived speed, since the user
can start reading the answer after, say, 1-2 seconds instead of waiting for a 10-second full completion.

It’s worth noting that OpenAI’s platform also supports a form of RAG via **built-in tools** or by uploading
documents to be searched. For example, the Responses API can use a "file_search" tool to let the
model pull info from files you’ve uploaded, or a "web_search_preview" tool to search the web.
However, in our setup, since we have a Postgres knowledge base, we are implementing the retrieval
ourselves. This gives us control over our data (and likely we can achieve lower latency by querying our
database directly, rather than relying on the model to use a tool to fetch data).

## System Architecture and Implementation Details

Bringing it all together, here’s how we can architect the system with clear components and function
responsibilities:

```
Front-End (Browser/JS): This will handle user interactions and display results. The front-end should
collect the user’s query (e.g., from a text input) and send it to the backend. Since we want streaming,
the front-end can open a WebSocket connection to the backend. For example, when the user hits
"Ask", we initiate a WebSocket connection (or send a message on an existing socket) containing the
query. The front-end code listens for incoming messages on that socket to update the answer text in
real time. The interface will concatenate tokens as they arrive and render them. We might also show
a loading indicator that clears when the stream is done.
```
```
Back-End (Server): The backend can be a Python service (Flask/FastAPI, etc.) using the OpenAI
Python SDK, or a Node.js service using OpenAI’s Node SDK – the approach is similar. Let’s outline a
Python-based approach:
```
```
WebSocket Handler: When a WebSocket connection from the client is established and a message
(query) is received, the backend should handle it (e.g., in an async function if using something like
websockets library or FastAPI’s WebSocket endpoint). We’ll parse the user’s question from the
message.
```
```
Retrieve Context: Call a helper function, say retrieve_relevant_context(question), that
implements the RAG steps discussed. This function might:
```
```
Generate an embedding for question (using OpenAI’s embedding API or another method).
Execute a SQL query on Postgres (with a vector similarity search) to get top relevant chunks.
Return those chunks of text (perhaps concatenated or as a structured list). Ensure this
function is efficient. If using Python, an asynchronous Postgres client (like asyncpg) could
allow this to run without blocking other requests. For now, assume it returns quickly with the
needed text.
```
### 2 • • • • ◦ ◦ ◦


```
Compose Prompt: Formulate the final prompt to send to the model. This could be done inside the
retrieval function or separately. For clarity, you might have another function
build_prompt(question, context_chunks) that inserts the retrieved context_chunks into
a template along with the question. This returns a string or message list to use as input for the
model.
```
```
Example: prompt = f"Use the following information to answer the question.
\n\n{context_chunks}\n\nQuestion: {question}"
```
```
Call OpenAI API (Streaming): Invoke the OpenAI client to get a streaming response:
```
```
stream = client.responses.create(
model="gpt-4.1",
input=prompt,
stream=True
)
```
```
Iterate over the stream as shown earlier, and for each text chunk event, immediately forward it to
the client via the WebSocket. For example:
```
```
forevent instream:
if hasattr(event, "type") and"text.delta" inevent.type:
websocket.send(event.delta) # pseudo-code to send chunk to
frontend
```
```
This will ensure the browser starts receiving event.delta strings (partial answer) in real time.
```
```
Finalize/Cleanup: After the loop finishes (which means the answer is complete), you can send a
special message or flag to the front-end to indicate the end of stream (or you might close the
WebSocket if it’s one-off). In many cases, the client can infer the end of answer when the WebSocket
is closed or no new chunks arrive for a while. If using a persistent connection, perhaps send a
designated end-of-answer message.
```
Throughout these steps, make sure to handle exceptions: e.g., the OpenAI API might error out or the DB
might fail to return results. You’d want to catch exceptions and send an error message to the client if so
(maybe as a final message or a separate channel).

```
Function and Variable Naming: Clarity is crucial. Use descriptive names that indicate each
function’s purpose:
openai_client for your OpenAI() client instance.
retrieve_relevant_context(query) for the retrieval logic.
build_prompt(question, context) for prompt assembly.
stream_response(prompt) or generate_response_stream(prompt) for the function
that calls OpenAI and streams the result.
```
### • • • • ◦ ◦ ◦ ◦


```
In the code loop, variables like event or chunk for the streaming events are fine. If using
asyncio, you might name coroutine functions with an async prefix or verb phrase (e.g.,
async handle_client(ws)).
On the front-end, if applicable, use clear event names for your WebSocket messages (if you
need to distinguish different message types, e.g., you might send JSON like {"type":
"token", "data": "..."}").
Keep the architecture concise: each function should have a single responsibility (separation of
concerns makes it easier to maintain and test).
```
**Concise Architecture Summary:**

```
Client-side: captures user input; opens WebSocket connection.
Server-side: on query received -> calls retrieve_relevant_context -> gets context from
Postgres.
Server: builds prompt with the context and question.
Server: calls client.responses.create(..., stream=True) with prompt, model choice
(gpt-4.1 or gpt-4.1-mini depending on trade-off).
Server: streams out tokens via WebSocket to client as they arrive.
Client: appends tokens to display; once done, the answer is fully shown.
```
This approach ensures the heavy lifting (embedding search and AI completion) happens server-side
(keeping our API key secure and leveraging Python tools), while the user interface gets a responsive,
streaming experience. Using **WebSockets** here is effective for pushing data to the browser in real-time,
aligning with the “just WebSockets” suggestion. OpenAI’s Responses API streaming (over SSE) is translated
into our app’s own streaming over WebSocket – achieving the best of both worlds: rapid, token-level
updates and a user-friendly interface.

## Final Considerations

```
Model selection: Decide when to use gpt-4.1 vs gpt-4.1-mini. For most queries where
quality is paramount and latency is acceptable, gpt-4.1 is ideal. If you need faster responses or
are handling many requests concurrently, gpt-4.1-mini can give a big speedup with slightly
lower cost. You could even let the user or system choose the model based on question
complexity or required speed.
Cost and tokens: Keep an eye on the context length. GPT-4.1 can handle massive prompts, but
embedding very large documents might be unnecessary if a shorter snippet answers the question.
Also, more tokens in prompt = higher cost and latency. Aim to retrieve the smallest relevant context
(maybe by chunking docs into paragraphs).
Asynchronous processing: If using Python and expecting high throughput, consider an async
framework (like FastAPI with async endpoints) and perhaps the async support of your DB client.
While the OpenAI SDK call itself might be blocking, you can offload it to a thread pool so other
requests aren’t stalled. Node.js backends inherently handle I/O asynchronously, which is a plus for
scaling.
Testing and iteration: Ensure to test with various queries to see that the RAG pipeline brings in the
correct context and that the model uses it. If the model sometimes ignores the provided context, you
might need to adjust the prompt format (e.g., emphasize “Using the above context, answer the
```



```
question...”). The good news is that GPT-4.1 models are quite capable of handling long context and
following instructions to use that context.
```
By following this design, we leverage the OpenAI **Responses API** to its fullest: streaming answers for a
great UX, and **Retrieval-Augmented Generation** with our Postgres knowledge base for accurate, up-to-
date information in responses. This documentation should serve as a guide for an AI engineer to
implement the solution, with clear function breakdown and best practices for naming and architecture.
With these pieces in place, our project will benefit from faster, informed AI responses that feel interactive
and reliable.

**Sources:**

```
OpenAI, Introducing GPT-4.1 in the API (model capabilities and context)
OpenAI API Reference (Responses API streaming and usage)
OpenAI Help Center, Retrieval Augmented Generation (RAG) and Semantic Search (concept and
workflow)
OpenAI Responses API Guides (example usage and features)
```
Azure OpenAI Responses API - Azure OpenAI | Microsoft Learn
https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses

openai-php/client - Packagist
https://packagist.org/packages/openai-php/client

Introducing GPT-4.1 in the API | OpenAI
https://openai.com/index/gpt-4-1/

OpenAI Responses API: A Comprehensive Guide | by Tom Odhiambo | Medium
https://medium.com/@odhitom09/openai-responses-api-a-comprehensive-guide-ad546132b2ed

Retrieval Augmented Generation (RAG) and Semantic Search for GPTs |
OpenAI Help Center
https://help.openai.com/en/articles/8868588-retrieval-augmented-generation-rag-and-semantic-search-for-gpts


