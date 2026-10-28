# RAG API

A starter API built with FastAPI.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

Open <http://127.0.0.1:8000/docs> for the interactive API documentation.
The default embedding model is loaded during server startup, so the first
startup may take longer while the model is downloaded. The server accepts
requests after the model has loaded.

## Test search from the console

Start the API in one terminal:

```bash
uvicorn app.main:app --reload
```

Then start the interactive console client in another terminal:

```bash
python test/console_search.py
```

Enter a search query; leave it blank to exit. Optional settings:

```bash
python test/console_search.py --api-url http://127.0.0.1:8000 --max-results 5 --region us-en --safesearch strict
```

Found URLs are appended to `search_results.txt` in the current directory by
default. Choose a different output file with `--output`:

```bash
python test/console_search.py --output test/results/search.txt
```

## Test scraping from the console

Start the API, then run the scraper to process every URL from
`search_results.txt`:

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

To use an API running at a different address:

```bash
python test/console_scrape.py --api-url http://127.0.0.1:8000 https://www.python.org/about/
```

## Test embedding from the console

Start the API in one terminal:

```bash
uvicorn app.main:app --reload
```

Then test the embedding endpoint:

```bash
python test/console_embed.py
```

## Chat with Groq from the console

Configure `GROQ_API_KEY` in `.env`, start the API, then run:

```bash
python test/console_groq.py
```

Enter messages at the prompt. The client keeps the conversation context for
follow-up messages; enter `/exit` to end the chat. You can override the API
address, model, temperature, or token limit:

```bash
python test/console_groq.py --api-url http://127.0.0.1:8000 \
  --model llama-3.3-70b-versatile --temperature 0.7 --max-tokens 500
```

Or test with a custom Vietnamese sentence:

```bash
python test/console_embed.py "Trí tuệ nhân tạo đang phát triển rất nhanh tại Việt Nam"
```

To search the text chunks in `scraped_data_processed.json`, run the same
command without a query and enter the search text when prompted. The script
embeds the query and each chunk, sorts the chunks by cosine similarity, and
saves the ranked records with a `relevance_score` field to
`scraped_data_ranked.json`:

```bash
python test/console_embed.py
```

You can provide the query and customize the input/output files:

```bash
python test/console_embed.py "tiến độ sân bay Long Thành" \
  --input scraped_data_processed.json \
  --output search_results_ranked.json
```

## Test paragraph chunking

Start the API:

```bash
uvicorn app.main:app --reload
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
- `GET /health` — health check
- `GET /chat` — web chat UI for trying the Groq chat endpoint
- `POST /chat/groq` — send a chat completion request to Groq (requires `GROQ_API_KEY`)
- `GET /search?q=FastAPI&max_results=10` — search the web with DuckDuckGo
- `GET /scrape?url=https%3A%2F%2Fwww.python.org%2Fabout%2F` — extract webpage text and metadata with Trafilatura
- `POST /embeddings` — compute dense vector embeddings for a list of texts (default: `intfloat/multilingual-e5-small`, 384 dimensions)
- `GET /embeddings/single?text=...` — compute dense vector embedding for a single text
- `POST /ranking` — embed a search query and documents, then sort documents by cosine similarity
- `POST /semantic-search` — search the web, scrape pages, split text into chunks, embed, and rank by relevance
- `POST /chunks/split` — split text into paragraph-aware chunks using LangChain

Set `GROQ_API_KEY` in a local `.env` file before starting the API to use the chat
endpoint. Copy `.env.example` to `.env` and replace the placeholder with your
Groq API key. `.env` is excluded from Git. The endpoint defaults to
`llama-3.3-70b-versatile`; the model, temperature, and maximum output tokens can
be supplied in the request:

```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY to your key.
uvicorn app.main:app --reload
```

Then send a chat request:

```bash
curl -X POST http://127.0.0.1:8000/chat/groq \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Xin chào!"}],"temperature":0.7}'
```

You can also open <http://127.0.0.1:8000/chat> in a browser to try the chat
interface. It keeps conversation context, supports selecting a model, and sends
requests to the same `/chat/groq` endpoint.

The response contains the assistant `message`, the model used, and token `usage`
when provided by Groq.

The chat API includes a system rule: when the chatbot does not know an asked
fact, it should respond with `search: [nội dung cần tìm kiếm]` so the system can
look it up. Each request also includes the current date and time in the API
server's timezone. When Groq returns a `search:` request, the chat API calls
`/semantic-search` internally and sends up to five ranked text chunks and their
sources back to Groq to generate the final answer.

The semantic-search endpoint runs the complete web retrieval flow. It accepts a
query and optional search, chunking, and embedding settings:

```bash
curl -X POST http://127.0.0.1:8000/semantic-search \
  -H "Content-Type: application/json" \
  -d '{"query":"tiến độ sân bay Long Thành","max_results":5,"chunk_size":1000,"chunk_overlap":100}'
```

The response includes the ranked chunks with source metadata and relevance
scores, counts for searched pages and chunks, and any pages that could not be
scraped. `step_timings` reports server-side elapsed seconds for search, scrape,
chunking, embedding, and ranking. A failed page does not prevent other search
results from being processed.

To test the endpoint from a console client, start the API and run:

```bash
python test/console_semantic_search.py
```

Enter a query when prompted, or pass it directly with optional API settings:

```bash
python test/console_semantic_search.py "tiến độ sân bay Long Thành" \
  --max-results 5 --chunk-size 1000 --chunk-overlap 100 \
  --output semantic_search_response.json
```

The client prints processing counts, timing, and scrape failures without
printing ranked results or matched text. It can save the full API response,
including ranked results and text, to a JSON file with `--output`.

The ranking endpoint accepts a query and documents in the same `text` and
`metadata` shape produced by `test/chunking.py`:

```bash
curl -X POST http://127.0.0.1:8000/ranking \
  -H "Content-Type: application/json" \
  -d '{"query":"tiến độ sân bay Long Thành","documents":[{"text":"Sân bay Long Thành đang được xây dựng.","metadata":{"source":"https://example.com","title":"Tiến độ sân bay"}},{"text":"Dự báo thời tiết ngày mai.","metadata":{"source":"https://example.org","title":"Thời tiết"}}]}'
```

The response contains the documents sorted from most to least relevant, with
their original metadata and a `relevance_score`. The endpoint reuses the
embedding service and model from `POST /embeddings`.

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

## API structure

- `app/routers/root.py` — `GET /`
- `app/routers/health.py` — `GET /health`
- `app/routers/search.py` — `GET /search`
- `app/routers/ranking.py` — `POST /ranking`
- `app/routers/semantic_search.py` — `POST /semantic-search`
- `app/routers/scrape.py` — `GET /scrape`
- `app/routers/embeddings.py` — `POST /embeddings`, `GET /embeddings/single`
- `app/routers/chunks.py` — `POST /chunks/split`
- `app/main.py` — creates the FastAPI app and registers the routers
