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
python -m app.console_search
```

Enter a search query; leave it blank to exit. Optional settings:

```bash
python -m app.console_search --api-url http://127.0.0.1:8000 --max-results 5 --region us-en --safesearch strict
```

## Test scraping from the console

Start the API, then in another terminal run the interactive console client:

```bash
python test/console_scrape.py
```

Enter a publicly accessible webpage URL; leave it blank to exit. To scrape one
URL directly:

```bash
python test/console_scrape.py https://www.python.org/about/
```

By default, the plain-text result is appended to `scraped_data.txt` in the current
directory. Choose a different output file with `--output`:

```bash
python test/console_scrape.py --output test/results/python.txt https://www.python.org/about/
```

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

Or test with a custom Vietnamese sentence:

```bash
python test/console_embed.py "Trí tuệ nhân tạo đang phát triển rất nhanh tại Việt Nam"
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

To process scraped JSON into a JSON file with each token-limited chunk stored in
its own field (`paragraph_1`, `paragraph_2`, etc.), run:

```bash
python test/chunking.py --input scraped_data.txt --output scraped_data_processed.json --max-tokens 450
```

The script uses the `intfloat/multilingual-e5-small` tokenizer and includes
special tokens in the limit. The default is 450 tokens per chunk (the model
limit is 512). Each output record retains its metadata, replaces the original
`text` field with individual chunk fields, and is written as part of a JSON
array. Use `--model` to select a different tokenizer.

Direct API request:

```bash
curl -X POST http://127.0.0.1:8000/chunks/split \
  -H "Content-Type: application/json" \
  -d '{"text":"Đoạn văn thứ nhất.\n\nĐoạn văn thứ hai.","chunk_size":1000,"chunk_overlap":100}'
```

## Endpoints

- `GET /` — welcome message
- `GET /health` — health check
- `GET /search?q=FastAPI&max_results=10` — search the web with DuckDuckGo
- `GET /scrape?url=https%3A%2F%2Fwww.python.org%2Fabout%2F` — extract webpage text and metadata with Trafilatura
- `POST /embeddings` — compute dense vector embeddings for a list of texts (default: `intfloat/multilingual-e5-small`, 384 dimensions)
- `GET /embeddings/single?text=...` — compute dense vector embedding for a single text
- `POST /chunks/split` — split text into paragraph-aware chunks using LangChain

The search endpoint accepts `q` (required), `max_results` (1–50, default 10),
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
- `app/routers/scrape.py` — `GET /scrape`
- `app/routers/embeddings.py` — `POST /embeddings`, `GET /embeddings/single`
- `app/routers/chunks.py` — `POST /chunks/split`
- `app/main.py` — creates the FastAPI app and registers the routers
