# Overview

Identifies sequence liabilities in antibody/TCR or peptide amino acid sequences and classifies them by fixability — how tractable each liability is to engineer away. This lets you distinguish candidates that need a quick conservative substitution from those requiring significant reengineering or that are not viable.

The block evaluates sequences for deamidation (`N[GS]`, `N[AHNT]`, `[STK]N`), fragmentation (`DP`, `TS`), isomerization (`D[DGHST]`), N-linked glycosylation (`N[^P][ST]`), oxidation-prone residues (tryptophan, methionine), cysteine issues (missing or extra), and integrin binding motifs. The set of applicable rules adapts to modality: antibody/TCR inputs are evaluated per CDR and framework region and include architecture-specific cysteine and hinge-fragmentation checks, while peptide inputs apply a flat backbone-chemistry rule set without region or cysteine-architecture checks.

Two output columns are emitted for both modalities:

- **Developability risk** — `None` / `Low` / `Medium` / `High` / `Very High` / `Non-Developable`: engineering severity for fixable liabilities at the lower end of the scale; `Very High` when a Hard to fix liability is present (e.g. Extra Cysteines); `Non-Developable` when a Structural liability is present (e.g. Missing Cysteines)
- **Developability cost** — continuous score: sum of engineering effort weighted by fixability class (antibody mode also weights by region importance); lower = easier to engineer

Antibody/TCR inputs additionally produce:
- **Is Productive** — `Pass`/`Fail`: fails on stop codons or out-of-frame sequences

You can extend the predefined liability set with custom motifs defined in the block settings or imported from a JSON file.

# Humanness Score

In addition to liability-based developability outputs, the block emits a **Humanness Score** column for both antibody/TCR and peptide modalities.

## Method

- **Library**: [promb](https://github.com/MSDLLCpapers/promb) v1.0.2 (PyPI; MIT license).
- **Database**: `human-oas` — curated 9-mer peptide set derived from human antibody repertoires (Observed Antibody Space).
- **Function**: `PrombDB.compute_peptide_content(seq)` — fraction of 9-mer windows in `seq` found in the human-oas peptide set, returned as a value in `[0, 1]`.
- **Output**: rescaled to `[0, 100]` (multiplied by 100, rounded to 2 decimals). **Higher = more human.** Not inverted; no transformation.
- **Coverage**: alignment-free, works uniformly across modalities (VHH, mAb, scFv, peptide) without per-modality configuration. For antibody/TCR mode, all `* aa` sequence columns of a clonotype are concatenated and scored as one string.
- **Unscoreable inputs**: sequences shorter than the 9-mer window (`<9 aa`), empty strings, or any internal scoring exception yield a null score (the cell is empty in the output TSV); the pipeline never fails on a single bad row.

## Validation and rationale

The OASis-style 9-mer match is conceptually inherited from BioPhi/OASis (Prihoda et al., *mAbs* 2022, [doi:10.1080/19420862.2021.2020203](https://doi.org/10.1080/19420862.2021.2020203)). The metric correlates with humanness of FDA-approved therapeutic antibodies. It is **not** a direct predictor of anti-drug-antibody (ADA) response or immunogenicity. The score is annotated with `pl7.app/isScore: "true"` and `pl7.app/score/rankingOrder: "decreasing"` so downstream selection blocks (Lead Selection, etc.) can rank candidates with higher = better.

## Known limitations

- Sequences shorter than 9 aa are not scoreable (output: null).
- The `human-oas` corpus is the only database wired in; framework vs CDR are not weighted differently — every 9-mer window contributes equally.
- promb is a single-maintainer repository (latest release May 2025); should be re-validated when upstream updates land.

## Throughput

Measured locally on `humanness-calc-script` (Apple Silicon, Python 3.13):

- **Database initialization** (`init_db('human-oas')`): ~1.75 s (one-time per process; cached via `functools.lru_cache`).
- **Per-sequence latency** on full-length VH sequences (~115 aa): ~0.015 ms / sequence (30-sequence batch). Per-row scoring overhead is dominated by polars I/O, not promb.
