---
"@platforma-open/milaboratories.humanness-score": patch
"@platforma-open/milaboratories.humanness-score.model": patch
"@platforma-open/milaboratories.humanness-score.ui": patch
---

The block runs without its window being opened: its arguments no longer wait for the coverage check the UI mirrored into the data, so a block created from a template or started by Run All is not skipped. An under-covered dataset now runs and scores null, with the same warning shown.
