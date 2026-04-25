# This is a public repo!

# Moonshine — Overnight Research Loop

A simple, durable two-role research system that runs all night, searches the web,
accumulates source notes, and produces a progressively improving report by morning.

## How it works

Each cycle does exactly this:

```
1. Researcher  → asks LLM for search queries
               → searches the web
               → fetches + extracts page text
               → LLM summarises each source
               → saves accepted sources to DB + disk immediately

2. Synthesiser → reads ALL accumulated notes
               → reads current draft report
               → LLM produces improved draft
               → identifies gaps and next search angles
               → saves draft to DB + disk immediately

3. Cycle count incremented → repeat
```

Everything is saved after each step. If the process is killed, restart with
`--resume` and it picks up from the next cycle.

---

## Setup

### 1. Create a virtual environment

```bash
cd /data/tools/moonshine
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialise the database

```bash
python init_db.py
```

This creates `topic_loop.db` in the project directory.

### 4. Make sure Ollama is running

```bash
ollama serve
ollama pull gpt-oss:20b   # or whatever model you use
```

Check the model name and URL in `config.py`.

### 5. Set your research topic

`topic.txt` is gitignored to keep your topics private. Copy the example and edit it:

```bash
cp topic.txt.example topic.txt
```

Then edit `topic.txt` with your research question — one question per file:

```
What are the long-term macroeconomic effects of universal basic income?
```

---

## Running

### Start a new run

```bash
python run_topic_loop.py
```

### Resume after an interruption

```bash
python run_topic_loop.py --resume
```

### Resume a specific run by ID

```bash
python run_topic_loop.py --resume --run-id 3
```

### Run with a custom cycle limit

```bash
python run_topic_loop.py --max-cycles 60
```

---

## Outputs

Working files are saved under `outputs/`:

| File | Contents |
|------|----------|
| `run_N_notes.md` | All accepted sources with summaries, key points, scores |
| `run_N_draft.md` | Latest draft report (updated every cycle) |

Final reports are saved under `outputs/reports/`:

| File | Contents |
|------|----------|
| `run_N_final_report.md` | Final report written when the run completes |

Logs are saved under `logs/run_N.log`.

The SQLite database `topic_loop.db` holds the full structured state, including the full extracted text of each accepted source.

---

## Configuration

Edit `config.py` to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `MODEL_NAME` | `gpt-oss:20b` | Ollama model to use |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `MAX_CYCLES` | `40` | Cycles to run (40 cycles ≈ overnight) |
| `SOURCES_PER_CYCLE` | `2` | Sources to accept per cycle |
| `MIN_RELEVANCE_SCORE` | `3` | Minimum LLM relevance score (1–10) |
| `MIN_QUALITY_SCORE` | `3` | Minimum LLM quality score (1–10) |
| `SEARCH_PROVIDER` | `tavily` | Search backend (see below) |
| `MAX_TEXT_CHARS` | `12000` | Characters to extract from each page |

---

## Plugging in a real search provider

The search layer lives in `search.py`. Set `SEARCH_PROVIDER` in `config.py` to one of:

### Tavily (recommended)

Get an API key at https://tavily.com/, then:

```bash
export TAVILY_API_KEY=your_key_here
```

And in `config.py`:

```python
SEARCH_PROVIDER = "tavily"
```

### SearXNG (self-hosted)

```bash
# Run SearXNG locally with Docker
docker run -d -p 8080:8080 searxng/searxng
```

Then in `config.py`:

```python
SEARCH_PROVIDER = "searxng"
SEARXNG_URL = "http://localhost:8080"
```

### Brave Search API

Get an API key at https://api.search.brave.com/, then:

```bash
export BRAVE_API_KEY=your_key_here
```

And in `config.py`:

```python
SEARCH_PROVIDER = "brave"
```

### Adding a new provider

Add a function `_yourprovider_search(query, num_results) -> list[dict]` in
`search.py` and register it in the `providers` dict at the top of `search()`.
Each result dict needs `url`, `title`, and `snippet` keys.

---

## Inspecting state mid-run

```bash
# Check run status
sqlite3 topic_loop.db "SELECT id, status, cycle_count, max_cycles FROM runs ORDER BY id DESC LIMIT 5;"

# See accepted sources
sqlite3 topic_loop.db "SELECT cycle_number, title, relevance_score, quality_score FROM sources WHERE status='accepted' ORDER BY id;"

# See failures
sqlite3 topic_loop.db "SELECT cycle_number, stage, url, error_message FROM failures ORDER BY id DESC LIMIT 20;"
```

---

## Architecture

```
run_topic_loop.py   Main loop — orchestrates cycles, handles crashes gracefully
researcher.py       Researcher role — search, fetch, summarise, score, save
synthesiser.py      Synthesiser role — integrate notes, improve draft, identify gaps
ollama_client.py    Thin wrapper around Ollama HTTP API with retries
search.py           Search abstraction — mock / SearXNG / Brave
fetcher.py          HTTP fetch + BeautifulSoup text extraction
db.py               SQLite helpers — all reads and writes go through here
prompts.py          All LLM prompt templates
config.py           All configuration in one place
init_db.py          One-time database schema creation
```

---

## Assumptions

- Ollama is running locally and the configured model is already pulled.
- With `SEARCH_PROVIDER = "mock"` the researcher pass accepts 0 sources per cycle
  (the system still runs and synthesises, but has no new material).
- Page fetch uses a browser-like User-Agent; heavily JS-rendered pages will return
  little text. Browser automation is not included in v1.
- The LLM scores (relevance, quality) are the model's own judgement — calibrate
  `MIN_RELEVANCE_SCORE` and `MIN_QUALITY_SCORE` to taste.
- Cycles with 0 new sources still run the synthesiser (it may still improve the draft
  by reorganising existing notes).
