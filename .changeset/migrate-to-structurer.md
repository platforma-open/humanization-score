---
'@platforma-open/milaboratories.humanness-score.model': minor
'@platforma-open/milaboratories.humanness-score': minor
'@platforma-open/milaboratories.humanness-score.ui': patch
'@platforma-open/milaboratories.humanness-score.workflow': patch
'@platforma-open/milaboratories.humanness-score.software': patch
---

Migrate onto the structurer and take the full SDK upgrade (block-tools 2.14.3, tengo-builder 4.0.23, model 1.83.0, ui-vue 1.83.3).

Adds the mandatory block kind. Its init-params contract is the input dataset, the block subtitle and the memory override, so a project template can seed a configured Humanness Score block.
