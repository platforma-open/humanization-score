# @platforma-open/milaboratories.humanization-score.model

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

- 5c4b4f0: Initial release of the Humanization Score block.

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
