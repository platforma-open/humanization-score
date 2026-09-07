---
'@platforma-open/milaboratories.humanness-score.software': patch
'@platforma-open/milaboratories.humanness-score': patch
---

Drop the stale `prepublish: pl-pkg prepublish` script from the software package.

The migration onto block-tools removed the `@platforma-sdk/package-builder` devDependency that provides `pl-pkg`, so `pnpm -r publish` failed the release job with `sh: 1: pl-pkg: not found`. Build and image push already happen in `block-tools software build`, so the script has nothing left to do.
