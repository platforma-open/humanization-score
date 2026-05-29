---
"@platforma-open/milaboratories.humanization-score.workflow": minor
"@platforma-open/milaboratories.humanization-score.model": minor
"@platforma-open/milaboratories.humanization-score.ui": minor
---

Emit a dedicated per-sample humanness pframe from the workflow whose score
column declares `[sampleId, clonotypeKey]` as real axes, instead of joining a
clonotype-keyed score against the abundance column at plot time.

The per-clonotype score (which is sample-independent) is broadcast onto every
sample a clonotype appears in via an inner join against the input's primary
abundance membership. The "By Sample" box plot now reads the `sampleId` axis
straight from the score column's own spec and pre-selects it as the primary
grouping. Datasets without a primary-abundance column simply produce no
per-sample output (the page stays empty).
