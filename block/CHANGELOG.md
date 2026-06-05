# @platforma-open/milaboratories.humanness-score

## 0.3.2

### Patch Changes

- Updated dependencies [ac1bb58]
  - @platforma-open/milaboratories.humanness-score.model@0.3.2
  - @platforma-open/milaboratories.humanness-score.ui@0.3.2

## 0.3.1

### Patch Changes

- Updated dependencies [5a28f73]
- Updated dependencies [2c8b719]
  - @platforma-open/milaboratories.humanness-score.model@0.3.1
  - @platforma-open/milaboratories.humanness-score.ui@0.3.1

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
  - @platforma-open/milaboratories.humanness-score.workflow@0.3.0
  - @platforma-open/milaboratories.humanness-score.model@0.3.0
  - @platforma-open/milaboratories.humanness-score.ui@0.3.0

## 0.2.0

Initial release.
