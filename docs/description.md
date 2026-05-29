# Overview

Scores antibody amino-acid sequences for **humanness** — how human-like a sequence looks relative to natural human antibody repertoires. Among otherwise comparable candidates, more human-like sequences are generally preferred because they tend to carry lower immunogenicity risk.

The block emits a single column, **Humanness Score**, ranging from 0 to 100, where higher values are more human-like. The score is available in Lead Selection as a ranking criterion.

The score follows the **OASis** method: it is the fraction of overlapping 9-residue windows (9-mers) in a sequence that are found in a reference peptide set derived from human antibody repertoires in **OAS (Observed Antibody Space)**, rescaled to 0–100. The metric is alignment-free and works across antibody formats (VHH, mAb, scFv); for paired formats the heavy and light chains are scored together, giving one value per clonotype. Sequences shorter than 9 amino acids cannot produce a 9-mer and are left blank. Peptide (non-antibody) input is out of scope.

# Method and validation

The block uses the [promb](https://github.com/MSDLLCPapers/promb) library (David Prihoda / Merck & Co.). The OASis method it implements has published validation against clinical immunogenicity — it separates human from non-human sequences with high accuracy and correlates with anti-drug-antibody (ADA) rates across a panel of 216 therapeutic antibodies:

> Prihoda et al. BioPhi: an open-source platform for antibody design, humanization, and humanness evaluation. _mAbs_, 2022. [doi:10.1080/19420862.2021.2020203](https://doi.org/10.1080/19420862.2021.2020203)

The evidence is a correlation with population-level ADA rates, not a per-sequence predictor; treat the score as a humanness proxy for ranking candidates, not as a direct prediction of an individual molecule's immunogenicity.

# License

The MIT license on the promb repository covers only the code. The bundled reference databases are governed by the terms of their upstream sources.

| Component | License | Commercial use | Obligation |
|---|---|---|---|
| **promb** (scoring code) | MIT, © 2025 Merck & Co., Inc. | Yes | — |
| **Human SwissProt** (UniProt, UP000005640) | CC-BY 4.0 | Yes | attribution |
| **Human OAS** (`human-oas` peptide set) | CC-BY 4.0 | Yes | attribution + citation |

There is no licensing restriction for commercial use; the only obligation is attribution — credit UniProt and OAS, and cite the relevant OAS publications:

> Olsen, Boyles, Deane. Observed Antibody Space: A diverse database of cleaned, annotated, and translated unpaired and paired antibody sequences. _Protein Science_, 2021.
