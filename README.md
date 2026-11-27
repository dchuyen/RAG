# RAG API

A FastAPI starter project for a RAG workflow. The repository currently contains the
service layer and early app wiring, but it is still in a partial/transition state:
router modules are not yet fully populated to match every feature described below,
so the project should be treated as a work-in-progress rather than a fully finished
API.

Note: this snapshot is intentionally a service-first scaffold. The app starts with
the `/chat` and `/semantic-search` routes; the other service endpoints are not yet
wired in `app/main.py`.

## Run locally

```bash
python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.15.0+cpu"
python -m pip install --no-cache-dir -r requirements.txt
python -m uvicorn app.main:app --reload
```
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Open <http://127.0.0.1:8000/docs> for the interactive API documentation.
Semantic search hiện không tạo embedding hoặc lưu chunk vào ChromaDB. Kết quả
được xếp hạng sơ bộ bằng BM25 và độ gần của ngày, sau đó được cross-encoder
xếp hạng lại với ưu tiên cho ngày gần hơn. Model cross-encoder chỉ được nạp khi
có yêu cầu xếp hạng. Các endpoint embedding riêng vẫn hoạt động và chỉ nạp model
khi được gọi.

## ChromaDB vector storage

`app.services.chroma` provides `store_documents()` and `query_documents()` for
persisting document chunks and retrieving the most similar ones. ChromaDB uses
the existing embedding model and stores its local database under `data/chroma/`
by default. Set `CHROMA_DB_PATH` to change the storage directory and
`CHROMA_COLLECTION_NAME` to change the collection name.
Set `CHROMA_QUERY_CACHE_COLLECTION_NAME` to change the dedicated semantic
query-cache collection name.

ChromaDB storage and query helpers remain available in `app.services.chroma`,
but the current semantic-search flow does not generate embeddings, read from
ChromaDB, or store chunks there.

Inspect stored records from the project root:

```bash
python test/console_chroma.py --limit 10
```

Use `--offset` to page through larger collections, for example
`python test/console_chroma.py --limit 10 --offset 10`.

## Open the chat interface

Configure `GEMINI_API_KEY`, `GROQ_API_KEY`, and `SERPAPI_API_KEY` in `.env`,
start the API with `python -m uvicorn app.main:app --reload`, then open
<http://127.0.0.1:8000/chat> in your browser.

If the chat reports `HTTP 429`, the selected provider is rate-limiting requests
or the account has reached a usage limit. Wait before retrying and check that
provider's usage and limits. A response that triggers web search can make two
requests in one chat turn.

## Test search from the console

Run the interactive console, which calls the search service directly:

```bash
python test/console_search.py
```

Enter a search query; leave it blank to exit. Optional settings:

```bash
python test/console_search.py --max-results 5 --region us-en --safesearch strict
```

The search service uses SerpApi's DuckDuckGo engine. Add `SERPAPI_API_KEY` to
`.env` before searching; get the key from your SerpApi account. Search settings
use `--region` in `country-language` format. The default `vn-vi` is mapped to
DuckDuckGo's supported `vn-en` region.

Found URLs are appended to `search_results.txt` in the current directory by
default. Choose a different output file with `--output`:

```bash
python test/console_search.py --output test/results/search.txt
```

## Test scraping from the console

Run the scraper to process every URL from `search_results.txt` using the
scrape service directly:

```bash
python test/console_scrape.py
```

To use a different file containing one URL per line:

```bash
python test/console_scrape.py --input test/results/search.txt
```

To scrape one URL directly:

```bash
python test/console_scrape.py https://www.python.org/about/
```

By default, the plain-text result is appended to `scraped_data.txt` in the current
directory. Choose a different output file with `--output`:

```bash
python test/console_scrape.py --output test/results/python.txt https://www.python.org/about/
```

The scraper continues after individual URL failures and returns a non-zero exit
code if any URL fails.

## Test embedding from the console

Start the API, then use the console to call the embedding and ranking endpoints:

```bash
python test/console_embed_rerank.py
```

The console calls `GET /embeddings/single` when using `--single`, and
`POST /ranking` to rank text records. It connects to `http://127.0.0.1:8000`
by default; use `--api-url` to choose another API server. For example:

```bash
python test/console_embed_rerank.py --single "Một câu tiếng Việt" \
  --api-url http://127.0.0.1:8000
```

## Chat with Gemini from the console

Configure `GEMINI_API_KEY` in `.env`, then run:

```bash
python test/console_gemini.py
```

The script calls the Gemini service directly. Enter messages at the prompt;
the conversation context is kept for follow-up messages. Enter `/exit` to end
the chat. You can override the model, temperature, or token limit:

```bash
python test/console_gemini.py --model gemini-2.5-flash \
  --temperature 0.7 --max-tokens 500
```

Or test with a custom Vietnamese sentence:

```bash
python test/console_embed_rerank.py "Trí tuệ nhân tạo đang phát triển rất nhanh tại Việt Nam"
```

To search the text chunks in `scraped_data_processed.json`, run the same
command without a query and enter the search text when prompted. The script
sends the query and chunks to the ranking API, which uses BM25 and date proximity
to establish an initial order before cross-encoder reranking, then saves the
ranked records with a `relevance_score` field to
`scraped_data_ranked.json`:

```bash
python test/console_embed_rerank.py
```

You can provide the query and customize the input/output files:

```bash
python test/console_embed_rerank.py "tiến độ sân bay Long Thành" \
  --input scraped_data_processed.json \
  --output search_results_ranked.json
```

## Test paragraph chunking

Start the API:

```bash
python -m uvicorn app.main:app --reload
```

Then split text through the console client. The API prefers paragraph boundaries:

```bash
python test/console_tokenize.py
```

Or pass text directly and customize the chunk size and overlap (in characters):

```bash
python test/console_tokenize.py --chunk-size 1000 --chunk-overlap 100 "Đoạn văn thứ nhất.

Đoạn văn thứ hai."
```

The client can connect to a different API address with `--api-url`.

To process scraped JSON into a JSON file where each token-limited chunk is a
separate object with its text and source metadata, run:

```bash
python test/chunking.py --input scraped_data.txt --output scraped_data_processed.json --max-tokens 450
```

The script uses the `intfloat/multilingual-e5-small` tokenizer and includes
special tokens in the limit. The default is 450 tokens per chunk (the model
limit is 512). Each object in the output array has a `text` field for one chunk
and a `metadata` object containing the source record's metadata. Use `--model`
to select a different tokenizer.

Direct API request:

```bash
curl -X POST http://127.0.0.1:8000/chunks/split \
  -H "Content-Type: application/json" \
  -d '{"text":"Đoạn văn thứ nhất.\n\nĐoạn văn thứ hai.","metadata":{"source":"https://example.com","title":"Bài viết mẫu"},"chunk_size":1000,"chunk_overlap":100}'
```

Each entry in `chunks` contains one chunk's `text` and a `metadata` object
copied from the request. If omitted, `metadata` is an empty object.

## Endpoints

- `GET /` — welcome message
- `GET /chat` — web chat UI for choosing Gemini or Groq
- `POST /chat/gemini` — send a chat request to Gemini (requires `GEMINI_API_KEY`)
- `POST /chat/groq` — send a chat request to Groq (requires `GROQ_API_KEY`)
- `GET /search?q=FastAPI&max_results=10` — search DuckDuckGo through SerpApi (requires `SERPAPI_API_KEY`)
- `GET /scrape?url=https%3A%2F%2Fwww.python.org%2Fabout%2F` — extract webpage text and metadata with Trafilatura
- `POST /embeddings` — compute dense vector embeddings for a list of texts (default: `intfloat/multilingual-e5-small`, 384 dimensions); supports `text_type: "query" | "passage"` (default: `"passage"`)
- `GET /embeddings/single?text=...` — compute dense vector embedding for a single text; supports `text_type: "query" | "passage"` (default: `"query"`)
- `POST /ranking` — rank documents with BM25, date proximity, and cross-encoder reranking
- `POST /semantic-search` — search the web, scrape pages, split text into chunks, and rank by relevance
- `POST /chunks/split` — split text into paragraph-aware chunks using LangChain

Set the API key for the provider you want to use in a local `.env` file before
starting the API. Add `GEMINI_API_KEY` and/or `GROQ_API_KEY` to `.env`; `.env` is
excluded from Git. Gemini defaults to `gemini-3.5-flash-lite`, and Groq defaults
to `llama-3.3-70b-versatile`. The model, temperature, and maximum output tokens
can be supplied in the request:

```bash
# Add GEMINI_API_KEY, GROQ_API_KEY, and SERPAPI_API_KEY to .env as needed.
python -m uvicorn app.main:app --reload
```

Then send a Gemini chat request (use `/chat/groq` and `GROQ_API_KEY` for Groq):

```bash
curl -X POST http://127.0.0.1:8000/chat/gemini \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Xin chào!"}],"temperature":0.7}'
```

You can also open <http://127.0.0.1:8000/chat> in a browser to try the chat
interface. It keeps conversation context and lets you choose Gemini or Groq;
the interface sends requests to the matching endpoint.

The response contains the assistant `message`, the model used, and token `usage`
when provided by the selected provider.

The chat API asks the selected provider to return a JSON action to answer,
clarify, or search. Each request also includes the current date and time in the
API server's timezone. When the provider returns a `search` action, the chat API
calls `/semantic-search` internally and searches up to ten web pages by default.

The semantic-search endpoint runs the complete web retrieval flow. It accepts a
query and optional search, chunking, and embedding settings:

```bash
curl -X POST http://127.0.0.1:8000/semantic-search \
  -H "Content-Type: application/json" \
  -d '{"query":"tiến độ sân bay Long Thành","max_results":3,"chunk_size":1000,"chunk_overlap":100}'
```

The response includes ranked results with source metadata and relevance scores;
each matching chunk remains a separate result. It also includes counts
for searched pages and chunks, and any pages that could not be scraped.
`step_timings` reports server-side elapsed seconds for search, scrape, chunking,
and ranking. A failed page does not prevent other search results
from being processed. The ranked results are returned in the API response
and are no longer saved to a file.

To export the ranked chunks saved by `test/console_embed_rerank.py` as Markdown
without running semantic search again, run:

```bash
python test/console_markdown_export.py
```

By default, this reads `test/output/scraped_data_ranked.json`, keeps each record
separate, writes the Markdown result to `test/output/scraped_data_markdown.md`,
and prints it to the console.

Start the API server, then run semantic search through `POST /semantic-search`:

```bash
python test/console_semantic_search.py
```

Enter a query when prompted, or pass it directly with optional search settings:

```bash
python test/console_semantic_search.py "tiến độ sân bay Long Thành" \
  --max-results 5 --chunk-size 1000 --chunk-overlap 100 \
  --output semantic_search_response.json
```

The console sends requests to `http://127.0.0.1:8000` by default. Use
`--api-url` to connect to a different API server.

The script prints processing counts, timing, and scrape failures without
printing ranked results or matched text. It can save the full result, including
ranked results and text, to a JSON file with `--output`.

The ranking endpoint accepts a query and documents in the same `text` and
`metadata` shape produced by `test/chunking.py`:

```bash
curl -X POST http://127.0.0.1:8000/ranking \
  -H "Content-Type: application/json" \
  -d '{"query":"tiến độ sân bay Long Thành","documents":[{"text":"Sân bay Long Thành đang được xây dựng.","metadata":{"source":"https://example.com","title":"Tiến độ sân bay"}},{"text":"Dự báo thời tiết ngày mai.","metadata":{"source":"https://example.org","title":"Thời tiết"}}]}'
```

The response contains the documents sorted from most to least relevant, with
their original metadata and a `relevance_score`. Documents are first ranked by
BM25 and date proximity, then reranked by a cross-encoder with date proximity
boosting the final score.

The search endpoint accepts `q` (required), `max_results` (1–50, default 1),
`region` (default `wt-wt`), and `safesearch` (`off`, `moderate`, or `strict`).
Search results are returned as a JSON array of URLs only. Upstream search
errors return HTTP 502.

The scrape endpoint accepts a publicly reachable HTTP(S) webpage URL and returns
Trafilatura's extracted JSON metadata with the article content in the `text`
field formatted as plain text. The console client prints and saves plain text.
The endpoint rejects non-public hosts, follows up to five redirects,
and limits downloaded pages to 5 MB.
Install the added dependencies with `pip install -r requirements.txt` before
starting the API.

## Current project structure

This checkout is a service-oriented scaffold. The main implementation modules
currently live under `app/services`; the active routes are registered in
`app/main.py`:

- `app/main.py` — app bootstrap and lifecycle setup
- `app/routers/chat_ui.py` — `/chat` page route
- `app/routers/embeddings.py` — `/embeddings`, `/embeddings/single`, and `/ranking` API routes
- `app/routers/semantic_search.py` — `/semantic-search` API route
- `app/routers/health.py` — `/health` route
- `app/services/search.py` — DuckDuckGo web search through SerpApi
- `app/services/scrape.py` — webpage extraction with Trafilatura
- `app/services/embeddings.py` — dense embedding logic
- `app/services/ranking.py` — BM25 and date-priority ranking logic
- `app/services/semantic_search.py` — end-to-end search/scrape/chunk/rank flow
- `app/services/chunks.py` — paragraph-aware chunking logic
- `app/services/chat.py` — shared provider-independent chat and RAG orchestration
- `app/services/gemini.py` — Gemini chat integration
- `app/services/groq.py` — Groq chat integration
- `app/services/markdown_export.py` — load ranked chunks and render them as Markdown
- `app/static/` — frontend assets for the chat UI
- `test/` — console scripts and validation helpers

The app remains a work in progress; only the routes listed above are currently
registered.
