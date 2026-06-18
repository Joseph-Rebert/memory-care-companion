# Case analysis for the caregiver-support chatbot

Analysis of the strong-match Alzheimer's case studies (relevance score ≥ 2),
distilled into caregiver-relevant insights + example Q&A. Machine-readable
version: `knowledge_base/analysis.jsonl` (also folded into `cases.jsonl`).

I applied caregiver-relevance judgment **on top of** the keyword score: the
keyword score is good at ranking, but a few high-scoring papers are off-topic for
a caregiver bot. Those are listed at the bottom with reasons.

## Analyzed cases (13) — by relevance

### High relevance (4) — core caregiver material
- **#18 Frontal-variant AD presenting as psychiatric illness** — behavior/mood/
  psychosis can precede memory loss; antipsychotics caused movement side effects;
  caregiver collateral history was key to diagnosis.
- **#22 Behavioral variant of AD** — atypical AD led by behavior, with its own
  diagnostic criteria and management principles.
- **#1 Linguistic-cognitive intervention (early-onset AD)** — weekly non-drug
  speech-language therapy helped maintain communication despite progression.
- **#3 Logopenic variant PPA (language-led AD)** — word-finding/naming failure as
  the first sign; donepezil + speech-language rehab gave partial benefit.

### Moderate relevance (9) — useful, more specific situations
- **#16 PSEN1 early-onset AD (onset age 29), familial** — genetics/genetic
  counseling; irritability and seizures in the course.
- **#31 Lecanemab → urinary retention** — adverse effects of newer anti-amyloid
  drugs; watch and report new symptoms after infusions.
- **#32 Agitation + urinary retention (acupuncture)** — co-occurring agitation and
  physical symptoms; complementary therapy coordinated with medical care.
- **#25 Autotopagnosia in AD** — unusual brain-based symptom (can't locate body
  parts); not non-cooperation.
- **#9 Myoclonus in AD** — sudden muscle jerks; may flag seizure risk; treatable.
- **#17 B12-deficiency rapidly progressive dementia** — reversible mimic of AD;
  rapid decline should trigger a search for treatable causes.
- **#12 Feeding-tube complication in advanced AD** — late-stage care; watch for
  non-verbal signs of illness in patients who can't describe pain.
- **#6 Behavioral abnormalities in PD / Lewy body dementia** — Capgras and other
  misidentification syndromes, hallucinations (related dementias, not AD itself).
- **#30 Wernicke's unmasking PSP + AD** — sudden confusion/falls can be a treatable
  acute illness on top of dementia, not just "progression."

## Cross-cutting themes for the chatbot
1. **Behavior can come before memory** — several atypical AD variants present with
   psychiatric/behavioral symptoms first (#18, #22).
2. **Language-led AD is real and treatable** — speech-language rehab helps (#1, #3).
3. **"Sudden worse" ≠ just progression** — look for treatable acute or reversible
   causes (#30, #17, #9).
4. **Medication vigilance** — both classic (antipsychotics, #18) and newer
   (lecanemab, #31) drugs carry watch-for side effects.
5. **Advanced-stage practicalities** — non-verbal pain signs, feeding tubes (#12).
6. **Unusual symptoms are brain-based, not willful** — autotopagnosia (#25),
   misidentification delusions (#6).

## Strong-match cases I did NOT analyze (off-topic for a caregiver bot)
Kept in the searchable corpus but excluded from the distilled caregiver analysis:
- **#34 Dual-AI consultation methods paper** — about cross-validating LLMs on
  imaging data; a methods paper, not caregiving.
- **#37 Iatrogenic AD from cadaveric growth hormone** — research/postmortem prion-
  clinic series; little day-to-day caregiver value.
- **#4 FTD (MAPT variant)**, **#5 FTLD (GRN variants)**, **#35 PSEN1 pathogenicity
  lab study** — genetics/lab-focused; minimal caregiver guidance.
- **#11 Sneddon syndrome**, **#14 lymphovenous-anastomosis surgical complication**,
  **#27 functional propriospinal myoclonus** — niche conditions/complications,
  not general AD caregiving.

> These exclusions are judgment calls — the raw cases remain in `cases.jsonl` if
> you want to include them later. To re-tune what counts as relevant, edit
> `alz_finder/relevance.py`.
