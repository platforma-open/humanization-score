# Humanness Scoring — Migration Plan (Current → Correct)

This is the technical plan to move the block from its current (incorrect) implementation to
the behavior defined in [`humanness-scoring-correct-behavior.md`](./humanness-scoring-correct-behavior.md).
Read that document first — it is the biological source of truth; this plan only describes
*how* to get the code there.

The plan is phased so each phase is independently reviewable and (mostly) independently
shippable. Phases are ordered by dependency: the data contract (Phase 1) must be agreed
before the workflow (Phase 3) and Python (Phase 2) can be rewritten against it.

---

## 0. Summary of the gap

| Layer | File | Current behavior | Target behavior |
|---|---|---|---|
| Scoring tool | `software/src/main.py` | Concatenates **every** column ending in `" aa"`, in column order, into one string per row; one score per row | Scores **one sequence per call/row = one full variable domain of one chain**; never concatenates across regions or chains |
| Data assembly | `workflow/src/main.tpl.tengo` | Per modality, hand-builds headers that duplicate the full sequence, drop FR4, keep only FR1 (scFv), merge chains | Per modality, emits **one full variable-domain sequence per chain** (FR1–FR4, natural order), each chain separate |
| Output mapping | `workflow/src/clonotype-process.tpl.tengo` | One score column keyed by `clonotypeKey` | One score **per chain type** (Heavy/Light), scoring the primary-rank rearrangement; secondary-rank → `null` |
| Block model | `model/src/index.ts` | Selectors accept any VDJ aminoacid anchor (incl. TCR); single score column | Reject TCR; expose per-chain score columns; fix single-cell table |
| Tests | `software/tests/*`, fixtures | Fixtures encode the wrong layout (interleaved chains, only FR1, no FR4) → green on wrong behavior | Fixtures encode full variable domains per chain; tests assert correct scoring unit |

---

## 1. Phase 1 — Define and freeze the data contract

Nothing else can be correct until we pin down, precisely, **what one "scoring unit" is and how
it arrives at the Python tool**. This is the highest-leverage decision; do it first and write
it down.

### 1.1 The scoring unit

One scoring unit = the **complete variable domain of one chain**: `FR1+CDR1+FR2+CDR2+FR3+CDR3+FR4`
in N→C order (consumed as the already-assembled `VDJRegionInFrame` column, 1.2). Each unit
carries:
- a **clonotype key** (the existing `clonotypeKey` / `scClonotypeKey` axis value),
- a **chain identity** (single-cell: chain **type** Heavy/Light = `scClonotypeChain` A/B, and
  **rank** primary/secondary = `scClonotypeChain/index` — two orthogonal axes, see 1.2),
- the **amino-acid sequence** of the full variable domain.

### 1.2 How to obtain the full variable domain

> **Resolved against the upstream producer** (`mixcr-clonotyping`,
> `workflow/src/calculate-export-specs.lib.tengo`). The concrete domain keys below come from
> that block — it is the only realistic source of these columns.

The full variable domain is exported by MiXCR as a **single amino-acid column** keyed
`pl7.app/vdj/feature == "VDJRegionInFrame"`, alphabet `aminoacid`. ⚠️ **For the amino-acid
column the feature is always the in-frame variant** — the producer rewrites `VDJRegion` →
`VDJRegionInFrame` for the `aminoacid` alphabet (`calculate-export-specs.lib.tengo:18-21` define
`inFrameFeatures`, applied at `:505`, written to `pl7.app/vdj/feature` at `:534`). Plain
`"VDJRegion"` appears only on the **nucleotide** column. So an aa-column selector/guard **must
match `"VDJRegionInFrame"`** and must not rely on the literal `"VDJRegion"`. This column **is**
FR1–CDR1–FR2–CDR2–FR3–CDR3–FR4 already assembled, in natural order. **Use it directly as the one
scoring unit.** Do **not** add the individual region columns on top of it — that is the current
bulk duplication bug.

The source priority is therefore:

1. **`VDJRegion` (`/VDJRegionInFrame`) amino-acid column present** → score it directly. This is
   the normal, correct path. (One per chain in single-cell — see 1.4 and the constraints
   below.)
2. **No `VDJRegion` column** → the full domain is **not available** and the chain is **not
   scoreable** → emit `null` (correct-behavior §6). Do **not** reconstruct from individual
   region pieces and do **not** fall back to CDR3.

> **Why no fragment reconstruction:** MiXCR only emits the individual FR/CDR region columns
> for some presets, and even then completeness is not guaranteed (regions can be
> `region_not_covered`). The reliable, already-ordered full domain is the `VDJRegion` column.
> Reconstructing from fragments reintroduces exactly the ordering/completeness risks this
> migration is removing. If a future need arises, reconstruction can be added as an explicit,
> fixed-order (`FR1,CDR1,FR2,CDR2,FR3,CDR3,FR4`), all-or-null step — but it is **not** the
> default path.

#### Critical data-availability constraints (discovered in the producer)

These shape what is even *possible* and must be reflected in the contract:

- **Two orthogonal single-cell axes — do not conflate them.** The producer emits **four**
  per-chain tables per receptor via two independent nested loops in `process.tpl.tengo`: the
  outer `for chainIdx in [0,1]` (`:694`, `A`=Heavy, `B`=Light, ordered by diversity per `:40`)
  and the inner `for isPrimary in [true,false]` (`:728`). So **Heavy-primary, Light-primary,
  Heavy-secondary, Light-secondary** all exist (cf. `process-single-cell.tpl.tengo` outputs
  `a1/a2/b1/b2`). The two axes are:
  - `pl7.app/vdj/scClonotypeChain` = `A`/`B` = **chain type** (IG: `A`=Heavy, `B`=Light).
  - `pl7.app/vdj/scClonotypeChain/index` = `primary`/`secondary` = **rearrangement rank**, NOT
    chain type.
- **The CDR3-only restriction keys on `index = secondary`, regardless of chain type.** The
  stripping at `process.tpl.tengo:687-693` (keep only `aaSeqCDR3`) is selected at `:767` by
  `isPrimary ? full-columns : CDR3-only`. Therefore:
  - **Heavy-primary AND Light-primary** both carry the full `VDJRegionInFrame` → both are scored.
  - **Heavy-secondary AND Light-secondary** are both CDR3-only → both are `null` (not a CDR3
    score).
  - **Key the null rule on `index == "secondary"`** — never on Heavy-vs-Light. (The earlier
    framing "only the primary chain carries the full domain / secondary = light" was wrong:
    Light-primary is full-domain, Heavy-secondary is CDR3-only.)
- **Availability depends on the upstream assembling feature.** `VDJRegion` is present only when
  the clonotyping run assembled by the full region. If it assembled by `CDR3`, *no* chain has a
  full domain. **DECIDED:** in that case the block **hard-fails** with a clear message —
  *"Humanness scoring requires sequences assembled over the full variable region (VDJRegion);
  this dataset was assembled by CDR3. Re-run clonotyping assembled by VDJRegion."* — rather than
  emitting nulls or scoring CDR3. This is enforced both in the input selectors (a CDR3-assembled
  dataset should not be offered) and as a workflow guard (`ll.panic`).
- **Chain identity mapping:** `pl7.app/vdj/scClonotypeChain` is `"A"`/`"B"` where **A is the
  more diverse chain** — for IG that is **Heavy** (`receptorInfos.IG.chains = ["IGHeavy","IGLight"]`),
  so `A → Heavy`, `B → Light`. (The current code's `A?Heavy:Light` mapping is correct on this
  point.)

### 1.3 Where the ordering/assembly logic lives

**Move sequence assembly out of header-string conventions and into explicit, typed logic.**
Two acceptable designs (pick one and document it):

- **(A) Assemble in the workflow (tengo), pass one sequence column per chain to Python.**
  Python becomes trivial: "score the one sequence column you are given." Cleanest separation;
  the workflow owns biology, Python owns scoring.
- **(B) Pass labelled region columns to Python and assemble there.** Python must then know the
  region order and chain grouping. More logic in Python, but easier to unit-test in isolation.

**Recommendation: Design (A).** It keeps the scoring tool dumb and side-effect-free, makes the
"one chain in, one score out" rule structural rather than conventional, and removes the entire
class of "header string parsed wrong" bugs. The rest of this plan assumes (A); note where (B)
would differ.

### 1.4 Single-cell chain representation

For single-cell, decide how per-chain scores are represented downstream:

- **Recommended:** one score **column per chain type**, keyed by the existing `scClonotypeKey`
  axis, with the chain type encoded in the column's domain + label (e.g.
  `"Humanness Score, Heavy"` / `"Humanness Score, Light"`). Only the **primary**-rank
  rearrangement of each type is scored; secondary-rank is `null` (1.2). This keeps the table
  one-row-per-clonotype and naturally fixes the broken single-cell table view.
- *Alternative:* introduce a chain axis (one row per clonotype×chain). More normalized but a
  bigger change to the table/graph UI and to the histogram. Avoid unless there's a reason.

(scFv VH/VL representation is **descoped** for now — see Phase 3 and the scFv note in
correct-behavior §4.4; the current upstream emits no scFv data.)

**Deliverable of Phase 1:** a short written contract (append to the correct-behavior doc or a
`CONTRACT` section here) specifying: scoring unit, source priority (1.2), assembly location
(1.3 = A), and chain representation (1.4 = per-chain columns). Get it reviewed by the domain
reviewer before coding.

---

## 2. Phase 2 — Rewrite the scoring tool (`software/src/main.py`)

Goal: Python scores **one sequence per row**, where each row already represents one full
variable domain of one chain. No cross-column concatenation.

### 2.1 Changes

- **Delete** `_identify_sequence_columns()` and the `pl.concat_str([...])` logic
  (`main.py:55-89`). That "glue every `aa` column" behavior is the core bug and must go.
- New input contract: a Parquet with a key column (`clonotypeKey`, plus a chain identifier
  column if present) and **exactly one sequence column** (e.g. `sequence aa`). Score that
  column row-by-row with the existing `humanness()` function (which is correct as-is:
  9-mer window, `human-oas`, rescaled 0–100, `null` if `< _MIN_WINDOW`).
- Preserve the robustness behaviors: short sequence → `null`; scoring exception → `null`;
  never fail the whole run on one bad row.
- Keep the output shape: key column(s) + `humanness_score`. If a chain-id column is present,
  carry it through to the output so the workflow can map scores back to chains.

### 2.2 Notes

- The `humanness()` function and the promb `human-oas` setup do **not** change — the method is
  correct; only *what we feed it* changes.
- Under Design (B) instead: Python would receive region columns, validate the full set is
  present per chain, assemble in fixed order, then score — but prefer (A).

### 2.3 Acceptance

- Given a single full-VH sequence, the score equals scoring that VH directly with promb (no
  duplication).
- Given a CDR3-only row, output is `null` (not a CDR3 score).
- Multiple sequence columns in the input is now a **contract violation** — fail fast with a
  clear error rather than silently concatenating.

---

## 3. Phase 3 — Rewrite data assembly (`workflow/src/main.tpl.tengo`)

This is the largest change. The current `prepare`/`body` builds a single wide table with
hand-written headers; replace it with per-chain full-variable-domain assembly.

### 3.1 `prepare` (the bundle queries, `main.tpl.tengo:13-54`)

- Collect the **full-domain amino-acid column** directly: `pl7.app/vdj/sequence`, alphabet
  `aminoacid`, `pl7.app/vdj/feature == "VDJRegionInFrame"` (1.2). This is the scoring unit — we
  do **not** reconstruct it from region pieces.
- For single-cell, also collect the chain-axis domains `pl7.app/vdj/scClonotypeChain` (A/B) and
  `pl7.app/vdj/scClonotypeChain/index` (primary/secondary) so each VDJRegion column can be mapped
  to a chain type and rank.
- Collect the domain needed for the **TCR guard** (1.2 / Phase 6): bulk `pl7.app/vdj/chain`
  (`IG*` vs `TR*`), single-cell `pl7.app/vdj/receptor` (`IG` vs `TCRAB`/`TCRGD`).
- The individual FR/CDR **region columns** are needed only if/when we add per-residue annotation
  (Phase 7) — they are **not** collected for sequence assembly. Likewise the **CDR annotations**
  bundle (`pl7.app/vdj/sequence/annotation`) is Phase-7-only and can otherwise be dropped.

### 3.2 `body` — replace the modality branches

Implement one coherent assembly that selects the **`VDJRegionInFrame` amino-acid column(s)** and
produces one single-sequence table per scoring unit. **No fragment reconstruction anywhere** —
this is the frozen §1.2 contract and matches correct-behavior §3 ("no fragment gluing").

- **Bulk / VHH (single chain):**
  - Use the `VDJRegionInFrame` aa column directly as the single sequence to score. **Stop** — do
    not append CDR/FR fragments (removes the duplication + FR4-drop + ordering bug at
    `main.tpl.tengo:126-158`).
  - If no `VDJRegionInFrame` column exists (CDR3-assembled dataset) → **hard-fail** per §1.2 with
    the re-run-clonotyping message. Never reconstruct from region pieces; never fall back to CDR3.
  - Output: one sequence → one score per clonotype.

- **Single-cell:**
  - For each chain **type** (Heavy=`A`, Light=`B`), take its **primary-rank** `VDJRegionInFrame`
    column and score it directly. Emit one sequence column **per chain type**, tagged with chain
    identity. Never concatenate across chains (removes the merge bug and the CDR3-only
    fallthrough at `main.tpl.tengo:87-125`).
  - **Secondary-rank** rearrangements are CDR3-only by construction (§1.2) → emit `null`, do not
    score. Key this on `index == "secondary"`, **not** on Heavy-vs-Light.
  - If the dataset is CDR3-assembled (no `VDJRegionInFrame` on the primary chains either) →
    hard-fail per §1.2.

- **scFv: descoped for now.** The current upstream (`mixcr-clonotyping`) emits no scFv data, and
  the existing scFv branch (`main.tpl.tengo:91-107`, keyed on `pl7.app/vdj/scFv-sequence`) is
  **dead code** against a column that block never produces. **Delete that dead branch** as part
  of this rewrite. Do not implement scFv VH/VL handling until the scFv producer/column contract
  is confirmed (correct-behavior §4.4). If/when it exists, the same "use the full-domain column
  directly, split VH vs VL by chain identity, never reconstruct" rule applies.

- **No region-ordering / concatenation logic is needed at all** in the new design — because we
  consume the already-assembled `VDJRegionInFrame` column rather than gluing regions. (The fixed
  region order `FR1,CDR1,FR2,CDR2,FR3,CDR3,FR4` is relevant only to the deferred, explicitly
  optional reconstruction path of §1.2, which is **not** used here.)

### 3.3 Output of `body`

Under the recommended per-chain-column design, `body` produces a small set of single-sequence
tables (one per chain), each fed to the scoring template (`clonotype-humanness.tpl.tengo`) and
mapped to a distinct score column. The scoring template
(`clonotype-humanness.tpl.tengo`) itself needs no change beyond possibly running once per chain
table (or once over a tall table with a chain key — decide with the contract).

### 3.4 Acceptance

- Bulk: emitted table for a clonotype contains exactly one sequence = the full VH
  (`VDJRegionInFrame`), present once.
- Single-cell: one sequence unit per chain type (Heavy-primary, Light-primary), none
  concatenated; secondary-rank rows produce `null`.
- CDR3-assembled dataset: hard-fails with the re-run message (no scoring attempted).
- scFv: descoped (dead branch deleted); no scFv assertions until the producer contract exists.

---

## 4. Phase 4 — Output mapping & per-chain scores (`workflow/src/clonotype-process.tpl.tengo`)

- Currently emits one `humanness_score` column; the column array is at
  `clonotype-process.tpl.tengo:35-55`. Extend to emit **one score column per chain type**
  (Heavy/Light) for single-cell, with chain type encoded in the column domain
  (`pl7.app/vdj/scClonotypeChain`) + `pl7.app/label` (per 1.4).
- Each chain column keeps the existing score annotations (`pl7.app/isScore`, ranking decreasing,
  format, description) — just differentiated by chain type in `pl7.app/label` and the chain
  domain key.
- Preserve the blockId domain injection (`:57-65`) and trace construction (`:94-101`) for every
  emitted column.
- Bulk/VHH stays single-column (no chain split) — backward compatible.

**Acceptance:** the histogram and table see per-chain score columns for single-cell; bulk
unchanged.

---

## 5. Phase 5 — Block model & UI (`model/src/index.ts`, `ui/`)

- **Selectors (`index.ts:55-67`):** today they match any anchor with `pl7.app/sampleId` +
  clonotype key. Tighten so only **immunoglobulin (BCR/antibody)** datasets are offered (see
  Phase 6); TCR datasets must not appear as valid input options.
- **Table output (`pt`, `index.ts:100-118`) — diagnose, then fix.** Don't assume the cause.
  - *5a (diagnose):* load a current single-cell (`scClonotypeKey`) dataset, reproduce the broken
    table, and determine which mechanism is responsible — (a) the single merged score column
    being meaningless for multi-chain clonotypes, or (b) the enrichment selector keyed on
    `pCols[0].spec` (`index.ts:107-117`) failing to resolve against the `scClonotypeKey` axis.
  - *5b (fix):* re-point `anchors.main` at the Phase-4 per-chain columns; if (b), also adjust the
    selector/anchor so it resolves against `scClonotypeKey`. (Per-chain columns alone do **not**
    fix a selector-resolution failure, so confirm the mechanism first.)
- **Histogram (`histogramPf`) — concrete spec, not just "decide".** Phase 4 emits multiple score
  columns all sharing `spec.name == "pl7.app/humannessScore"`, differentiated only by chain
  domain. The current consumer picks the **first** match by `spec.name`
  (`ui/.../HistogramPage.vue`, `pcols.find(p => p.spec.name === HUMANNESS_SCORE_COLUMN)`) and
  `defaultGraphStateHistogram` (`index.ts:39-51`) is a single-series template — so it would
  silently bin one arbitrary chain. Fix: add a per-chain selector/series (let the user pick or
  split by chain), default to the **Heavy** chain; disambiguate the `.find()` by the chain domain
  since `spec.name` is no longer unique.
- **UI package (`ui/`):** verify the table/graph components render multiple score columns;
  adjust labels.

**Acceptance:**
- single-cell table shows one row per clonotype with separate Heavy/Light score columns
  populated (no empty/unresolved column);
- single-cell histogram renders per-chain distributions selectable/splittable by chain, default
  Heavy;
- a TCR dataset offers no valid input (or shows a clear "not applicable").

---

## 6. Phase 6 — Reject TCR input

TCR must be refused (correct-behavior §5). Defense in depth — implement at two layers. The
distinguishing keys are now known (from `mixcr-clonotyping`):

- **Bulk:** the `clonotypeKey` axis carries domain `pl7.app/vdj/chain` whose value is the
  producer's `chainInfos` **key** ∈ `{IGHeavy, IGLight, TCRAlpha, TCRBeta, TCRGamma, TCRDelta}`
  (set at `process.tpl.tengo:339` `for chain in chains` → `axisByClonotypeKeyGen(chain)` →
  `calculate-export-specs.lib.tengo:1019`). Ig = `{IGHeavy, IGLight}`; TCR = the `TCR*`-prefixed
  values. ⚠️ **Not** `IGH/IGK/IGL/TRA…` — those are the `discreteValues` of the separate
  `topChains` *column*, a different thing from this axis-domain value.
- **Single-cell:** the `scClonotypeKey` axis carries domain `pl7.app/vdj/receptor` ∈
  `{IG, TCRAB, TCRGD}`. Ig = `IG`; TCR = anything else.

1. **Input selectors (`model/src/index.ts`):** constrain the input options so only Ig datasets
   are selectable — require `pl7.app/vdj/receptor == "IG"` (single-cell) / `pl7.app/vdj/chain`
   in `{IGHeavy, IGLight}` (bulk) on the anchor.
2. **Workflow guard (`main.tpl.tengo` body):** if a TCR dataset slips through, detect it from
   the same domain keys and `ll.panic` with a clear message ("Humanness scoring applies to
   antibodies only; TCR input is not supported") rather than emitting a meaningless score.

**Acceptance:** TCR dataset → not offered as input and, if forced, fails fast with a clear
message. Antibody datasets unaffected.

---

## 7. Phase 7 — Per-residue annotation (stretch / per idea doc)

The original idea promises per-residue non-human flags. This is **not** in the current
implementation. Scope it as a follow-up unless required now:

- Either keep promb (peptide content only — no per-residue) and defer, or evaluate AntPack
  (probabilistic per-residue humanness) noting its possible license terms.
- If implemented, emit a per-position annotation column aligned to each chain's variable domain.

Mark this phase optional; it does not block the correctness fix.

---

## 8. Phase 8 — Tests & fixtures (`software/tests/`)

The current fixtures **bless the bug** — they must be rewritten, not patched.

- `tests/data/sequences.tsv` (bulk): replace `CDR1/CDR2/CDR3/FR1` layout with a single
  **full variable-domain** sequence column per clonotype.
- `tests/data/sequences_sc.tsv` (single-cell): replace the interleaved
  `Heavy CDR1 / Light CDR1 / … / FR1` layout with **per-chain full variable domains** — one
  full-domain sequence unit for Heavy-primary and one for Light-primary, plus a secondary-rank
  row that is CDR3-only (asserted `null`).
- Add a **CDR3-only fixture** asserting the result is `null` (and the workflow-level
  CDR3-assembled dataset asserts hard-fail).
- Add a **TCR fixture** asserting rejection.
- *(scFv fixture descoped — no scFv producer; add only once the scFv contract exists.)*
- Rewrite `tests/test_integration.py` to assert: one full sequence → score equals direct promb
  score; no duplication; FR4 present; chains scored separately; secondary-rank / CDR3-only → null.
- Add a unit test for the Python contract violation (multiple sequence columns → error).

**Acceptance:** new tests fail against the old code and pass against the new code (prove they
test the requirement, not the implementation).

---

## 9. Phase 9 — Versioning, changeset, rollout

- This is a **behavior-breaking** change to scores (existing results become invalid). Bump the
  block version accordingly and write a clear `.changeset` entry explaining that previously
  computed humanness scores were incorrect and must be recomputed.
- Bump the software package version (`software/` is at `0.3.0`); rebuild the software tarball.
- Note in the changeset: single-cell now produces per-chain scores (schema change), TCR is
  rejected, FR4 included, no more fragment gluing.
- Coordinate with anyone consuming the old single-column single-cell output (the schema change
  in Phase 4 is downstream-visible).

---

## 10. Suggested execution order & checkpoints

1. **Phase 1** (contract) → review with domain reviewer. ← *gate, do not skip*
2. **Phase 2** (Python) + **Phase 8** fixtures together (TDD: write correct fixtures, watch old
   Python fail, make new Python pass) — Python is testable in isolation.
3. **Phase 3** (workflow assembly) — the big one; depends on the contract.
4. **Phase 4** (per-chain output) + **Phase 6** (TCR guard).
5. **Phase 5** (model/UI) — fix single-cell table, tighten selectors.
6. **Phase 9** (changeset/version) — once behavior is verified end-to-end.
7. **Phase 7** (per-residue annotation) — separate follow-up.

### End-to-end verification matrix (run before shipping)

| Modality | Expected |
|---|---|
| Bulk heavy-chain dataset | one score/clonotype = full-VH score, no duplication |
| VHH dataset | one score/clonotype over full VHH (incl. FR4) |
| Single-cell paired | separate Heavy & Light score columns (primary-rank); secondary-rank → null; table renders |
| CDR3-assembled dataset | hard-fail with re-run message (no scoring) |
| Short / unscoreable sequence | null score, no crash |
| TCR | rejected at input + guarded in workflow |
| scFv | descoped — no producer; revisit when contract exists |

---

## 11. Open questions

**Resolved** (against `mixcr-clonotyping` producer — see 1.2 / Phase 6):

- ✅ Full variable region = **`pl7.app/vdj/feature == "VDJRegionInFrame"`** for the amino-acid
  column (the producer rewrites `VDJRegion`→`VDJRegionInFrame` for `aminoacid`; plain `VDJRegion`
  is the nucleotide column only). Already assembled in order. An aa-column guard must match
  `VDJRegionInFrame`.
- ✅ Ig vs TCR = `pl7.app/vdj/chain` (bulk axis-domain = chainInfos **keys**: Ig = `IGHeavy`/
  `IGLight`, TCR = `TCRAlpha`/`TCRBeta`/`TCRGamma`/`TCRDelta` — NOT `IGH/IGK/IGL`, which is the
  `topChains` column's discreteValues) / `pl7.app/vdj/receptor` (single-cell, `IG` vs
  `TCRAB`/`TCRGD`).
- ✅ **Two orthogonal single-cell axes:** `scClonotypeChain` `A`/`B` = chain **type**
  (IG: A=Heavy, B=Light); `scClonotypeChain/index` `primary`/`secondary` = rearrangement **rank**.
  Producer emits all four (Heavy/Light × primary/secondary).
- ✅ CDR3-only restriction keys on **`index == "secondary"`** (both Heavy-secondary and
  Light-secondary), **not** on Heavy-vs-Light. Heavy-primary AND Light-primary both carry the
  full domain and are scored; secondary-rank → `null`.
- ✅ **DECIDED:** CDR3-assembled dataset (no `VDJRegionInFrame`) → block **hard-fails** with a
  "re-run clonotyping assembled by VDJRegion" message (selectors + workflow guard). See 1.2.
- ✅ scFv = **descoped** (no upstream producer; dead branch to delete). Revisit when an scFv
  producer/column contract exists. See §3.2 and correct-behavior §4.4.

**Still to decide (Phase 1, with the domain reviewer):**

- Whether single-cell per-chain scores are **separate columns** (recommended) or a **chain
  axis** (1.4) — affects table/graph UI.
- How `clonotype-humanness.tpl.tengo` runs for multi-chain: once per chain table, or once over
  a tall (chain-keyed) table.
- **UI decision:** is a secondary-rank / CDR3-only chain simply `null`, or do we surface a
  distinct "not available (CDR3-only)" state in the UI?
- Whether per-residue annotation (Phase 7) is in-scope for this milestone.
