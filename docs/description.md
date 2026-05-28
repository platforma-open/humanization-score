# Overview

Scores antibody amino-acid sequences for **humanness** — how human-like a sequence looks relative to natural human antibody repertoires. The score is intended as a ranking criterion in Lead Selection: among otherwise comparable candidates, more human-like sequences are generally preferred because they tend to carry lower immunogenicity risk.

The block emits a single output column, **Humanness Score**, with a value in **[0, 100]** — **higher = more human**. The column is published as a score, so Lead Selection picks it up automatically as a ranking criterion.

# Method

- **Library**: [promb](https://github.com/MSDLLCPapers/promb) (author David Prihoda / Merck & Co.).
- **Reference set**: `human-oas` — a curated 9-mer peptide set derived from human antibody repertoires in **OAS (Observed Antibody Space)**, the Oxford OPIG resource of cleaned, annotated, translated antibody sequences.
- **Approach**: **OASis-style** humanness scoring. The score is the fraction of overlapping **9-mer (9-residue) windows** in the sequence that are found in the `human-oas` reference set. This is the same exact-9-mer-match idea introduced in BioPhi/OASis (see *Validation*).
- **Output**: that fraction rescaled to `[0, 100]` (rounded to 2 decimals). Higher = more human; the score is not inverted.

# Score scale

- Range: **[0, 100]**, continuous.
- Orientation: **higher = more human**; larger values rank first.
- **Unscoreable inputs**: sequences shorter than 9 amino acids cannot produce a single 9-mer and yield an **empty** cell. Empty / malformed inputs are also left blank rather than failing the run.

# Modality coverage

The metric is alignment-free and works uniformly across antibody formats without per-format model configuration:

- **Antibody** — VHH, mAb, scFv. For each clonotype, all available amino-acid sequence regions (heavy + light chains for paired formats, the single chain for VHH) are scored together, producing one humanness number per clonotype. A per-chain (heavy vs light) breakdown is not currently emitted.

Peptide input is intentionally **out of scope** — humanness scoring is not meaningful for non-antibody peptides.

# License

- **promb** (the scoring code): **MIT License**, Copyright © 2025 Merck & Co., Inc. Confirmed from the installed package metadata (`promb-1.0.2.dist-info/licenses/LICENSE`, `License: MIT`). Permissive; compatible with redistribution.
- **OAS data** (the basis of the `human-oas` peptide set): the OAS database is published by Oxford OPIG under **CC-BY 4.0** (attribution required). The `human-oas` set shipped with promb is a derived artifact.

# Validation and `isScore` decision

The score is exposed to Lead Selection as a **default ranking criterion**. By convention this is only done for methods with published validation against immunogenicity. The OASis method (which `human-oas` scoring follows) does have such validation:

- **Prihoda et al., *mAbs* 2022** ([doi:10.1080/19420862.2021.2020203](https://doi.org/10.1080/19420862.2021.2020203)). OASis separates human from non-human sequences with high accuracy and **correlates with clinical immunogenicity** on a panel of 216 paired therapeutic antibodies (percentage of patients developing an anti-drug-antibody / ADA response).

The score is used for *ranking only* — never as a hard filter.

**Interpretation note.** The published evidence is a correlation with population-level ADA (anti-drug-antibody) rates across a panel of therapeutics — not a per-sequence ADA predictor. Treat the score as a **humanness proxy** useful for ranking candidates, not as a direct prediction of an individual molecule's immunogenicity.
