---
"@platforma-open/milaboratories.humanness-score.model": minor
"@platforma-open/milaboratories.humanness-score.ui": patch
---

Block the run for datasets whose variable region covers fewer than 3 framework regions.

A dataset assembled by a short feature such as CDR1:CDR3 covers only FR2 and FR3 (2 frameworks), which cannot satisfy OASis-style scoring's framework floor — previously the block ran and produced a silent empty/null table. The model now computes a `coverageWarnings` output from the selected dataset's amino-acid sequence columns up front; the UI mirrors it into block data so `args` throws and the Run button is disabled, with a message explaining why (per chain for single-cell). Datasets with a full VDJRegion or >=3 frameworks are unaffected.
