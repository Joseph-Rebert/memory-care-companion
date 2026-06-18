# Curated key resources (manual pass)

Hand-picked, high-value starting points for the Alzheimer's chatbot, beyond what
the automated search pulls. Grouped by what they're useful for.

## ⭐ Most important: real patient language datasets
For a chatbot, the single most valuable resource is **actual dementia patient
speech/transcripts**, not just papers about them.

- **DementiaBank (Pitt Corpus)** — the canonical corpus of transcribed
  spontaneous speech from people with Alzheimer's/dementia and healthy controls
  (e.g. "Cookie Theft" picture descriptions). Access is gated (research
  agreement) but it's the gold standard for realistic patient language.
  https://dementia.talkbank.org/
- **ADReSS / ADReSSo challenge datasets** — balanced, benchmarked subsets of
  DementiaBank used in the major AD-from-speech challenges; good for grounding
  expected linguistic patterns.

## Chatbots / LLMs for dementia care (design + method guidance)
- **Frontiers in Dementia (2024): "Introduction to Large Language Models (LLMs)
  for dementia care and research"** — broad orientation to applying LLMs here.
  https://www.frontiersin.org/journals/dementia/articles/10.3389/frdem.2024.1385303/full
- **PDC30 Chatbot (JMIR Aging, 2025)** — GPT-4o chatbot with a "personality
  agent" constraining behavior to a caregiving guidebook; useful pattern for
  grounding/guardrails. https://aging.jmir.org/2025/1/e63715
- **LLM-powered chatbots assisting elderly people: systematic review (2025)** —
  landscape + evaluation criteria.
  https://link.springer.com/article/10.1007/s13721-025-00698-9
- **LUMEN: conversational AI to streamline dementia assessments** — pattern for
  structured pre-clinical data collection via dialogue.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12242181/
- **Evaluation of ChatGPT responses to dementia patients' information needs** —
  what off-the-shelf models get right/wrong here.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11069588/

## NLP detection of AD from language (informs realistic symptom modeling)
- **Detecting Alzheimer's Disease Using NLP of Referential Communication Task
  Transcripts (J. Alzheimer's Dis., 2022)** — BERT-based; what linguistic
  markers distinguish AD speech. https://pubmed.ncbi.nlm.nih.gov/35213368/
- **Optimization of an NLP approach using GPT embeddings (Brain Sci., 2024)** —
  AI transcription + GPT embeddings for AD detection.
  https://www.mdpi.com/2076-3425/14/3/211

## How these feed the chatbot
- Use **DementiaBank/ADReSS** to learn *how patients actually talk* (word-finding
  pauses, repetition, simplified syntax) → realistic persona + input handling.
- Use the **NLP-detection papers** for the concrete linguistic markers to expect.
- Use the **chatbot/LLM-care papers** for interaction design, grounding to
  vetted content, and safety/guardrail patterns.

> Reminder: case reports and datasets are de-identified but copyrighted/licensed.
> Use for design insight; respect each source's access terms (DementiaBank
> requires a signed agreement).
