# Humanization Score Block — Engineering Plan

Engineering plan for the `humanization-score` block. Biology is reduced to a minimum: from a code perspective, the block is `f(amino_acid_sequence: string) → float` wrapped into a standard platform pipeline unit.

Source of requirements: `Antibody Humanization Score.md`.

## Workflow

- **All tasks are executed via subagents** (Agent tool). The main thread orchestrates and verifies results; the actual work (repo clone, file copying, code edits, builds) is delegated.
- After each plan step, its status and a brief report are recorded in this file under the **Execution log** section at the end.
- Each task in the plan corresponds to one subagent invocation; if a task is large — several sequential or parallel ones.

---

## 0. Pre-flight (before any code)

- [ ] Clarify where the block lives: in this repo or in the platform monorepo next to `blocks/antibody-sequence-liabilities/`.
- [ ] Obtain access to the precedent repos (see §2). Without them correct PColumn annotations cannot be implemented.
- [ ] Obtain test datasets for the three modalities: VHH, mAb, scFv.
- [ ] Obtain a "reference" panel of known-human and known-non-human sequences for the acceptance test (§8).

---

## 1. Block contract

### Input
- Existing PColumn with antibody amino-acid sequences (same shape as in `antibody-sequence-liabilities`).
- Supported modalities: **VHH, mAb, scFv**.

### Output
- One PColumn per scored chain (heavy / light / both — depending on modality).
- `value type: Float`.
- Scale: higher = more "human". If the chosen tool gives the inverse — we invert it.
- Recommended normalization: 0–100 (or 0–1), so the scale is method-independent (the method may change in v2).
- The `pl7.app/isScore: "true"` annotation — set **only** if the chosen method has published validation against immunogenicity. The decision is on the implementer and is recorded in `description.md`. ⚠️ **Current state**: `isScore: "true"` is already set in both tengo templates (for Lead Selection participation), but the rationale in `description.md` has not yet been recorded — the open question is not formally closed.

### What the block does NOT do (out of scope)
- Per-residue score (which positions pull the score down).
- Mutation suggestions (back-mutation to a human germline).
- Parallel scoring with multiple methods.
- Hard-filter in Lead Selection (ranking only).

---

## 2. Precedent files to read BEFORE coding

| What | Where | Why |
|------|-------|-----|
| Scoring block structure | `blocks/antibody-sequence-liabilities/` | Copy as a skeleton |
| PColumn conventions (isScore, defaultCutoff, etc.) | `docs/text/work/projects/sequence-liability-fixability-scoring/pcolumn-spec.md` | So Lead Selection finds the column |
| Column discovery in Lead Selection | `blocks/antibody-tcr-lead-selection/model/src/util.ts` | Understand which annotations the block looks for |

These files are the only reliable source of truth on the format. Don't move on without reading them.

---

## 3. Scoring engine selection

A standalone engineering subtask. Purely technical criteria:

- **License**: open source, permissive (required for platform redistribution).
- **Footprint**: container size, model weights, runtime dependencies (Python/PyTorch/etc.).
- **Performance**: per-sequence cost → determines whether the full repertoire fits or only a pre-filtered panel.
- **Modalities**: must cover VHH, mAb, scFv (or the block's wrapper reduces the input to a supported format).
- **Validation**: existence of published validation → affects `isScore`.
- **Output**: a single number; method-specific scale is rescaled.

Research candidates (not a final list): BioPhi/OASis, AbNatiV, Hu-mAb, IgReconstruct.

**Artifact of this stage**: a short decision-doc inside `description.md` — what was chosen, which alternatives were considered, why.

> ✅ **Engine chosen**: `promb` (package `promb>=1.0.2`), `human-oas` DB — OASis-style score: fraction of 9-mers from the sequence found in human repertoires, rescaled to 0..100, higher = more human. ⚠️ The decision-doc in `description.md` is not yet written (see §9); alternatives are not formally documented.

---

## 4. Block scaffold

Source: `git@github.com:platforma-open/antibody-sequence-liabilities.git`. The precedent is named explicitly in the brief.

- [ ] **(subagent)** Clone `antibody-sequence-liabilities` into a temp directory, read its structure.
- [ ] **(subagent)** Replace the current "foreign" scaffold (it was copied from `antibody-tcr-lead-selection`, visible from `block/package.json:meta.title` and URL) with the `antibody-sequence-liabilities` structure.
- [ ] **(subagent)** Keep only: `.git/`, `Antibody Humanization Score.md`, `PLAN.md`, `README.md` (if non-empty). Everything else (including `node_modules`, build artifacts) is to be replaced / regenerated.
- [ ] **(subagent)** Rename package names: `antibody-sequence-liabilities` → `humanization-score` in all `package.json`, `pnpm-workspace.yaml`, cross-workspace references.
- [ ] **(subagent)** Update `block/package.json:meta` (title, description, url, docs) for humanization-score; concrete texts are placeholders, finalized in §9.
- [ ] Use **BlockModelV3** (current convention; should be inherited from the precedent).
- [ ] Do not commit — the main thread reviews the diff and decides.

---

## 5. Containerization of the chosen tool

- [ ] Dockerfile for the chosen scorer: system libs, runtime, model weights.
- [ ] Pin versions (model + tool code) for reproducibility.
- [ ] CLI wrapper: `stdin/stdout` or `--input file --output file`, so the workflow calls it deterministically.
- [ ] Measure per-sequence latency and throughput on a representative sample. Record in `description.md` the practical input-size ceiling.

---

## 6. Workflow (orchestration)

- [x] Read the input PColumn with sequences.
- [x] Iterate over rows (or batch, if the tool supports it) → call the scorer (`humanness-calc-script`, `main.py` / `peptide_main.py`).
- [~] Collect results → write output PColumn(s):
  - ⚠️ Currently **one** `humanness_score` column per clonotype: all `* aa` columns are concatenated and scored as a single number. There are NO separate heavy/light columns — reconsider whether per-chain detail is needed.
  - For VHH a single chain — covered.
- [x] Scale normalization 0..100 (see §1).
- [x] Apply annotations per `pcolumn-spec.md` (`pl7.app/humannessScore`, `isScore: "true"`, `rankingOrder: "decreasing"`, `score/method`).

---

## 7. Lead Selection integration

- [ ] Check how `blocks/antibody-tcr-lead-selection/model/src/util.ts` discovers scoring columns. ⚠️ Not confirmed that the annotations we emit match what util.ts looks for.
- [x] Apply annotations on the output PColumn for auto-pickup as the **default ranking criterion** (`isScore: "true"` + `score/rankingOrder: "decreasing"`).
- [x] **Lead Selection code is not touched** — respected (no changes there).
- [ ] Verify integration via an end-to-end run. ⚠️ Not done.

---

## 8. Tests and acceptance

- [ ] `pnpm build` green.
- [ ] Block integration tests pass.
- [ ] Run on a sample for each modality: VHH, mAb, scFv.
- [ ] **Sanity test**: on a mixed panel of "known-human" vs "known-non-human" → the average score on humans is noticeably higher. This is the final acceptance proving the wrapper hasn't broken the score's meaning.
- [ ] Run via Lead Selection: the column appears, ranking works.

Mapping to the brief's Success Criteria:

| Criterion from the brief | Covered by step |
|---|---|
| Block builds, installs, runs | §4, §5, §8 |
| Produces humanness score PColumn per chain | §6 |
| Wired into Lead Selection as default ranking criterion | §7 |
| Runs on VHH, mAb, scFv | §6, §8 |
| Human > non-human on mixed panel | §8 (sanity test) |
| `description.md` documents method, license, scale | §3, §9 |
| `pnpm build` + integration tests | §8 |

---

## 9. Documentation

`description.md` in the block must contain:

- The chosen method and its source/version.
- License.
- Score scale (range, orientation: higher = better).
- Modality coverage.
- Performance benchmark → practical input-size ceiling.
- The `isScore` decision and its rationale (validation present / absent).
- Alternatives considered (briefly, why rejected).

---

## 10. Execution order

1. §0 — pre-flight, unblock accesses.
2. §2 — read the three precedent files.
3. §3 — select the scoring engine.
4. §4 — block scaffold.
5. §5 — container + CLI wrapper for the tool.
6. §6 — workflow + PColumn IO.
7. §7 — apply annotations, verify discovery in Lead Selection.
8. §8 — run tests, sanity check.
9. §9 — finalize `description.md`.

---

## Open questions (inherited from the brief)

- `isScore: "true"` — decided after the method is chosen in §3.
- Input-size ceiling — measured in §5, recorded in §9.
- Final scale normalization — decided in §6 (recommendation: 0–100).

---

## 11. Decisions from the colleague (2026-05-28)

After reviewing the discovery code in `antibody-tcr-lead-selection/model/src/util.ts`, a conflict in the brief surfaced: for humanness to become the **default** ranking criterion for the in-vivo/in-vitro presets, the allowlist in lead-selection must be extended. The brief forbade touching lead-selection ("UNCHANGED"). The colleague lifted both constraints:

1. **Lead Selection is editable.** Humanness must be a **default ranking** for both **in-vivo** and **in-vitro**. The brief's "leads stays unchanged" point is dropped.
2. **Peptide input is out of scope.** The score doesn't make sense on peptides; remove the peptide branch from the block entirely.

### Required changes

#### A. In `antibody-tcr-lead-selection` (`/Users/aleksandr/GIT/MILAB/antibody-tcr-lead-selection`)

File: `model/src/util.ts`

- [ ] Add `'pl7.app/humannessScore'` to `IN_VIVO_RANKING_SPEC_NAMES` (lines 79-82).
- [ ] Add `'pl7.app/humannessScore'` to `IN_VITRO_RANKING_SPEC_NAMES` (lines 103-108).
- [ ] Check whether `defaultCutoff` is needed for preset filters (if humanness shouldn't end up in filters, leave as is).
- [ ] CHANGELOG + patch-version bump.

#### B. In `humanization-score` (peptide cleanup) ✅ 2026-05-28

**Delete:**
- [x] ✅ `humanness-calc-script/src/peptide_main.py`
- [x] ✅ `workflow/src/peptide-humanness.tpl.tengo`
- [x] ✅ `workflow/src/peptide-process.tpl.tengo`

**Edit:**
- [x] ✅ `workflow/src/main.tpl.tengo` — removed the peptide branch and the `peptideHumannessTpl` import.
- [x] ✅ `model/src/index.ts` — removed the peptide variant (`pl7.app/variantKey`) from `getOptions`; removed the `Modality`/`modality` output (single modality now). The `syncModality` consumer in `ui/src/app.ts` was also removed.
- [x] ✅ `humanness-calc-script/package.json` (block-software entrypoints) — `peptide` entrypoint registration removed.
- [x] ✅ `docs/description.md` — peptide section removed, VHH/mAb/scFv kept.
- [x] ✅ PLAN.md §1, §6 — peptide dropped (peptide wasn't mentioned in §1; §6 wording fixed).
- [x] ✅ CHANGELOG.md (root + humanness-calc-script) — noted that peptide is intentionally out of scope.
- [x] ✅ `block/package.json` — `peptide` tag removed.

**Verify:**
- [x] ✅ `pnpm build` green.
- [x] ✅ No references to `variantKey` / `peptide` / `peptide_main` / `peptide-humanness` remain in source (grep clean; remaining mentions are confined to `Antibody Humanization Score.md` and the historical execution log).

#### Order
1. B (peptide cleanup in this repo) — independent.
2. A (allowlist in lead-selection) — separate commit/PR in the other repo.
3. End-to-end run (§7/§8): the column appears in the default ranking of both presets.

---

## Execution log

Chronology of execution. Each entry: date, plan step, who did it (agent / main thread), brief outcome.

| Date | Step | Executor | Outcome |
|------|------|----------|---------|
| 2026-05-26 | §4 copying the scaffold from `antibody-sequence-liabilities` | subagent | Done. Source: commit `ff07500` of 2026-05-26. The old scaffold (from `antibody-tcr-lead-selection`) removed, replaced with `antibody-sequence-liabilities`. Kept: `.git/`, `Antibody Humanization Score.md`, `PLAN.md`, `README.md`, `.pnpm-store/`. Package names renamed (`antibody-sequence-liabilities` → `humanization-score`). Directory `liabilities-calc-script/` → `humanness-calc-script/`. Updated `block.meta.title` = "Humanization Score", `meta.description` = placeholder, `meta.url`/`meta.docs` point at humanization-score. `git status`: 97 changes, nothing committed. `pnpm install` not run. |
| 2026-05-26 | Step A: `pnpm build` green | subagent | Build OK from scratch, no fixes required. 9 tasks built: model, ui, workflow (tengo), humanness-calc-script, block-pack. Warnings: `${NPMJS_TOKEN}` in `.npmrc` (publish-only), vite chunk-size in `ui/dist` (preexisting). |
| 2026-05-26 | Step B: stub humanness logic | subagent | Build OK + Python tests 6/6 green. Stub function: `100 * (fraction of standard AAs) / len(seq)`, range 0..100, deterministic. Output PColumn: a single `humanness_score: Double` column with spec `pl7.app/humannessScore`, label "Humanness Score". Works for both clonotype and peptide branches. `pl7.app/isScore` NOT set (open question). Removed `annotations.py`/`definitions.py`/`detection.py`/`scoring.py` from the python script. 15 files changed, nothing committed. |
| 2026-05-27 | §9 `description.md` + cosmetics | subagents | **§9**: `docs/description.md` rewritten for humanness (method promb/OASis, scale 0..100, modalities, isScore, alternatives). Verified: promb = MIT (© Merck), OAS = CC-BY 4.0, OASis validation (Prihoda et al., mAbs 2022). OPEN ITEMS: license of the bundled `human-oas` artifact (needs sign-off), benchmark not measured (§5), per-sequence validation not confirmed. **Cosmetics**: `*-liabilities.tpl.tengo`→`*-humanness.tpl.tengo` (git mv + references), all CHANGELOGs cleaned → 0.1.0, package.json versions → 0.1.0. `pnpm build` green (9/9). Not committed. |
| 2026-05-27 | §3 + §6 + §7: real scorer promb/OASis | (committed: `975da7f`→`a09d386`) | Stub replaced with **promb / OASis** (`human-oas` DB): `humanness()` = fraction of 9-mers in human repertoires × 100. `main.py` (antibody, concatenates all `* aa` columns) + `peptide_main.py` (reuses `humanness`). `requirements.txt`: `promb>=1.0.2`, `polars-lts-cpu==1.33.1`. Annotations: `isScore: "true"`, `score/rankingOrder: "decreasing"`, `score/method: "promb / OASis (human-oas)"`. Model `index.ts` cleaned of liability dead-code (types `CustomLiability` and args removed, `upgradeLegacy` kept). UI cleaned of liability controls. **Not done**: decision-doc/`description.md` (§9, still about liabilities), human-vs-non-human sanity test (§8), end-to-end run through Lead Selection (§7), discovery cross-check in util.ts. |

### Step B — tails (from subagent)

These are stub-stage "leftovers" that do NOT block running but need attention:

1. ~~**Real scorer**~~ ✅ 2026-05-27: replaced with promb/OASis (`human-oas`) in `main.py` + `peptide_main.py`.
2. ~~**`pl7.app/isScore`**~~ ✅ 2026-05-27: set to `true` + `rankingOrder: "decreasing"` in both tengo templates. ⚠️ The rationale in `description.md` is still not recorded.
3. ~~**UI settings panel**~~ ✅ 2026-05-27: liability controls removed, `MainPage.vue` reduced to the table + customBlockLabel.
4. ~~**`model/src/index.ts`** dead-code~~ ✅ 2026-05-27: `CustomLiability` types / liability args removed.
5. ~~**Tengo `*-liabilities.tpl.tengo`**~~ ✅ 2026-05-27: renamed to `clonotype-humanness.tpl.tengo` / `peptide-humanness.tpl.tengo` (git mv), references in `main.tpl.tengo` updated, `pnpm build` green. (Internal var names like `liabilitiesResultCalc` left intact — they don't affect the build.)
6. **Trace type** = `milaboratories.humanization-score` — if Lead Selection has a binding to `milaboratories.sequence-liabilities`, a cross-check is needed (see §7).
7. **Workflow `bundleBuilder`** — collects sequences + annotations + peptide sequences; `main.py` concatenates all `* aa` columns. Reconsider whether per-chain (heavy/light) detail is needed instead of a single number (see §6).

### §4 — what's left (decisions needed / not code)

The "tail" of the scaffold stage, recorded separately so it's not lost:

1. **Logos** `logos/block-logo.png`, `logos/organization-logo.png` — currently from sequence-liabilities; we need our own (or keep them temporarily if OK).
2. **`docs/description.md`** (`block.meta.longDescription`) — rewrite for humanization score, final in §9.
3. **`block.meta`**: final `title`, `description`, `docs` URL, `tags`, `marketplaceRanking`. Currently placeholder.
4. ~~**`CHANGELOG.md`**~~ ✅ 2026-05-27: all CHANGELOGs cleaned of `antibody-sequence-liabilities` history, reduced to a single `## 0.1.0 / Initial release` entry.
5. ~~**`version`**~~ ✅ 2026-05-27: versions in all `package.json` reset to `0.1.0` (block/model/ui/workflow/humanness-calc-script).
6. ~~**`pnpm install`** — run to regenerate `pnpm-lock.yaml` against the new package names and install `node_modules`.~~ ✅ 2026-05-26: done, exit=0. Warnings: 6 deprecated subdependencies (transitive, non-blocking) + peer-dep warnings.
7. **Business logic** — currently the sequence-liabilities implementation under the hood (workflow tengo, model TS, UI, python script). This is to be cleaned up / rewritten in the next plan steps (§5–§7), not here.
