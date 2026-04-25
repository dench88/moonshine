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

### 4. Set up your secrets file

API keys are loaded from `~/.secrets.env` at startup. Create it once:

```bash
touch ~/.secrets.env
chmod 600 ~/.secrets.env   # owner-only read/write
```

Then add the keys you need (see `.secrets.env.example` for the full list):

```
TAVILY_API_KEY=tvly-...
ANTHROPIC_API_KEY=sk-ant-...    # only if using an Anthropic model
OPENAI_API_KEY=sk-...           # only if using an OpenAI model
DEEPSEEK_API_KEY=sk-...         # only if using a DeepSeek model
```

Keys already set in your shell environment always take precedence over the file.

### 5. Make sure Ollama is running (if using local models)

```bash
ollama serve
ollama pull gpt-oss:20b   # or whichever local model you want
```

Check `RESEARCHER_MODEL` and `SYNTHESISER_MODEL` in `config.py`.

### 6. Set your research topics

`topic.txt` is gitignored to keep your topics private. Copy the example and edit it:

```bash
cp topic.txt.example topic.txt
```

Add one research question per line. Lines starting with `#` are comments and are ignored:

```
# My overnight research queue

What are the long-term macroeconomic effects of universal basic income?
What are the most promising recent advances in solid-state battery technology?
```

Each topic gets its own run, completed in full before the next one starts.

---

## Running

### Run all topics in topic.txt

```bash
python run.py
```

Runs each topic in `topic.txt` sequentially — one full run per topic, top to bottom. Each topic gets its own run ID, log file, notes file, and final report.

### Choose models at runtime

Use `--researcher` and `--synthesiser` to override the defaults in `config.py`:

```bash
python run.py --researcher gptoss --synthesiser claude
```

**Available model aliases:**

| Alias | Model | Where |
|-------|-------|-------|
| `gptoss` | `gpt-oss:20b` | Local (Ollama) |
| `qwen` | `qwen2.5:32b` | Local (Ollama) |
| `huihui` | `huihui_ai/glm-4.7-flash-abliterated:q4_K` | Local (Ollama) |
| `claude` | `claude-sonnet-4-6` | Anthropic API |
| `chatgpt` | `gpt-4o` | OpenAI API |
| `deepseek` | `deepseek-chat` | DeepSeek API |

You can also pass a full `provider/model-name` string if you want a model not in the alias list. Each role can use a different model — for example, use a fast local model for the Researcher and a stronger online model for the Synthesiser:

```bash
python run.py --researcher gptoss --synthesiser claude
```

### Resume an interrupted run

```bash
python run.py --resume
```

Resumes the most recent incomplete run (single topic). Once it completes it stops — it does not automatically continue to the next topic in `topic.txt`.

### Resume a specific run by ID

```bash
python run.py --resume --run-id 3
```

### Run with a custom cycle limit

```bash
python run.py --max-cycles 60
```

Applies to all topics in the current session.

---

## Outputs

Every run gets a number (`N`). Your first run is run 1, second is run 2, and so on.

### Reading a completed run

The quickest way to read results is the files written to disk:

| File | Where | What it contains |
|------|-------|-----------------|
| `run_N_final_report.md` | `outputs/reports/` | The finished report — start here |
| `run_N_notes.md` | `outputs/` | All accepted sources: summaries, key points, scores |
| `run_N_draft.md` | `outputs/` | The last working draft (same content as the final report if the run completed) |
| `logs/run_N.log` | `logs/` | Full log of everything that happened |

For example, after your first run:

```
outputs/reports/run_1_final_report.md   ← read this
outputs/run_1_notes.md                  ← all your sources
logs/run_1.log                          ← what happened
```

### Finding your run number

If you're not sure which run number to look for:

```bash
sqlite3 topic_loop.db "SELECT id, topic, status, cycle_count, created_at FROM runs ORDER BY id DESC LIMIT 10;"
```

This lists your most recent runs with their topics and status (`running`, `completed`, or `failed`).

---

## Configuration

Edit `config.py` to change:

| Setting | Default | Description |
|---------|---------|-------------|
| `RESEARCHER_MODEL` | `ollama/gpt-oss:20b` | Model used by the Researcher role |
| `SYNTHESISER_MODEL` | `ollama/gpt-oss:20b` | Model used by the Synthesiser role |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `MAX_CYCLES` | `40` | Cycles to run (40 cycles ≈ overnight) |
| `SOURCES_PER_CYCLE` | `2` | Sources to accept per cycle |
| `MIN_RELEVANCE_SCORE` | `3` | Minimum LLM relevance score (1–10) |
| `MIN_QUALITY_SCORE` | `3` | Minimum LLM quality score (1–10) |
| `SEARCH_PROVIDER` | `tavily` | Search backend (see below) |
| `FETCH_TIMEOUT` | `8` | Seconds before giving up on a slow/blocking site |
| `MAX_TEXT_CHARS` | `12000` | Characters to extract from each page |

### Choosing a model

Set `RESEARCHER_MODEL` and `SYNTHESISER_MODEL` in `config.py` using a short alias or a full `provider/model-name` string. See the alias table in the [Running](#running) section for the full list. Example:

```python
RESEARCHER_MODEL  = "gptoss"
SYNTHESISER_MODEL = "claude"
```

You can also override both at runtime with `--researcher` and `--synthesiser` — see below.

---

## Plugging in a real search provider

The search layer lives in `search.py`. Set `SEARCH_PROVIDER` in `config.py` to one of:

### Tavily (recommended)

Get an API key at https://tavily.com/, add it to `~/.secrets.env`:

```
TAVILY_API_KEY=tvly-...
```

And in `config.py`:

```python
SEARCH_PROVIDER = "tavily"
```

### SearXNG (self-hosted, free)

SearXNG is a self-hosted meta-search engine. It aggregates Google, Bing, DuckDuckGo and others. No API key needed, but it requires a small one-time setup to enable the JSON API that Moonshine uses.

#### Step 1 — Start SearXNG with Docker

```bash
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -e SEARXNG_SECRET_KEY="$(openssl rand -hex 32)" \
  -v "$PWD/searxng-config:/etc/searxng" \
  searxng/searxng
```

This creates a `searxng-config/` folder with default config files.

#### Step 2 — Enable the JSON API

SearXNG only serves HTML by default. Edit the generated config to add JSON:

```bash
# Open the settings file
nano searxng-config/settings.yml
```

Find the `search:` section and add `json` to formats:

```yaml
search:
  formats:
    - html
    - json
```

Save the file, then restart the container:

```bash
docker restart searxng
```

Verify it's working:

```bash
curl "http://localhost:8080/search?q=test&format=json" | head -c 200
```

You should see JSON output, not an error page.

#### Step 3 — Configure Moonshine

In `config.py`:

```python
SEARCH_PROVIDER = "searxng"
SEARXNG_URL = "http://localhost:8080"
```

> **Note:** SearXNG does not return page content — only URLs, titles, and snippets. Moonshine will fetch each page directly. Sites that block bots (like McKinsey) will still time out. Use Tavily if this is a problem.

### Brave Search API

Get an API key at https://api.search.brave.com/, add it to `~/.secrets.env`:

```
BRAVE_API_KEY=...
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

## Browsing and searching past research

Everything Moonshine collects — every source, summary, draft, and extracted web page — is stored in `topic_loop.db`. There are two ways to explore it.

### Option 1: Visual browser (recommended for browsing)

[Datasette](https://datasette.io/) gives you a web interface to browse and search the database with no SQL needed. It's already in `requirements.txt`.

```bash
datasette topic_loop.db
```

Then open **http://localhost:8001** in your browser. You'll see:

- **runs** — all your research topics, with status and cycle count
- **sources** — every web source collected, filterable by score or run
- **drafts** — every draft report, one per cycle

The search box at the top of each table searches the full text of that table — source summaries, titles, extracted page text, draft content — across all runs.

### Option 2: Command-line search

If you prefer the terminal, you can search directly:

```bash
# Find all sources mentioning a term (replace 'your search terms')
sqlite3 topic_loop.db \
  "SELECT s.title, s.url, s.relevance_score, r.topic
   FROM sources s
   JOIN sources_fts f ON s.id = f.rowid
   JOIN runs r ON s.run_id = r.id
   WHERE sources_fts MATCH 'your search terms'
   ORDER BY rank;"

# Find drafts mentioning a term
sqlite3 topic_loop.db \
  "SELECT d.run_id, d.cycle_number, r.topic
   FROM drafts d
   JOIN drafts_fts f ON d.id = f.rowid
   JOIN runs r ON d.run_id = r.id
   WHERE drafts_fts MATCH 'your search terms'
   ORDER BY rank;"
```

### Rebuilding the search index

The search index is updated automatically during each run. If you have data from before search indexing was added, or you've edited the database manually, rebuild it with:

```bash
python rebuild_fts.py
```

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
run.py   Main loop — orchestrates cycles, handles crashes gracefully
researcher.py       Researcher role — search, fetch, summarise, score, save
synthesiser.py      Synthesiser role — integrate notes, improve draft, identify gaps
llm_client.py       Unified LLM dispatcher — routes to Ollama / Anthropic / OpenAI / DeepSeek
search.py           Search abstraction — Tavily / SearXNG / Brave / mock
fetcher.py          HTTP fetch + BeautifulSoup text extraction
db.py               SQLite helpers — all reads and writes go through here
prompts.py          All LLM prompt templates
config.py           All configuration in one place
init_db.py          One-time database schema creation (run once)
rebuild_fts.py      Rebuild full-text search indexes from existing data
```

---

## Assumptions

- If using a local model, Ollama is running and the model is already pulled (`ollama pull model-name`).
- If using an online model, the relevant API key is set in `~/.secrets.env`.
- With `SEARCH_PROVIDER = "mock"` the researcher pass accepts 0 sources per cycle
  (the system still runs and synthesises, but has no new material).
- Page fetch uses a browser-like User-Agent; heavily JS-rendered pages will return
  little text. Browser automation is not included in v1.
- The LLM scores (relevance, quality) are the model's own judgement — calibrate
  `MIN_RELEVANCE_SCORE` and `MIN_QUALITY_SCORE` to taste.
- Cycles with 0 new sources still run the synthesiser (it may still improve the draft
  by reorganising existing notes).
