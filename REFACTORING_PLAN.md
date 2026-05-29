# Refactoring Plan — humanization-score

Triaged against the codebase on 2026-05-29. Each item marks whether the original
feedback was confirmed, refined, or stale.

## Decisions (from product owner)

- Default block label → **input dataset name** (not the static "Humanness Score").
- Block naming unified to **"Humanization Score"** everywhere (matches the catalog).
- `liabilities*` → `humanness*` rename: **full**, including the `outputLiabilities`
  output key (touches `model/src/index.ts`).
- Software layout: **restructure** to a `software/` package like clonotype-clustering.

---

## 1. Remove dead data-flow (CONFIRMED, with refinements)

The Python tool reduces input to "concatenate every column whose header ends in
` aa`" (`humanness-calc-script/src/main.py:55-64`). Metadata threaded forward is unused.

- **`numberingSchema`** (`workflow/src/main.tpl.tengo:93-103`): computed but **never
  passed anywhere** (the calc template render at :190-191 passes only `table`). Worse
  than reported — it is pure dead code AND its `ll.panic` on mixed schemas is a
  gratuitous failure mode on input the tool ignores. **Delete the whole block.**
- **`mapping`**: STALE — already absent from the code (0 matches). No action.
- **`coveredFeatures` / `isSingleCell` / `hasAnnotations`**: packed into the params
  JSON resource (`main.tpl.tengo:208-210`) but `clonotype-process.tpl.tengo` reads only
  `params.datasetSpec` (:28). **Drop the three unused fields from the params resource.**
  - Note: `coveredFeatures`/`isSingleCell` are still used *locally* in main.tpl.tengo to
    drive seq-table header assembly (the `features` accumulator and the single-cell
    branch). Keep the local logic; only stop *exporting* them downstream.
- **`feature`** (`main.tpl.tengo:84-89`): the variable is dead, but the guard
  `len(sequences) > 0` + `ll.panic("No sequences found...")` is useful. **Remove the
  `feature` assignment, keep the guard.**
- ⚠️ **Do NOT touch** the seq-table header assembly (`:108-179`): those ` aa` headers
  drive Python's column selection.

## 2. Remove unused imports (CONFIRMED, broader than reported)

- `workflow/src/main.tpl.tengo`: unused **`exec`, `xsv`, `pSpec`, `text`, `json`**
  (0 uses each — verified). Original feedback only named text/json.
- `workflow/src/clonotype-process.tpl.tengo:8-9`: `text`, `json` — 0 uses.
- `workflow/src/clonotype-humanness.tpl.tengo:2,5,6`: `ll`, `text`, `json` — 0 uses
  (`math` is used).
- `ui/package.json:20`: `@vueuse/core` — never imported in `ui/src/`. Remove the dep.

## 3. Rename `liabilities*` → `humanness*` (CONFIRMED — full rename)

- `workflow/src/main.tpl.tengo`: `liabilitiesResultCalc`, `liabilitiesResult` →
  `humannessResultCalc`, `humannessResult`. Output key
  `outputLiabilities` → `outputHumanness` (in `outputs` map :225 and the
  `processResult.output(...)` resolve :220).
- `workflow/src/clonotype-process.tpl.tengo`: `liabilitiesTable` → `humannessTable`,
  `outputLiabilities` var/output → `outputHumanness`, `self.defineOutputs` :12,
  the stale comment at top, the builder var.
- `model/src/index.ts:71`: `ctx.outputs?.resolve('outputLiabilities')` →
  `'outputHumanness'`. (This is the cross-package coupling — must change in lockstep.)
- Grep `liabilit` across the repo after the change to confirm zero stragglers.

## 4. Block naming consistency → "Humanization Score" everywhere (CONFIRMED)

- `model/src/index.ts:85` `.title(() => 'Humanness Score')` → `'Humanization Score'`.
- `model/src/index.ts:87` `.subtitle(...)` default and `:48` `customBlockLabel` default
  `'Humanness Score'` → see item 5 (default becomes dataset name, not a static string).
- `workflow/src/clonotype-process.tpl.tengo:91` trace `type:
  "milaboratories.humanization-score"` is fine; the trace `label` follows the block label.
- The **column** label stays "Humanness Score" (`clonotype-process.tpl.tengo:49`) — that
  is the metric name, not the block name. Leave it.
- STALE: catalog `description` is no longer a placeholder (`block/package.json:31` has a
  real sentence). No action; the "(placeholder)" note referred to an old state.

## 5. Default block label → dataset name (CONFIRMED — design change)

- Today: `model/src/index.ts:48` `customBlockLabel: data.customBlockLabel || 'Humanness
  Score'` and subtitle `:87` default to the same string → title/subtitle duplicate.
- Change: derive the default from the selected input dataset name instead of a static
  string. Two options to confirm during implementation:
  - (a) Resolve the dataset/anchor label in the model and use it as the default
    `customBlockLabel` / subtitle.
  - (b) Keep `customBlockLabel` empty by default and have the subtitle fall back to the
    dataset spec label.
- The workflow trace label (`clonotype-process.tpl.tengo:88` `blockLabel :=
  customBlockLabel`) then inherits the dataset-derived label automatically.

## 6. Runenv / dependency hygiene (CONFIRMED, with one caveat)

- `humanness-calc-script/package.json:15` pins the custom runenv
  `@platforma-open/milaboratories.runenv-python-3.12.10-humanness` at exact `0.2.0`,
  not via `catalog:`. **Add a catalog entry and switch to `catalog:`** for consistency.
- `pnpm-workspace.yaml:24` declares the *base* runenv
  `@platforma-open/milaboratories.runenv-python-3: ^1.4.9` which **nothing uses**
  (the block uses the custom env). **Remove this stale catalog line** (or repurpose it
  for the custom runenv per the line above).
- `requirements.txt`: `polars-lts-cpu==1.33.1` (pinned, good) and `promb>=1.0.2` (range).
  Under offline `--no-index` resolution this only works if the runenv bundles a
  satisfying wheel. **Pin `promb==<bundled version>`** once confirmed.
- CAVEAT — STALE/INAPPLICABLE: the feedback's "add a reflection under
  `mictx-helper/harnesses/block-dev/_meta/reflections/`" — **that directory does not
  exist in this repo**. It belongs to external meta-tooling, not this block. No action
  here; if a reflection is wanted it lives in that other repo.

## 7. Investigate the bundled model/DB source (CONFIRMED — investigation)

- `main.py:36` calls `init_db("human-oas")` from `promb`. The `human-oas` peptide set /
  DB must be available offline. Confirm **where it comes from**:
  - Does the custom runenv `...-3.12.10-humanness` bundle the `human-oas` + SwissProt
    data (likely, since `requirements.txt` can't fetch it under `--no-index`)?
  - If so, document it: the custom runenv exists precisely to ship `promb` + its DBs.
  - Decide whether to "package it to us" (vendor the DB into our registry) vs. relying on
    whatever the custom runenv currently ships. Output: a short note in docs + a pinned,
    catalog-referenced runenv version.

## 8. Restructure into a `software/` package (CONFIRMED — design change)

Mirror `platforma-open/clonotype-clustering` (`software@4.0.0`):
- Rename dir `humanness-calc-script/` → `software/`.
- Package name `@platforma-open/milaboratories.humanization-score.humanness-calc-script`
  → `@platforma-open/milaboratories.humanization-score.software`.
- Keep `src/main.py` + `src/requirements.txt` layout (reference puts requirements in
  `./src`; current repo already has `src/requirements.txt`).
- Update `pnpm-workspace.yaml:5` package list (`humanness-calc-script` → `software`).
- Update the workflow `importSoftware` name in
  `clonotype-humanness.tpl.tengo:9` to the new package name + entrypoint.
- Update any `workspace:*` references and the lockfile (`pnpm install`).
- This is the highest-blast-radius change (paths, package name, imports, lockfile) — do
  it as its own commit, last, after the smaller cleanups are green.

---

## Suggested ordering (low-risk → high-risk)

1. Item 2 — delete unused imports (mechanical, isolated).
2. Item 1 — delete dead data-flow + params fields (keep guard & header logic).
3. Item 3 — `liabilities*` → `humanness*` rename (workflow + model lockstep).
4. Item 4 + 5 — naming consistency + dataset-name default label (model-side).
5. Item 6 — runenv/catalog hygiene + pin `promb`.
6. Item 7 — investigate & document the bundled DB.
7. Item 8 — restructure to `software/` package (biggest blast radius, last).

After each step: `pnpm -r build` / type-check the workflow + model; final `grep liabilit`
must be empty; `pnpm install` after item 8.
