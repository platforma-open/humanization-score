---
"@platforma-open/milaboratories.humanization-score.model": patch
---

Enrich the results table with every result-pool column sharing the humanness
score's `clonotypeKey` axis. The `pt` output now anchors on the score column and
uses an `enrichment` selector, so the original clonotype columns (sequences,
labels, etc.) are shown alongside the humanness score instead of the score alone.
