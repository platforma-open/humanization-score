# Humanness Score

Score antibody sequences for humanness — how human-like a sequence looks relative to natural human antibody repertoires. This Platforma block implements the OASis method: it measures the fraction of 9-residue windows in a variable domain that occur in human antibody repertoires from OAS (Observed Antibody Space), and reports it as a 0–100 score you can rank and filter candidates by.

Open-source analysis block for Platforma, the biologics discovery platform by MiLaboratories. For the full no-code workflow, see [platforma.bio](https://platforma.bio/).

> **Naming:** this block appears as **Humanness Score** in the Platforma app

## What it does

Among otherwise comparable candidates, more human-like sequences are generally preferred — they tend to carry lower immunogenicity risk. The Humanness Score block quantifies that so it becomes a sortable column rather than a judgement call.

The score follows the **OASis** method. Every overlapping 9-residue window (9-mer) in the antibody variable domain is checked against a reference peptide set derived from human antibody repertoires in OAS; the fraction found is rescaled to 0–100, where higher is more human-like. The method is alignment-free, so it needs no germline assignment or numbering scheme and works across antibody formats — nanobody (VHH), mAb, and scFv.

Scoring is done per chain, within one chain. Bulk and VHH datasets produce a single **Humanness Score** column. Paired datasets produce two — **Humanness Score, Heavy** and **Humanness Score, Light** — so you can see which chain drives a low score. Windows are never formed across a chain boundary or across a gap between non-adjacent regions, because that would fabricate 9-mers that do not occur in nature.

Results appear as a per-clonotype table and a score distribution histogram, and the score is available in [Lead Selection](https://github.com/platforma-open/antibody-tcr-lead-selection) as a ranking criterion.

## Inputs & outputs

* **Input:** antibody (Ig) amino acid variable-region sequences from bulk or single-cell clonotypes — [MiXCR Clonotyping](https://github.com/platforma-open/mixcr-clonotyping), [MiXCR scFv Alignment](https://github.com/platforma-open/mixcr-scfv-clonotyping), or [Import V(D)J Data](https://github.com/platforma-open/import-vdj-data). Scoring needs a contiguous variable region covering at least 3 of the 4 framework regions; a fully assembled VDJRegion is used when present, otherwise adjacent FR/CDR regions are assembled. T-cell receptors are not supported and are not offered as input.
* **Output:** a Humanness Score column per clonotype (one per chain for paired data) on a 0–100 scale, plus a sortable table and a score distribution histogram. Downstream blocks can consume the score as a ranking or filtering criterion.

## Specifications

| | |
|---|---|
| Block title in app | Humanness Score |
| Method | OASis — fraction of 9-mer windows found in human antibody repertoires (OAS), rescaled to 0–100 |
| Implementation | [promb](https://github.com/MSDLLCPapers/promb) (Merck & Co.), MIT |
| Reference set | `human-oas` peptide set, derived from Observed Antibody Space |
| Molecule types | Antibodies only — nanobody (VHH), mAb, scFv. |
| Sequence requirement | Amino acid variable region covering ≥ 3 of 4 framework regions; sequences under 9 aa are unscoreable |
| Score direction | Higher = more human-like |
| Outputs | Humanness Score per clonotype per chain; table; score distribution histogram |

## Use cases

* **Rank candidates on immunogenicity risk:** add humanness as a criterion in [Lead Selection](https://github.com/platforma-open/antibody-tcr-lead-selection) so more human-like sequences are preferred among comparable candidates.
* **Triage a humanization campaign:** score a panel of humanized variants against their parental sequence to see which designs moved closest to natural human repertoires.
* **Screen non-human-derived libraries:** flag murine, llama, or synthetic-origin candidates that will need humanization before they progress.
* **Chain-level diagnosis:** on paired data, compare Heavy and Light scores to see which chain is responsible for a low overall humanness.
* **Developability panel:** combine with [Sequence Liabilities](https://github.com/platforma-open/antibody-sequence-liabilities) so candidates are assessed for both immunogenicity risk and specific liability motifs.
* **Library-level view:** read the score distribution to see whether a library is broadly human-like or contains a distinct non-human population.


## FAQ

### What is a humanness score?

A measure of how closely an antibody sequence resembles antibodies found in natural human repertoires. It is used as a proxy for immunogenicity risk: sequences that look human are less likely to provoke an anti-drug antibody response, so among comparable candidates the more human-like ones are usually preferred.

### What counts as a good score?

There is no universal cutoff. The score is designed for relative comparison — rank candidates within your own panel, or compare humanized variants against their parental sequence, rather than applying a fixed threshold.

### Does the score predict immunogenicity for a given molecule?

No. The published validation shows that OASis separates human from non-human sequences and correlates with anti-drug antibody rates across a panel of 216 therapeutic antibodies. That is a population-level correlation, not a per-molecule prediction. Treat it as a humanness proxy for ranking, not as a clinical immunogenicity forecast.

### Can I score TCRs or peptides?

No. The OAS reference set contains antibody sequences only, so the block applies to antibodies (Ig) exclusively. TCR datasets are not offered as input, and peptides are out of scope.

### What sequences does it need?

Amino acid variable-region sequences covering at least 3 of the 4 framework regions. A fully assembled variable domain (VDJRegion) is ideal. Clonotypes assembled by a short feature such as CDR3 alone, or CDR1:CDR3, do not carry enough of the domain — the block reports that clearly and returns a null score instead of failing. Re-run clonotyping with full or partial (≥ 3 framework) variable-region assembly to get scores.

### Are heavy and light chains scored together?

No. Each chain is scored independently, and paired datasets return separate Heavy and Light scores. Windows are never formed across the chain boundary, since a heavy–light junction 9-mer does not occur in nature.

### Does it work on nanobodies and scFvs?

Yes. The method is alignment-free and format-agnostic. Single-domain formats such as VHH produce one score; scFv and paired formats produce a score per chain.

## References:

If you use this block in your research, please cite the OASis method and the OAS database:

> Prihoda, D., Maamary, J., Waight, A., Juan, V., Fayadat-Dilman, L., Svozil, D., & Bitton, D. A. (2022). BioPhi: A platform for antibody design, humanization, and humanness evaluation based on natural antibody repertoires and deep learning. *mAbs* **14**(1), 2020203. [https://doi.org/10.1080/19420862.2021.2020203](https://doi.org/10.1080/19420862.2021.2020203)

> Olsen, T. H., Boyles, F., & Deane, C. M. (2022). Observed Antibody Space: A diverse database of cleaned, annotated, and translated unpaired and paired antibody sequences. *Protein Science* **31**(1), 141–146. [https://doi.org/10.1002/pro.4205](https://doi.org/10.1002/pro.4205)

## Part of the Platforma ecosystem

This block is part of [Platforma](https://platforma.bio/) by [MiLaboratories](https://github.com/milaboratory), built on [promb](https://github.com/MSDLLCPapers/promb) and the [Observed Antibody Space](https://opig.stats.ox.ac.uk/webapps/oas/) database. Explore the other open-source blocks at [github.com/platforma-open](https://github.com/platforma-open) and the docs for antibody discovery at [docs.platforma.bio/biology-guides/antibody-discovery](https://docs.platforma.bio/biology-guides/antibody-discovery/).
