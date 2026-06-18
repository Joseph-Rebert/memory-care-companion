# Memory Care Companion — Chatbot

A Streamlit web chat that answers Alzheimer's-caregiver questions, grounded in
the real case studies you collected, powered by the Claude API.

## One-time setup

1. Install dependencies (from the project root):
   ```bash
   pip install -r requirements.txt
   ```
2. Add your API keys. Copy `.env.example` to `.env` and paste:
   ```
   ANTHROPIC_API_KEY=sk-ant-...   # the chat model (https://console.anthropic.com/settings/keys)
   VOYAGE_API_KEY=pa-...          # embeddings for retrieval (https://dash.voyageai.com/api-keys)
   ```
   Keys stay in `.env`, which is gitignored — never paste them into chat or
   commit them. (Without `VOYAGE_API_KEY` the chat still works — it just falls
   back to sending all cases instead of retrieving.)
3. Build the retrieval index once:
   ```bash
   python -m alz_finder.cli build-embeddings
   ```

## Run it

```bash
streamlit run chatbot/app.py
```

A browser tab opens with the chat. Type a caregiver question (e.g. *"My dad gets
agitated in the evenings — what can I do?"*) and it answers from your cases,
citing them, with safety guardrails (it defers medical/medication decisions to
clinicians and stays on topic).

Sidebar controls: pick the **model**, see how many **cases** are loaded, view
**Sources**, **Refresh knowledge** after you add cases, and **Clear chat**.

## Growing the knowledge — self-serve, no code changes

When you collect more case studies, turn them into chatbot knowledge with the
same CLI you already use, then refresh:

```bash
# add cases by searching, OR import a CSV of article URLs (PMCID/PMID/DOI links):
python -m alz_finder.cli search          --profile case-studies --limit 50
python -m alz_finder.cli import-csv      "Possible Sources.csv"   # URLs → library

python -m alz_finder.cli fetch-fulltext  --profile case-studies
python -m alz_finder.cli analyze         --profile case-studies --min-score 1
python -m alz_finder.cli build-embeddings                        # re-index for retrieval
python -m alz_finder.cli build-kb        --profile case-studies  # optional: updates cases.jsonl
# then click "Refresh knowledge" in the running app (or restart it)
```

`import-csv` reads URLs from the first column of a CSV, extracts a PMCID/PMID/DOI
from each, and resolves it via Europe PMC. URLs with no usable ID are written to
`output/unresolved_sources.txt`.

Re-run `build-embeddings` whenever you `analyze` new cases — it rebuilds the
vector index so the new cases become retrievable.

`analyze` calls Claude to write the structured per-case analysis into
`knowledge_base/analysis.jsonl` (the file the chatbot reads). It's **idempotent**
— only new cases are analyzed — and it tags each case's relevance, skipping
`off-topic` ones from the chatbot.

## Models & cost

- **Chat** defaults to `claude-opus-4-8` (most capable); switch to
  `claude-sonnet-4-6` or `claude-haiku-4-5` in the sidebar for lower cost.
- **`analyze`** defaults to `claude-sonnet-4-6` (cheap for bulk extraction);
  override with `--model`.
- The case knowledge is sent as a **prompt-cached** system block, so after the
  first message each turn reuses it at ~10% of the input cost. The sidebar shows
  per-reply token usage (including cache reads) so you can watch this.

## How it works (RAG)

For each question the chatbot **retrieves** the few most relevant cases and
grounds the answer in only those — instead of sending the whole library every
time. This keeps cost roughly flat and answers sharp as the library grows.

1. `build-embeddings` embeds each case (via Voyage AI) into a vector index
   (`knowledge_base/index.npz` + `index_meta.json`) — see `alz_finder/embeddings.py`.
2. On each question, `chatbot/knowledge.py::retrieve_knowledge` embeds the
   question, finds the top-k cases by cosine similarity, and builds the grounding
   text from just those (the sidebar's **top-k** slider controls how many).
3. The sidebar shows which cases were used (with similarity scores).

**Fallback:** if the index hasn't been built or `VOYAGE_API_KEY` isn't set, the
chatbot automatically falls back to sending *all* non-off-topic cases
(`load_knowledge`). So it always works; retrieval just makes it cheaper at scale.

> Next step (separate push): a **golden set + retrieval metrics** (precision@k,
> recall@k) to measure that retrieval surfaces the right cases. See `FEATURES.md`.

## Files
```
chatbot/
  app.py            Streamlit UI (chat, sidebar, refresh)
  knowledge.py      loads analysis.jsonl → grounding text + sources
  prompts.py        caregiver system prompt + safety guardrails
  claude_client.py  Anthropic SDK wrapper (cached system block + streaming)
```

## Safety note
This assistant gives **general caregiver education and support, not medical
advice**. It is grounded in published, de-identified case reports for design
insight. Always direct medical, diagnostic, and medication questions to the
person's care team.
