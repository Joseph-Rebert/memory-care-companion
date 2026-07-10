# Mentor Meeting — Memory Care Companion (2026-06-30)

A live demo is running at **http://127.0.0.1:8000** (FastAPI server, streaming chat UI).

---

## TL;DR — what to say first
"I built a working Alzheimer's-caregiver assistant. It answers caregiver
questions and grounds every answer in a library of **92 real, published
Alzheimer's case reports** — and it cites the case it used. This week I rebuilt
the front end into a real web app and got the retrieval (RAG) pipeline working
live against the production embeddings API. It's demo-ready right now."

---

## What the project is
- A **RAG chatbot** for Alzheimer's caregivers — practical, supportive answers,
  *not* medical advice (it says so up front and routes medical decisions to the
  care team).
- Two halves:
  - **`alz_finder/`** — a toolkit that finds, ingests, and distills real
    published Alzheimer's case reports into a clean knowledge base.
  - **`chatbot/`** — the web app that answers questions grounded in that base.
- Knowledge base today: **92 analyzed case reports** (from PubMed/Europe PMC),
  each distilled into patient profile, symptoms, communication, progression,
  treatment, caregiver insights, and example Q&A.

---

## What changed / what I accomplished (this stretch)

### 1. Migrated the app from Streamlit → FastAPI + a real web UI
- **Why it matters:** Streamlit was a prototype scaffold. The new stack is a
  proper, deployable web app.
- Streaming answers over **Server-Sent Events** — text appears word-by-word like
  ChatGPT instead of waiting for the whole reply.
- A clean, custom, **build-step-free** chat UI (plain HTML/CSS/JS).
- **Stateless server** — the browser holds the conversation, so it can scale to
  many users with no session database.
- Added a **`Procfile`** → one-line deploy to Render / Railway / Fly.io.

### 2. Got RAG retrieval working *live* (the big technical win)
- Instead of stuffing all 92 cases into every prompt, the app **embeds the
  question and retrieves only the most relevant cases** (Voyage AI embeddings,
  `voyage-3.5`, 1024-dim, cosine similarity).
- **Tested live today against the real embeddings API** — it works end to end.

### 3. Verified retrieval quality with a quick test
Sample caregiver questions → top retrieved case (relevance score):

| Question | Top case retrieved | Score |
|---|---|---|
| Evening agitation | Urinary retention in AD *with agitation* | 0.59 |
| Trouble swallowing | Gastrostomy-tube obstruction / pica | 0.52 |
| Can't find her words | Logopenic primary progressive aphasia | 0.46 |
| Early warning signs | Early-Onset AD with aphasia | 0.66 |
| **"Best pizza topping?"** (control) | (noise) | **0.31** |

**Takeaway:** every real question pulled topically-correct cases, and the
off-topic control scored far lower (0.31 vs 0.45–0.66) — a clean, measurable gap.

### 4. Answers cite their sources
In the live demo, an agitation question produced advice that explicitly named
the doll-therapy and vocalization case reports it drew from — so answers are
**traceable, not black-box.**

---

## Suggested live demo flow (2–3 min)
1. Open http://127.0.0.1:8000 — point out the disclaimer ("support, not medical advice").
2. Ask: *"My mom gets very agitated every evening — any tips?"* → watch it stream
   and **cite a case**.
3. Ask a follow-up: *"How do I communicate when she can't find her words?"*
4. (Optional) Ask something off-topic to show it stays in its lane.

---

## What's next (where I'd want your input)
- **Relevance threshold:** add a cutoff (~0.40) so off-topic questions ground on
  *nothing* rather than the closest-but-irrelevant case. Want to pick the number
  empirically, not by guess.
- **Evaluation push:** build a "golden set" of question→expected-case pairs and
  measure retrieval with **precision@k / recall@k / MRR**. This makes quality a
  number I can improve against — natural next milestone now that RAG is real.
- **Proactive support (bigger idea):** track conversation *themes* over time
  (memory, behavior, swallowing, safety…) and gently surface relevant support
  when topics shift toward later-stage care — always optional, never a clinical
  verdict.
- Smaller UX wins: clickable starter questions, inline source links, "download
  this conversation."

---

## Honest status / caveats
- Retrieval is **validated on a small (5-question) sample** — promising, but not
  yet a rigorous eval. That's exactly what the golden-set work is for.
- A few knowledge-base records have placeholder/empty source URLs (~21 sources
  still need DOIs resolved) — a known, queued cleanup, not a blocker.
- Not deployed publicly yet — runs locally; the Procfile makes hosting a small step.

---

## One-line framing for the meeting
"It went from a prototype script to a **deployable, source-citing web app with a
working retrieval pipeline** — and I have a clear, measurable plan to prove and
improve its answer quality next."
