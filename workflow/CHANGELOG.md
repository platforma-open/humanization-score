# @platforma-open/milaboratories.humanness-score.workflow

## 1.1.0

### Minor Changes

- eb8103c: Content-address the exported humanness-score column instead of scoping it to the block instance.

  The score column's domain previously carried `pl7.app/blockId` (the block UUID), making every block's output unique and preventing cross-block reuse of the (expensive) scoring computation. The domain now carries a content tag derived from the scored table's canonical id, so blocks with identical scoring inputs produce content-identical columns (which can deduplicate) while different inputs stay distinct. `blockId` is no longer threaded through the workflow into the process template, and the provenance trace step no longer keys on it.

## 1.0.0

### Major Changes

- df6b969: Release

### Patch Changes

- Updated dependencies [df6b969]
  - @platforma-open/milaboratories.humanness-score.software@1.0.0

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

### Patch Changes

- Updated dependencies [8a6b41d]
  - @platforma-open/milaboratories.humanness-score.software@0.4.0

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

### Patch Changes

- Updated dependencies [5c4b4f0]
  - @platforma-open/milaboratories.humanness-score.software@0.3.0

## 0.2.0

Initial release.
