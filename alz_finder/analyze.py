"""Auto-analyze stored cases into the chatbot's structured knowledge.

For each case not yet in knowledge_base/analysis.jsonl, ask Claude to extract the
same caregiver-focused schema the hand-written analyses use, then append it.
Idempotent: existing paper_ids are skipped, so you can re-run after adding cases.

Requires ANTHROPIC_API_KEY in the environment (loaded from .env).
"""
from __future__ import annotations

import json
import os

import anthropic

from .store import Store

ANALYSIS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "knowledge_base", "analysis.jsonl"
)

# High-volume structured extraction → Sonnet by default (cheap, supports
# structured outputs). Override with --model. See README for the cost note.
DEFAULT_MODEL = "claude-sonnet-4-6"

# Cap source text fed to the model so a 90k-char full-text case stays affordable.
_MAX_TEXT_CHARS = 24000

SYSTEM = """You analyze a single published clinical case report and extract \
information useful for a chatbot that supports FAMILY CAREGIVERS of people with \
Alzheimer's disease and dementia.

Extract only what the case text supports — do not invent specifics. Write in \
plain, warm language a caregiver can understand. For each field:
- patient_profile: age, sex, dementia type/stage, key comorbidities.
- symptoms_behavior: presenting symptoms and behaviors (memory, agitation, mood, etc.).
- communication: how the patient communicates / language characteristics (or "Not detailed").
- progression: stage, timeline, how the case evolved (or "Not detailed").
- treatment_management: medications, therapies, interventions, caregiver-relevant management.
- caregiver_insights: 2-4 concrete, practical takeaways for a caregiver.
- example_qa: 1-3 realistic caregiver questions with grounded, safe answers \
(general/educational, encourage consulting clinicians; no specific drug doses).
- summary_text: one flowing paragraph combining the above (used for retrieval).
- caregiver_relevance: "high" or "moderate" if genuinely about Alzheimer's/dementia \
caregiving; "low" if tangentially related; "off-topic" if it is really about an \
unrelated condition or is a methods/lab paper with little caregiver value."""

SCHEMA = {
    "type": "object",
    "properties": {
        "patient_profile": {"type": "string"},
        "symptoms_behavior": {"type": "string"},
        "communication": {"type": "string"},
        "progression": {"type": "string"},
        "treatment_management": {"type": "string"},
        "caregiver_insights": {"type": "array", "items": {"type": "string"}},
        "example_qa": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"q": {"type": "string"}, "a": {"type": "string"}},
                "required": ["q", "a"],
                "additionalProperties": False,
            },
        },
        "summary_text": {"type": "string"},
        "caregiver_relevance": {
            "type": "string",
            "enum": ["high", "moderate", "low", "off-topic"],
        },
    },
    "required": [
        "patient_profile", "symptoms_behavior", "communication", "progression",
        "treatment_management", "caregiver_insights", "example_qa",
        "summary_text", "caregiver_relevance",
    ],
    "additionalProperties": False,
}


def _existing_ids() -> set[int]:
    ids: set[int] = set()
    if os.path.exists(ANALYSIS_PATH):
        with open(ANALYSIS_PATH) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        ids.add(json.loads(line)["paper_id"])
                    except (json.JSONDecodeError, KeyError):
                        pass
    return ids


def _case_text(row) -> str:
    body = row["full_text"] if row["text_source"] != "abstract" and row["full_text"] \
        else row["abstract"]
    body = (body or "")[:_MAX_TEXT_CHARS]
    return f"TITLE: {row['title']}\nYEAR: {row['year']}\n\n{body}"


def analyze(profile: str | None, min_score: int | None,
            model: str = DEFAULT_MODEL, limit: int | None = None) -> dict:
    """Analyze un-analyzed cases and append to analysis.jsonl. Returns a report."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    store = Store()
    try:
        rows = store.list_papers(profile=profile, min_score=min_score)
    finally:
        store.close()

    done = _existing_ids()
    todo = [r for r in rows if r["id"] not in done and (r["abstract"] or r["full_text"])]
    skipped_existing = len(rows) - len(todo)  # already analyzed (before applying limit)
    if limit:
        todo = todo[:limit]

    report = {"analyzed": 0, "skipped_existing": skipped_existing, "errors": 0,
              "by_relevance": {}}
    os.makedirs(os.path.dirname(ANALYSIS_PATH), exist_ok=True)
    with open(ANALYSIS_PATH, "a") as fh:
        for r in todo:
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=2048,
                    system=SYSTEM,
                    messages=[{"role": "user", "content": _case_text(r)}],
                    output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                )
                text = next(b.text for b in resp.content if b.type == "text")
                data = json.loads(text)
            except Exception as exc:
                report["errors"] += 1
                print(f"  [{r['id']:>4}] ERROR: {exc}")
                continue

            # Stamp identifying/citation metadata from the DB (not model-generated).
            data.update({
                "paper_id": r["id"], "title": r["title"], "year": r["year"],
                "url": r["url"], "doi": r["doi"], "oa_status": r["oa_status"],
                "source_depth": r["text_source"], "generated_by": model,
            })
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")
            fh.flush()
            rel = data["caregiver_relevance"]
            report["by_relevance"][rel] = report["by_relevance"].get(rel, 0) + 1
            report["analyzed"] += 1
            print(f"  [{r['id']:>4}] {rel:<9} {r['title'][:60]}")
    return report
