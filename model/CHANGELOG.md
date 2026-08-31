# @platforma-open/milaboratories.humanness-score.model

## 1.4.0

### Minor Changes

- adc1fdf: Migrate onto the structurer and take the full SDK upgrade (block-tools 2.14.3, tengo-builder 4.0.23, model 1.83.0, ui-vue 1.83.3).

  Adds the mandatory block kind. Its init-params contract is the input dataset, the block subtitle and the memory override, so a project template can seed a configured Humanness Score block.

## 1.3.0

### Minor Changes

- 12a697a: Accept bare imported antibody sets keyed on pl7.app/variantKey

  Import VDJ Data's bare receptor sets key a record on `pl7.app/variantKey`, an axis peptide-extraction
  and synthetic-repertoire-profiler also key on. The axis name therefore identifies no producer — the
  run-id in its domain does (`pl7.app/vdj/clonotypingRunId` for a receptor set) — and this block read
  neither: such a set was not offered in the dataset dropdown at all, so an imported antibody panel
  could not be scored.

  The dropdown now offers a `pl7.app/variantKey` dataset whose axis carries
  `pl7.app/vdj/receptor: IG`, which only the VDJ producer stamps on that axis; peptide and amplicon
  sets are still not offered, and a TCR set stamps TCRAB/TCRGD and is not offered either. The workflow
  re-checks the run-id key and refuses an unrecognised producer by name instead of falling through to
  the nearest branch.

  Whether the two chains are scored separately now follows the `pl7.app/vdj/scClonotypeChain` COLUMN
  domain rather than the key axis being `pl7.app/vdj/scClonotypeKey`. A paired bare set carries both
  chains in one frame under that domain, so reading it off the axis name sent it down the bulk path,
  where one chain is picked and the other silently dropped — and the result still looks complete. A
  single-chain bare set carries no chain domain and stays bulk-shaped, which is what its producer
  intends.

  Bulk, single-cell and VHH inputs take exactly the paths they took before: the Ig/TCR guard reads the
  receptor from the key axis where the axis states it and the chain where it does not, which is the
  same decision it made when it read the axis name.

## 1.2.0

### Minor Changes

- 7282344: Block the run for datasets whose variable region covers fewer than 3 framework regions.

  A dataset assembled by a short feature such as CDR1:CDR3 covers only FR2 and FR3 (2 frameworks), which cannot satisfy OASis-style scoring's framework floor — previously the block ran and produced a silent empty/null table. The model now computes a `coverageWarnings` output from the selected dataset's amino-acid sequence columns up front; the UI mirrors it into block data so `args` throws and the Run button is disabled, with a message explaining why (per chain for single-cell). Datasets with a full VDJRegion or >=3 frameworks are unaffected.

## 1.1.0

### Minor Changes

- eb8103c: Content-address the exported humanness-score column instead of scoping it to the block instance.

  The score column's domain previously carried `pl7.app/blockId` (the block UUID), making every block's output unique and preventing cross-block reuse of the (expensive) scoring computation. The domain now carries a content tag derived from the scored table's canonical id, so blocks with identical scoring inputs produce content-identical columns (which can deduplicate) while different inputs stay distinct. `blockId` is no longer threaded through the workflow into the process template, and the provenance trace step no longer keys on it.

## 1.0.0

### Major Changes

- df6b969: Release

## 0.4.0

### Minor Changes

- 8a6b41d: Fix incorrect humanness scoring: score the full variable-region sequence per chain (antibody-only).

  This is a correctness-breaking change. Humanness scores produced by previous
  versions were computed on the wrong sequences and must be recomputed — old
  scores should not be trusted or compared against new ones.

  What was wrong:

  - **Bulk:** the scored sequence was assembled incorrectly. The full variable
    region was effectively duplicated, the FR4 framework was dropped, and the
    framework/CDR fragments were stitched together in the wrong order. The
    resulting amino-acid string did not correspond to a real antibody variable
    domain, so every score was meaningless.
  - **Single-cell:** Heavy and Light chains were merged into a single scored
    sequence, and rows that only carried a CDR3 (secondary rearrangements) were
    scored as if they were complete variable regions. A model trained on full
    variable domains was therefore fed concatenated/partial sequences.
  - **scFv:** an scFv-specific branch interleaved Heavy and Light segments into
    one sequence. The upstream producer never emits scFv data, so this path was
    dead code that could only ever produce a malformed sequence.

  What the fix does:

  - Scores are computed directly on the full assembled variable-region
    amino-acid sequence (`VDJRegion` / `VDJRegionInFrame`, FR1..FR4 inclusive)
    exactly as produced upstream. FR/CDR fragments are no longer reassembled and
    the assembling-feature sequence is no longer scored on its own.
  - **Single-cell now emits one score column per chain type** (Heavy and Light),
    distinguished by the `pl7.app/vdj/scClonotypeChain` domain on the shared
    `pl7.app/humannessScore` column — this is an output schema change. Only the
    primary rearrangement of each chain type is scored; secondary rearrangements
    are CDR3-only and emit null (keyed on the rearrangement-rank index, not on
    Heavy/Light). The table joins Heavy and Light into one row per clonotype and
    the histogram defaults to the Heavy chain.
  - **TCR datasets are now rejected.** They are no longer offered in the input
    selector and the workflow hard-fails on TCR input (bulk chains other than
    `IGHeavy`/`IGLight`, single-cell receptor other than `IG`). Humanness scoring
    applies to antibodies only.
  - **CDR3-assembled datasets (no full variable region) now yield a null
    humanness score with a non-fatal warning.** Such datasets have no full
    variable region available, so the score is honestly not computable: the block
    emits a null/empty humanness result and surfaces a warning instructing the
    user to re-run clonotyping assembled by VDJRegion. The run completes normally
    (no crash, no hard-fail). These datasets are still offered in the input
    selector (which stays Ig-only); VDJRegion availability cannot be detected at
    the anchor level.
  - The dead scFv code path was removed.

## 0.3.2

### Patch Changes

- ac1bb58: Enrich the results table with every result-pool column sharing the humanness
  score's `clonotypeKey` axis. The `pt` output now anchors on the score column and
  uses an `enrichment` selector, so the original clonotype columns (sequences,
  labels, etc.) are shown alongside the humanness score instead of the score alone.

## 0.3.1

### Patch Changes

- 5a28f73: Give the charts a solid fill instead of the default white: the score
  distribution histogram now renders in blue and the per-sample box plot in teal,
  using colours from graph-maker's fixed palette. Applies to newly created blocks.
- 2c8b719: Remove the per-sample box plot ("By Sample") view: the `perSamplePf` /
  `perSamplePfPcols` outputs, the `graphStateBoxplot` state and its defaults, and
  the `/by-sample` section are gone. The score distribution histogram remains.

## 0.3.0

### Minor Changes

- 5c4b4f0: Initial release of the Humanness Score block.

  Scores antibody sequences for humanness relative to natural human antibody
  repertoires using the offline OASis/SwissProt databases bundled with the
  `promb` Python runtime environment.

  - **workflow**: Tengo templates that run per-clonotype humanness scoring over
    the input dataset.
  - **software**: Python scoring scripts (Parquet in/out) wrapping `promb`.
  - **model**: block configuration, inputs/outputs, and result columns.
  - **ui**: results UI with humanness score table, histogram, and sample boxplot
    pages.

## 0.2.0

Initial release.
