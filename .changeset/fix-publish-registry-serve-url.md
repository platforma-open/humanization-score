---
"@platforma-open/milaboratories.humanness-score": patch
---

Fix release publishing: pass the now-required `--registry-serve-url` to `block-tools publish`. block-tools 2.11.4+ made this option mandatory, so the previous publish command failed with "required option '--registry-serve-url <url>' not specified".
