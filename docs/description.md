# Overview

Scores antibody amino-acid sequences for **humanness** — how human-like a sequence looks relative to natural human antibody repertoires. The score is intended as a ranking criterion in Lead Selection: among otherwise comparable candidates, more human-like sequences are generally preferred because they tend to carry lower immunogenicity risk.

The block emits a single output column, **Humanness Score** (`humanness_score`). The value is a float in **[0, 100]**, where **higher = more human**. The column is published with the spec name `pl7.app/humannessScore` (valueType `Double`) and is annotated as a score so downstream blocks can pick it up automatically.

# Method

- **Library**: [promb](https://github.com/MSDLLCPapers/promb) (`promb>=1.0.2`, PyPI; author David Prihoda / Merck & Co.).
- **Database**: `human-oas` — a curated 9-mer peptide set derived from human antibody repertoires in **OAS (Observed Antibody Space)**, the Oxford OPIG resource of cleaned, annotated, translated antibody sequences.
- **Approach**: **OASis-style** humanness scoring. The score is the fraction of overlapping **9-mer (9-residue) windows** in the sequence that are found in the `human-oas` peptide set. This is the same exact-9-mer-match idea introduced in BioPhi/OASis (see *Validation*).
- **Function**: `init_db("human-oas").compute_peptide_content(seq)` returns the matching 9-mer fraction in `[0, 1]`.
- **Output**: rescaled to `[0, 100]` (multiplied by 100, rounded to 2 decimals). The score is **not** inverted and carries no other transformation — higher = more human.

# Score scale

- Range: **[0, 100]**, continuous (Float / `Double`).
- Orientation: **higher = more human** (`pl7.app/score/rankingOrder: "decreasing"`, i.e. larger values rank first).
- **Unscoreable inputs → null**: a sequence shorter than the 9-mer window (`< 9 aa`) cannot produce a single 9-mer and yields a **null** score (empty cell). Empty strings and any internal scoring exception also yield null — the pipeline never fails on a single bad row.

# Modality coverage

The metric is alignment-free and works uniformly across antibody formats without per-format model configuration:

- **Antibody** — VHH, mAb, scFv. The block runs in clonotype mode: for each clonotype, every `* aa` sequence column is concatenated into a single string and scored as one number (`humanness-calc-script/src/main.py`). A single per-clonotype score is produced; per-chain (heavy/light) breakdown is not currently emitted.

Peptide input is intentionally **out of scope** — humanness scoring is not meaningful for non-antibody peptides.

# License

- **promb** (the scoring code): **MIT License**, Copyright © 2025 Merck & Co., Inc. Confirmed from the installed package metadata (`promb-1.0.2.dist-info/licenses/LICENSE`, `License: MIT`). Permissive; compatible with redistribution.
- **OAS data** (the basis of the `human-oas` peptide set): the OAS database is published by Oxford OPIG under **CC-BY 4.0** (attribution required). The `human-oas` set shipped with promb is a derived artifact.

⚠️ **OPEN ITEM (license)**: The MIT license of the promb code is confirmed. What still needs explicit sign-off is the redistribution status of the *bundled `human-oas` database artifact* inside the promb wheel — i.e. that shipping that derived data through the platform satisfies the OAS CC-BY 4.0 attribution requirement. promb itself is MIT, but the embedded data's attribution obligations should be confirmed before release.

# Validation and `isScore` decision

The score is currently annotated with **`pl7.app/isScore: "true"`** plus `pl7.app/score/rankingOrder: "decreasing"` and `pl7.app/score/method: "promb / OASis (human-oas)"`. This makes it eligible as a **default ranking criterion** in Lead Selection.

The brief sets a bar: `isScore: "true"` should be set **only** if the method has published validation against immunogenicity. The OASis method (which promb's `human-oas` scoring follows) does have published validation:

- **Prihoda et al., *mAbs* 2022** ([doi:10.1080/19420862.2021.2020203](https://doi.org/10.1080/19420862.2021.2020203)). OASis separates human from non-human sequences with high accuracy and **correlates with clinical immunogenicity** on a panel of 216 paired therapeutic antibodies (percentage of patients developing an anti-drug-antibody / ADA response).

So the `isScore: "true"` decision is defensible: the underlying method has published immunogenicity-correlation evidence, and the score is used for *ranking only* (never as a hard filter).

⚠️ **OPEN ITEM (validation)**: Two caveats remain. (1) The published validation is for OASis as implemented in BioPhi; this block uses **promb's** `human-oas` reimplementation of the same 9-mer approach — equivalence in score values has not been independently re-verified here. (2) A correlation with population-level ADA rates is **not** a per-sequence immunogenicity predictor; the score is a humanness proxy, not a direct ADA prediction. The internal sanity test ("human" vs "non-human" panel scores apart) is **not yet run** (PLAN §8); it should be completed to confirm the wrapper preserves the intended meaning of the score.

# Performance benchmark

⚠️ **OPEN ITEM / TODO (performance)**: A representative per-sequence latency / throughput benchmark has **not** been measured yet (PLAN §5 not done), so a practical input-size ceiling is not established. Notes for when it is measured: the `human-oas` DB load is one-time per process (cached via `functools.lru_cache`), and per-row scoring is a 9-mer membership lookup rather than a model inference. Do not rely on any throughput figure until this is measured and recorded here.

# Alternatives considered

A short, honest comparison of OASis-style scoring against other humanness methods. Detailed per-method rejection notes are not documented elsewhere, so this is kept high-level:

- **BioPhi / OASis** — the published reference implementation of this exact 9-mer approach. promb is effectively a lightweight, standalone packaging of the same OASis scoring (same author), which is why it was chosen: open-source (MIT), small footprint, no model weights, OAS-based, and it returns a single interpretable number.
- **AbNatiV** — VAE-based nativeness/humanness model; heavier (deep-learning weights, larger runtime footprint).
- **Hu-mAb** — random-forest humanness classifier; more dependencies and less direct to package as a single-number scorer.
- **IgReconstruct** — germline-reconstruction-based humanness; oriented more toward humanization design than a lightweight ranking score.

**Why promb / OASis**: open-source and permissively licensed, lightweight (no model weights, fast membership lookup), produces a single number that rescales cleanly to a method-independent 0–100 scale, is grounded in the OAS human repertoires, and has published immunogenicity-correlation validation. The 0–100 normalization keeps the block's output contract stable if the scoring engine is swapped in a future version.
