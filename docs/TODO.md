# TODO — deferred decisions for humanness scoring

Backlog of decisions deferred out of the current milestone. Each item maps to a
`PENDING` decision or fidelity caveat in [`humanness-scoring.md`](./humanness-scoring.md).
None of these block the current promb-based score; they define the gap between our
lightweight approximation and faithful OASis/BioPhi.

---

## D6 — Per-chain reference (R2 fidelity defect, = caveat C2)

**Problem.** R2 requires each chain to be scored against its **own chain-type**
repertoire (VH→heavy, VL→light). promb cannot do this:

- It ships a **single pooled** peptide set
  (`resources/OASis_9mers_v1_10perc_subjects.txt.gz`, ~5.7M 9-mers, one `frozenset`).
- `PrombDB.compute_peptide_content(seq)` takes **no chain-type argument** — there is
  no API or data path to select a per-chain reference.
- The `≥10%`-of-subjects prevalence threshold is computed **over the pool**, not within
  each chain type. The real OASis computes prevalence *per chain type*.

**Impact.** Light-chain scores carry a systematic but **unmeasured** bias (the pool is
heavy-skewed; the prevalence cutoff is mixed across chain types). Not "garbage" — light
9-mers are present — but not faithful to OASis. Magnitude unknown.

**Routing is already solved.** The workflow separates chains and carries a chain-id
column (commits `422b47f`, `9d087e9`), so we already know each row's chain type. What is
missing is a per-chain reference, not the ability to route.

**Options:**

- **A — Fix promb (chain-split DB).** Ship two files (`human-oas-heavy`,
  `human-oas-light`); route each row by chain-id in `software/src/main.py`. Code change
  is trivial (`init_db` already loads arbitrary `.txt.gz`). The hard part is **building
  the two files faithfully**: needs raw OAS (or BioPhi's internal DB), split by chain,
  prevalence recomputed *within* chain type, thresholded at ≥10%. Effectively
  reimplements part of BioPhi's DB build. Solves D6 only — **not** D5.
- **B — Move to full BioPhi.** Ships the real OASis DB: per-subject prevalence split by
  chain type, multiple thresholds, **and** the calibrated percentile. Closes **D6 + D5 +
  C1 + C2** at once. Cost: heavier deps (ANARCI/HMMER for numbering + chain detection;
  Sapiens/torch if humanization is added), bigger image, and a contract question of who
  owns chain-type detection (our upstream vs BioPhi's ANARCI).

**Recommendation.** D5 and D6 point the same way: promb is a lightweight approximation;
faithful OASis = BioPhi. The real fork is **"is the promb approximation good enough for
this milestone?"** — if yes, do nothing now but **label the number honestly** and keep
C2 flagged; if "do it right", go **B** (it closes D5+D6 together). Option A is usually a
false economy — heavy data work for half the result — justified only if we explicitly
want per-chain *without* the percentile and want to avoid the BioPhi/ANARCI dependency.

**Suggested next step (cheap, decision-informing).** Quantify the light-chain bias:
run a set of known-human VL sequences through the pooled DB and inspect the score
distribution, so D6 is decided on a number rather than "may be less faithful".

**Owner:** Eng (route) + Product (acceptability). **Status:** PENDING.

---

## D5 — Which number do we expose (identity vs percentile, = caveat C1)

**Problem.** We currently emit raw OASis **identity** × 100 (`fraction × 100`, see
`humanness()` in `software/src/main.py`). BioPhi exposes the calibrated **percentile**
(the interpretable "~5–7% murine / ~80% human"), which requires BioPhi's 544-mAb
calibration — promb alone cannot produce it.

**Impact.** Our numbers are **not comparable** to published "% human" percentiles. Any
UI/report wording must not imply percentile semantics.

**Decision.** Stay on promb (identity, labeled honestly) **vs** adopt BioPhi (percentile).
Coupled to D6 — Option B above resolves both.

**Owner:** Product + Eng. **Status:** PENDING.

---

## D4 — Per-residue "non-human positions" deliverable (R7)

**Problem.** The idea note promised per-residue non-human flags. The OASis score is
**peptide-level** (9-mer membership) and does not natively attribute humanness to a
single position.

> Note: promb *does* ship an approximate per-residue method
> (`PrombDB.compute_positional_likelihood`, `db.py:341`) derived from nearest-peptide
> PSSMs — worth evaluating before reaching for a new tool. The spec (R7) points instead
> at **Sapiens** (Merck, same family as promb/BioPhi → most consistent) or **AntPack**
> (`calc_per_aa_probs`, lighter deps) as the canonical residue-level scorers.

**Why it's wanted.** A scalar says *whether* there's a problem; a per-residue map says
*where* — directly actionable for humanization (back-mutation candidates), explains the
score, and enables a sequence heatmap in the UI.

**What's missing (not just a column):**

1. New tool/dependency (Sapiens → likely torch + weights; AntPack → lighter).
2. New output contract: a **variable-length array per row** (or a normalized
   `position → score` table) instead of today's single `humanness_score` scalar
   (`main.py` output is key + chain-id + one Float). Needs positional numbering
   (IMGT/Kabat via ANARCI) for cross-clonotype comparability.
3. New UI: a sequence/heatmap viewer, not another table column.
4. Reconciling **two** humanness numbers from **different** models (promb 9-mer scalar vs
   per-residue map) so users aren't confused by "score 85 but half the residues red".

**Scope.** Out of scope for the score itself; a separate feature on its own pass.

**Owner:** Product + reviewer (scope/timing/tool). **Status:** PENDING.
