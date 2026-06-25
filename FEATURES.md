# Feature ideas

A running list of things to maybe build. Add anything — no idea is too small.
Move items between sections as you decide. Status tags: 💡 idea · 🔜 next · 🔨 building · ✅ done

## 🔜 Near-term (small, high value)
- 💡 Suggested starter questions as clickable buttons in the chatbot UI
- 💡 Analyze the rest of the stored cases (run `analyze` with no `--limit`)
- 💡 "Download this conversation" button (save a chat as a text/markdown file)
- 💡 Show the cited case's link inline in the chat answer

## 💡 Knowledge & sources
- 💡 Add a second search profile (e.g. "speech & language in Alzheimer's")
- 💡 Pull from more sources (DementiaBank/ADReSS transcripts — see notes/curated-key-resources.md)
- 💡 Let the user paste their own case/notes to add to the knowledge base
- 💡 De-duplicate / merge near-identical cases automatically

## 💡 Chatbot quality
- 🔨 RAG retrieval — built (Voyage embeddings + cosine search; per-question top-k,
  with stuff-all fallback). Needs a live test with your `VOYAGE_API_KEY`.
- 💡 Remember context across sessions (save chat history)
- 💡 Tune the tone (warmer / more concise) — easy prompt edit in chatbot/prompts.py
- 💡 Add a "crisis resources" panel (hotlines, when to call for help)

## 💡 Bigger / later
- 💡 Deploy it online so others can use it (Render / Railway / Fly.io via the Procfile)
- 💡 User accounts / per-caregiver profiles
- 💡 Multi-language support
- 💡 Feedback buttons (👍/👎) on answers to improve the prompt over time

## 💡 Proactive support from chat trends
💡 Move the bot from reactive (waits for questions) to proactive (notices
patterns and offers relevant support).

- **Track topics, not volume.** Tag each question into themes — memory,
  behavior/agitation, communication, mobility, eating/swallowing, incontinence,
  safety, end-of-life. A *shift* over time from early-stage themes toward
  later-stage ones is a meaningful pattern; raw question count is not (it can
  rise for many unrelated reasons).
- **Offer support, never a verdict.** When a theme shift shows up, surface a
  gentle, optional nudge — e.g. *"We've been talking more about swallowing
  lately. Caregivers at this stage often find it helpful to loop in the care
  team and look into X. Want some options?"* Never assert that the person is
  "declining" — that's a clinical judgment the bot must route to professionals.
- **Opt-in & transparent.** It means remembering chat history over time, so make
  it something the caregiver turns on and can see/clear.
- **Buildable now-ish:** persist sessions → have Claude tag each question's
  theme → track themes over time → trigger a soft prompt on a shift. Medium
  effort, high payoff.

## 💡 Evaluation & metrics
> ✅ Prerequisite met: RAG retrieval is now built (Voyage embeddings + cosine
> search in `alz_finder/embeddings.py`), so retrieval is now a real, measurable
> step. The golden set + retrieval metrics are the natural next push.
- 💡 Retrieval metrics — measure how well the right cases are surfaced (e.g.
  precision@k, recall@k, MRR) once RAG retrieval is in place.
- 💡 A golden set — a curated set of test questions paired with the cases/answers
  that *should* be retrieved, used to score the retrieval metrics above.
- 💡 Generation metrics — measure answer quality (e.g. groundedness/faithfulness
  to the cited cases, relevance, safety-guardrail adherence, citation accuracy).

## 🧊 Parking lot (unsorted ideas)
- Patient profiles: let the user create a separate profile per Alzheimer's patient
  (e.g. one for Grandma) holding age, cognitive scores, Alzheimer's stage and type,
  comorbidities, etc. The chatbot pulls from the active profile to give more
  tailored, relevant answers.
- Recover the ~21 ID-less source URLs (in `output/unresolved_sources.txt`) by
  fetching each page and reading its `citation_doi`/`citation_title` meta tags,
  then resolving via Europe PMC — the deferred half of the CSV import.
