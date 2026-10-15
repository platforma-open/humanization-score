---
"@platforma-open/milaboratories.humanness-score": minor
"@platforma-open/milaboratories.humanness-score.kind": minor
"@platforma-open/milaboratories.humanness-score.model": minor
"@platforma-open/milaboratories.humanness-score.ui": minor
"@platforma-open/milaboratories.humanness-score.workflow": minor
---

Update the SDK and accept a subset filter (e.g. a Repertoire Labeling label or Lead Selection picks) with the input dataset. The dataset list is built with buildDatasetOptions (requireEnrichments: false). Only the subset's clonotypes are scored; the score is per clonotype, so their values match a full-data run. Outputs of a subset run carry pl7.app/inputSubset in their domain and a trace rooted in the subset, so their labels name it. Unfiltered runs are unchanged.
