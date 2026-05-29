---
"@platforma-open/milaboratories.humanization-score": minor
"@platforma-open/milaboratories.humanization-score.workflow": minor
"@platforma-open/milaboratories.humanization-score.model": minor
"@platforma-open/milaboratories.humanization-score.ui": minor
"@platforma-open/milaboratories.humanization-score.software": minor
---

Initial release of the Humanization Score block.

Scores antibody sequences for humanness relative to natural human antibody
repertoires using the offline OASis/SwissProt databases bundled with the
`promb` Python runtime environment.

- **workflow**: Tengo templates that run per-clonotype humanness scoring over
  the input dataset.
- **software**: Python scoring scripts (Parquet in/out) wrapping `promb`.
- **model**: block configuration, inputs/outputs, and result columns.
- **ui**: results UI with humanness score table, histogram, and sample boxplot
  pages.
