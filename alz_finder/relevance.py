"""Score a case study for relevance to a *caregiver-support* Alzheimer's chatbot.

Relevance is judged on four dimensions the user cares about:
  - symptoms & behavior
  - how the patient communicates
  - disease progression
  - treatment & management

A paper must also be genuinely about Alzheimer's / dementia (the "core" gate) and
be a case report. Score = number of the four dimensions present (0-4); papers
that fail the core gate score 0.
"""
from __future__ import annotations

import re

from .normalize import Paper

# Must mention the condition at all, or it isn't relevant to this chatbot.
CORE = [
    "alzheimer", "dementia", "cognitive impairment", "cognitive decline",
    "neurocognitive", "mci",
]

DIMENSIONS: dict[str, list[str]] = {
    "symptoms": [
        "agitation", "aggression", "anxiety", "depression", "apathy",
        "delusion", "hallucination", "wandering", "sleep", "behavioral",
        "behavioural", "psychiatric", "bpsd", "mood", "confusion",
        "memory loss", "disorientation", "irritability", "restless",
    ],
    "communication": [
        "speech", "language", "aphasia", "word-finding", "word finding",
        "naming", "verbal", "communication", "conversation", "repetition",
        "anomia", "discourse", "fluency",
    ],
    "progression": [
        "progression", "progressive", "stage", "decline", "longitudinal",
        "follow-up", "follow up", "deteriorat", "course", "onset",
        "over months", "over years", "trajectory", "worsening",
    ],
    "treatment": [
        "treatment", "therapy", "therapeutic", "medication", "donepezil",
        "memantine", "rivastigmine", "galantamine", "intervention",
        "management", "caregiver", "care", "pharmacolog", "non-pharmacolog",
        "rehabilitation", "support",
    ],
}


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(t in text for t in terms)


def is_case_report(paper: Paper) -> bool:
    return "case report" in (paper.pub_types or "").lower()


def score_paper(paper: Paper) -> tuple[int, str]:
    """Return (score 0-4, comma-joined matched dimension names)."""
    text = f"{paper.title} {paper.abstract}".lower()
    if not _contains_any(text, CORE):
        return 0, ""
    matched = [name for name, terms in DIMENSIONS.items() if _contains_any(text, terms)]
    return len(matched), ",".join(matched)
