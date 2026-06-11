---
"@platforma-open/milaboratories.humanness-score.workflow": minor
---

Content-address the exported humanness-score column instead of scoping it to the block instance.

The score column's domain previously carried `pl7.app/blockId` (the block UUID), making every block's output unique and preventing cross-block reuse of the (expensive) scoring computation. The domain now carries a content tag derived from the scored table's canonical id, so blocks with identical scoring inputs produce content-identical columns (which can deduplicate) while different inputs stay distinct. `blockId` is no longer threaded through the workflow into the process template, and the provenance trace step no longer keys on it.
