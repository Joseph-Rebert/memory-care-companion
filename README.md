# Memory Care Companion

**Memory Care Companion** is an Alzheimer's caregiver-support chatbot plus the
Python toolkit that feeds it. This README covers the toolkit (`alz_finder`),
which locates, organizes, and tracks two kinds of source material for the
**Alzheimer's chatbot** in `chatbot/`:

1. **Patient case studies** — published clinical case reports on Alzheimer's
   patients (realistic symptom patterns, disease progression, conversational
   scenarios).
2. **AI / chatbot research** — conversational AI, LLMs, and dialogue systems
   applied to Alzheimer's and cognitive care (design and method guidance).

It queries free academic APIs, dedupes results into a local SQLite database,
lets you tag papers as you review them, and exports readable Markdown/CSV.

## Sources

| Source            | Key needed | Used for                                  |
|-------------------|------------|-------------------------------------------|
| PubMed (E-utils)  | optional   | clinical case reports                     |
| Europe PMC        | no         | case reports + open-access full text      |
| OpenAlex          | no         | broad metadata across both fields         |
| arXiv             | no         | CS/AI preprints (conversational AI, NLP)  |
| Semantic Scholar  | optional   | AI/CS papers + citation context           |

All sources are free. **No keys are required to start.** Adding optional keys in
`.env` (see `.env.example`) raises rate limits — useful because the keyless
Semantic Scholar pool and arXiv both throttle aggressively under load.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # optional: add NCBI/S2 keys + your contact email
```

## Usage

```bash
# Fetch case reports (PubMed + Europe PMC), dedupe, store
python -m alz_finder.cli search --profile case-studies --limit 25

# Fetch AI/chatbot research (Semantic Scholar + arXiv + OpenAlex)
python -m alz_finder.cli search --profile ai-chatbot --limit 25

# Review what's stored (sorted best-first by relevance score)
python -m alz_finder.cli list --profile case-studies --status unrated

# Only the strongest matches (relevance score 3-4 out of 4)
python -m alz_finder.cli list --profile case-studies --min-score 3

# Mark relevance and add a note
python -m alz_finder.cli tag 7 keep --note "good early-onset progression detail"
python -m alz_finder.cli note 7 "follow up on the linguistic intervention method"

# Export a readable review doc to output/
python -m alz_finder.cli export --profile case-studies --format md
python -m alz_finder.cli export --status keep --format csv

# Quick counts
python -m alz_finder.cli stats
```

### Building a knowledge base for a chatbot (RAG)

```bash
# 1. Pull open-access full text where available (abstract fallback otherwise)
python -m alz_finder.cli fetch-fulltext --profile case-studies --min-score 2

# 2. Build the chunked JSONL knowledge base in knowledge_base/
python -m alz_finder.cli build-kb --profile case-studies
```

This writes `knowledge_base/cases.jsonl` (chunked source text + metadata, ready
to embed). Only ~28% of case reports are open-access full text; the rest
contribute their dense abstracts. See `knowledge_base/README.md` for how to embed
and retrieve, and `notes/case-analysis.md` for the distilled per-case caregiver
analysis (also in `knowledge_base/analysis.jsonl`).

### The caregiver chatbot

A FastAPI web chat grounded in these cases lives in `chatbot/`. It uses **RAG**:
each question retrieves only the most relevant cases (via Voyage embeddings)
instead of sending all of them. Prepare the knowledge and run it:

```bash
python -m alz_finder.cli analyze          --profile case-studies --min-score 2  # needs ANTHROPIC_API_KEY
python -m alz_finder.cli build-embeddings                                       # needs VOYAGE_API_KEY
uvicorn chatbot.server:app --reload                                             # open http://127.0.0.1:8000
```

The server is stateless (the browser holds the conversation) and streams replies
over Server-Sent Events. The UI lives in `chatbot/static/` (plain HTML/CSS/JS,
no build step — edit and refresh). To deploy a live server, any host that runs a
`Procfile` (Render, Railway, Fly.io) works out of the box; set `ANTHROPIC_API_KEY`
and `VOYAGE_API_KEY` in the host's environment.

(Without `VOYAGE_API_KEY` / an index, the chat still works — it falls back to
sending all cases.) See `chatbot/README.md` for setup, the self-serve
add-knowledge workflow, models, and cost notes.

### Measuring retrieval quality

Once embeddings are built you can score how well the right cases are surfaced,
using a hand-labeled golden set (`eval/golden_set.jsonl`) that pairs test
questions with the case IDs that *should* come back:

```bash
# Precision@k, Recall@k, Hit@k, and MRR for k = 1, 3, 5
python -m alz_finder.cli eval

# Use a different golden set, k values, or save the raw results as JSON
python -m alz_finder.cli eval --golden eval/golden_set.jsonl --k 1,3,5 --output output/eval.json
```

Charts for the results live in `eval/make_charts.py` (and a plain-language
variant, `eval/make_charts_friendly.py`).

## Making sure results are real case studies *and* relevant

The `case-studies` profile applies two guarantees so you don't have to sift noise:

1. **Genuine case studies only.** Results not tagged `Case Reports` by the source
   are dropped before saving (`search` prints how many it dropped).
2. **Caregiver-relevance score (0-4).** Each paper is scored on the four
   dimensions a caregiver-support chatbot cares about — **symptoms & behavior**,
   **how the patient communicates**, **disease progression**, and **treatment &
   management** — and must actually be about Alzheimer's/dementia to score above 0.
   `list` and `export` are sorted best-first and accept `--min-score N`.

The scoring keywords live in `alz_finder/relevance.py`; edit the `DIMENSIONS`
lists to tune what counts as relevant.

## How it's organized

```
alz_finder/
  sources/        one module per API, each returns normalized Paper records
  normalize.py    unified Paper record + DOI/title dedup key + text cleaning
  store.py        SQLite: papers + review status + tags (dedup on insert)
  search.py       orchestrator: run a profile's sources -> dedupe -> store
  relevance.py    caregiver-relevance scoring (0-4 across four dimensions)
  fulltext.py     fetch open-access full text for stored papers
  analyze.py      Claude-driven per-case caregiver analysis
  embeddings.py   Voyage embeddings + cosine search (the RAG index)
  rag.py          retrieval glue used by the chatbot
  eval.py         golden-set retrieval metrics (P@k, R@k, Hit@k, MRR)
  import_urls.py  import article URLs from a CSV into the library
  export.py       Markdown / CSV writers
  cli.py          command-line entry point
chatbot/          FastAPI RAG chat (server.py + static/) grounded in the cases
eval/             golden set + chart scripts for retrieval metrics
config.yaml       editable search profiles (queries, year filter, sources)
data/papers.db    your collected papers (gitignored)
knowledge_base/   chunked JSONL knowledge base + embedding index (gitignored)
output/           generated review docs
notes/            longer-form manual curation write-ups
```

You can also bulk-import a list of article URLs (e.g. from a spreadsheet) into
the library:

```bash
python -m alz_finder.cli import-csv "Possible Sources.csv" --profile case-studies
```

## Refining searches

Edit `config.yaml` — change the `query`, `from_year`, `per_source_limit`, or the
list of `sources` per profile. No code changes needed. You can also add new
profiles (e.g. a narrower "speech & language in Alzheimer's" profile) by copying an
existing block.

## Note on using case reports

Published case reports are **de-identified** by their journals, but most are
**copyrighted**. Use them for **design insight** (symptom patterns, language,
progression) — not for verbatim redistribution or as training text you republish.
Always check each article's license (the open-access ones surfaced by Europe PMC
and OpenAlex are the safest to quote).
