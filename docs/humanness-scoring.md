# Humanness Scoring — Final Specification

This is the authoritative spec for what the block **must do**. It is deliberately split into
two layers so it is clear what is *fact* and what is *our choice*:

- **§2 Requirements** — grounded in the actual scoring tool (promb / OASis / BioPhi) and its
  reference database (OAS). Every requirement cites a primary source. These are not opinions;
  they are the input/output contract of the tool that computes the score. You do not need to
  understand the biology — you trust the source.
- **§3 Decisions** — product/engineering choices the sources do **not** dictate. Each has an
  **OWNER** and a **STATUS**. `PENDING` items must be confirmed by the domain reviewer / product
  owner before they are treated as settled.

> Provenance note: the original idea note (`humanness-scoring-block.md`) contained **no** data
> contract — only a tool shortlist and "FASTA in, scored out". The requirements below were
> reconstructed from the tools' own documentation/paper (§2) and from the upstream data producer
> `mixcr-clonotyping`. Citations are verbatim; sources in §5.

---

## 1. What the block does (one paragraph)

The block estimates antibody **humanness** — how closely an antibody's amino-acid sequence
resembles sequences in natural human antibody repertoires — as a proxy for immunogenicity risk.
It uses **promb** (Merck/MSD), a lightweight reimplementation of **OASis** (the humanness score
from **BioPhi**, Prihoda et al., *mAbs* 2022), which scores a sequence against the human
**Observed Antibody Space (OAS)** repertoire. Higher score = more human = lower expected
immunogenicity risk.

---

## 2. Requirements (tool-grounded — each cites a source)

### R1 — The scoring unit is one chain's full variable domain (FR1–FR4)
The tool scores the **complete variable-domain amino-acid sequence of a single antibody chain**
(framework + CDR regions: FR1-CDR1-FR2-CDR2-FR3-CDR3-FR4), supplied whole. The 9-mer chopping is
internal to the tool — the caller supplies the whole variable region, never pre-cut fragments.
> BioPhi paper [S3]: input is *"variable heavy and light chain sequences"* / *"amino acid
> sequences of antibody variable regions"*; OASis works by *"chopping it into all overlapping
> 9-mer peptides."* promb's `compute_peptide_content` worked example [S1] feeds a full VH
> variable domain (`QVQLVQSG…VTVSS`, i.e. FR1..FR4) and returns `0.714`.

**Implication:** the block must feed a contiguous variable-domain sequence — ideally the whole
domain (`VDJRegion`/`VDJRegionInFrame`). The reviewer has widened the accepted input to also
include *contiguous partial* domains that still cover most of the framework (see decision D2 in
§3b); the hard constraint is that whatever is fed is a real, gap-free subsequence in natural
order (see the contiguity rule in §3a), never pre-cut fragments stitched across non-adjacent
regions or chains.

### R2 — Heavy and light chains are scored separately; never concatenated
VH and VL are **separate scoring units**, each producing its own score, each compared against
its **own chain-type repertoire**. They are never joined into one string. A "paired antibody"
score is the **average of the two per-chain scores**, computed only after each chain is scored
independently.
> README [S2] (verbatim): *"Both chains of each antibody should have the same ID with an
> optional `_VL/_VH` or `_HC/_LC` suffix."*  Paper [S3]: prevalence is computed against *"the
> total number of subjects for the given chain type"*; *"Humanness scores of each therapeutic
> were calculated as averages of the scores of their chains."*

**Implication:** single-cell must score Heavy and Light separately (one column each); the block
must never concatenate chains. (Directly addresses the reviewer's "do not join both chains".)

### R3 — Method: fraction of 9-mers found in the human repertoire
The score is computed by sliding **all overlapping 9-residue (9-mer) windows** across the chain
and counting the fraction that appear in the human OAS reference.
> promb README [S1]: `promb exact -d human-reference -l 9 …`; *"Use `compute_peptide_content` to
> compute OASis-like score (% of peptides that are human, exact match)"* (example → `0.714`).
> Paper [S3]: *"OASis is a novel antibody humanness score based on exact 9-mer peptide search in
> the OAS."*  The reference is antibody-specific: *"all overlapping 9-mer peptides were extracted
> from variable heavy and light chains found in OAS repertoires that were linked to a single
> human subject."*  promb's bundled `human-oas` DB = *"antibody peptides found in ≥10% of
> subjects."*

### R4 — A fragment (e.g. CDR3 alone) is NOT a valid scoring unit
Scoring CDR3 — or any single region — instead of the full variable domain is invalid. HCDR3 is
the principal **hypervariable, non-germline** region; scored in isolation it spuriously reads as
"non-human" and does not measure humanness.
> Frontiers Immunol. 2018 [S6]: *"the theoretical HCDR3 diversity exceeds 10^15 variants,
> generated from fixed genomic sequences by combinatorial and junctional diversification"*; *"the
> HCDR3 is necessary, albeit insufficient, for specific antibody binding."*  Combined with R1
> (the tool's input is the whole variable region), a fragment is not a valid input.

**Implication:** if only CDR3 (or an incomplete domain) is available, the score is not
computable — see decision D1. (Addresses the reviewer's "calculated over CDR3 … very poor score,
not the right one".)

### R5 — Antibodies only; T-cell receptors must be rejected
The reference (OAS) is an **antibody / immunoglobulin (BCR) database only** — it contains **no
TCR data**. Scoring a TCR against it is meaningless.
> OAS [S4]: *"Observed Antibody Space: A diverse database of cleaned, annotated, and translated
> unpaired and paired antibody sequences"*; its contents are 100% VH+VL from BCR-seq. The same
> lab built a **separate** "Observed T cell receptor Space" (OTS) for TCRs — proving OAS itself
> has none.

**Implication:** the block must reject TCR input (selectors + workflow guard). (Addresses the
reviewer's "Block accepts TCR input, it shouldn't".)

### R6 — Sequences shorter than the 9-mer window are unscoreable
A sequence shorter than 9 residues yields zero 9-mer windows and cannot be scored.
> By mechanism of R3 (window length 9). *Not separately documented in the tool* — see caveat C3.

**Implication:** such inputs → `null` score, never a failure of the whole run.

### R7 — Per-residue "which positions are non-human" (deliverable, optional)
The idea note promises per-residue non-human flags. promb/OASis does **not** provide this (it is
peptide-level). Per-residue humanness comes from **Sapiens** or **AntPack**.
> BioPhi README [S2]: `biophi sapiens mabs.fa --scores-only` → *"Sapiens probability matrix
> (score of each residue at each position)"*. AntPack [S7]: `calc_per_aa_probs` returns a
> per-position log-probability array, *"enables easy identification of low-probability
> residues."*

**Implication:** the per-residue deliverable is out of scope for the score itself and tracked
separately (see D4 / [`TODO.md`](./TODO.md)). Note promb does ship an *approximate* per-residue
method (`compute_positional_likelihood`) worth evaluating before adopting a new tool.

---

## 3. What logically follows, and the few real open decisions

This section derives behavior **from the requirements (§2)**, not from anyone's preference.
Most apparent "choices" are actually forced by R1–R7. Only a small set are genuinely open.

### 3a. Consequences of the requirements (NOT choices)

These follow directly from §2 — there is nothing to decide:

- **Below the coverage floor → `null` (unscoreable).**
  R4 says a fragment (e.g. CDR3) is not a valid scoring unit; R6 says an unscoreable input yields
  `null` and never crashes the run. So when there is not enough contiguous framework to score
  honestly — at the extreme, only CDR3 — the **logical, tool-consistent behavior is to emit
  `null`**, the same as a too-short sequence. Where that floor sits is a reviewer call (D2 below).
  Crashing the whole run ("hard-fail") is **not** implied by the tool or the research; it is a
  separate UX overlay.
  *Surfacing a warning that explains why (so the user knows to re-run clonotyping by VDJRegion)
  is good practice, but the score itself is `null`, not an error.*
  > ⚠️ The implementation (workflow Phase 3) was originally built to **hard-fail** (`ll.panic`);
  > per this spec it has since been changed to emit `null` + a non-fatal warning.

- **The join, if any, must be contiguous (correctness rule — not a choice).**
  The score is the fraction of 9-mer windows found in human OAS (R3). A window is only "real" if
  its 9 residues actually sit next to each other in a natural sequence. Therefore the block may
  assemble a domain from its per-region features **only by concatenating naturally-adjacent
  regions in canonical order** (FR1-CDR1-FR2-CDR2-FR3-CDR3-FR4), single chain, one consensus per
  clonotype. Stitching non-adjacent regions, mixing chains, or gluing heterogeneous reads
  fabricates junction 9-mers that never occur in nature and corrupts the score — the same defect
  R2 forbids for chains. A *contiguous partial* domain (missing leading regions, e.g.
  `CDR1_TO_FR4` or `FR2_TO_FR4`) is fine because it is still a gap-free subsequence; an
  incoherent stitch is not.
  > Reference implementation of a correct join: the **paratope-clustering** block
  > (`workflow/src/main.tpl.tengo`) pulls each region as its own `pl7.app/vdj/feature`
  > amino-acid column, keeps **primary** chains only and orders them deterministically
  > (`normalizePrimaryChainOrder`), then concatenates in FR1→FR4 order (with `FR4→FR4InFrame`
  > fallback). Same template applies here.

- **Single-cell secondary-rank rearrangement → `null`.**
  It is CDR3-only upstream → below the coverage floor (D2). Same rule as everything else; not a
  special case and not a separate decision.

- **Per-chain-type reference is required (not optional).**
  R2 says each chain is scored against its **own chain-type** repertoire (VH vs heavy, VL vs
  light). Therefore scoring VL against a non-light reference is **incorrect**, not a tunable
  trade-off. If promb's bundled `human-oas` does not split by chain type, that is a **fidelity
  defect to fix** (chain-split DB or BioPhi), not a decision to accept. See §6/C2.

### 3b. Decisions (need an owner)

**D2 is confirmed and in current scope** — it is part of what the block must do now and drives
the upcoming implementation. **D4/D5/D6 are deferred** future improvements, tracked in detail
(problem, options, recommendation) in [`TODO.md`](./TODO.md).

| ID | Decision | What the research implies | Owner | Status |
|----|----------|---------------------------|-------|--------|
| **D2** | Coverage floor: how much of the domain must be present to score? **Decided: accept any *contiguous* domain covering ≥3 of the 4 framework regions** (`VDJRegion`, `CDR1_TO_FR4`, `FR2_TO_FR4`); reject ≤2 FRs (`CDR2_TO_FR4`, CDR3-only) → `null`. | R1 wants the whole domain and R3/R4 say framework carries the signal while CDR3 alone reads spuriously low; the *exact* floor is a reviewer judgment, not forced by the sources. | Reviewer | **CONFIRMED** (2026-06-04) — widens the old "full-domain only" default. **In current scope: to be implemented now** (region assembly + coverage gate); see §3b implementation note below. |
| **D4** | Is the per-residue "non-human positions" deliverable (R7) in scope now, and via promb's own `compute_positional_likelihood`, Sapiens, or AntPack? | R7 only tells us the OASis *score* is peptide-level; scope/timing/tool choice is a product call. | Product + reviewer | **PENDING** |
| **D5** | Which number do we expose: raw **OASis identity** (what promb gives, our current `fraction×100`) or the calibrated **OASis percentile** (BioPhi's interpretable "5–7% murine / 80% human")? | The **percentile** is the meaningful, comparable metric — but it requires BioPhi's 544-mAb calibration; promb alone cannot produce it. So this is really "stay on promb (identity, label honestly) **vs** adopt BioPhi (percentile)". | Product + eng | **PENDING** |
| **D6** | Given R2 mandates a per-chain reference, do we fix promb (chain-split `human-oas`) or move to full BioPhi? | R2 makes per-chain *required*; the only open part is the engineering route. Tied to D5 (BioPhi gives both percentile **and** per-chain split). | Eng | **PENDING** |

**D2 implementation note (current scope).** The work splits across the two layers where each is
idiomatic — the **workflow selects the source columns**, the **scorer assembles + gates per row**:

1. **Workflow — column selection/routing** (`workflow/src/main.tpl.tengo`). The prepare phase
   pulls the per-region amino-acid features in addition to `VDJRegionInFrame`, reusing the
   **paratope-clustering** template (`workflow/src/main.tpl.tengo:41`): each region via
   `pl7.app/vdj/feature` (`FR1, CDR1, FR2, CDR2, FR3, CDR3, FR4`, with `FR4→FR4InFrame` fallback);
   `normalizePrimaryChainOrder` keeps **primary** chains only and orders them deterministically.
   Per scoring unit it then routes the source: prefer the single `VDJRegion` column when present;
   otherwise hand that chain's per-region columns to the scorer. Tengo cannot concatenate strings
   per row, so it never assembles — it only chooses.
2. **Scorer — assembly + coverage gate** (`software/src/main.py`). Given the per-region columns
   it assembles each row by concatenating in canonical FR1→FR4 order, but **contiguity is judged
   against the full canonical 7-region template**, so a region that is absent *as a column* (not
   just sentinel-valued) is a hole and breaks the run — never gluing non-adjacent regions (§3a).
   It then counts framework regions in the contiguous run; `<3` FRs → `null`. This per-row work
   (string concatenation, template-aware contiguity, FR count) lives in polars because it is
   row-wise — the same division paratope-clustering uses (tengo pulls/orders, Python joins).

> Net (D5/D6): D5 and D6 point the same way — **promb is a lightweight approximation; faithful
> OASis humanness (per-chain reference + interpretable percentile) is BioPhi.** The real decision
> is whether the promb approximation is acceptable for this milestone or we adopt BioPhi.
> See [`TODO.md`](./TODO.md) for the full breakdown of D4/D5/D6.

---

## 4. Behavior by modality (applying the requirements)

- **Bulk / VHH (single chain):** score the chain's full variable domain (R1); one score per
  clonotype. VHH is just a single heavy variable domain — same path.
- **Single-cell (paired):** score Heavy and Light **separately** (R2) over each chain's variable
  domain; one score column per chain type. Score the **primary**-rank rearrangement of each chain
  type; **secondary**-rank is CDR3-only upstream → below the D2 floor → `null`. Never join chains.
- **scFv:** engineered VH-linker-VL. Biologically each domain would be split at the linker and
  scored separately (R1/R2), linker excluded. **But the current upstream emits no scFv data** —
  scFv is descoped until a producer/column contract exists.
- **TCR:** rejected (R5).
- **CDR3-assembled dataset (no `VDJRegion`):** the other regions can still be pulled and
  **contiguously** assembled (per the §3a contiguity rule, paratope-clustering template). If the
  assembly clears the D2 floor (≥3 contiguous FRs) it is scored; otherwise the row is honestly
  `null` (sub-floor or incoherent stitch) — **not** a run failure. The non-fatal warning is
  reserved for the case where a chain has **nothing assemblable at all** (no `VDJRegion` and no
  region columns); sub-floor coverage just yields `null` per row, no warning needed.
- **Short / sub-floor / incoherent sequence:** `null` (R6 / D2 / §3a), with a non-fatal warning.

---

## 5. Sources

- **[S1] promb** (Merck/MSD) — repository & README: https://github.com/MSDLLCpapers/promb/blob/main/README.md
- **[S2] BioPhi** (Merck) — repository & README: https://github.com/Merck/BioPhi/blob/main/README.md
- **[S3] OASis / BioPhi paper** — Prihoda et al., *mAbs* 2022 (preprint): https://www.biorxiv.org/content/10.1101/2021.08.08.455394v1 · journal: https://www.tandfonline.com/doi/full/10.1080/19420862.2021.2020203 · PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC8837241/
- **[S4] Observed Antibody Space (OAS)** — Olsen, Boyles, Deane: https://pmc.ncbi.nlm.nih.gov/articles/PMC8740823/ · webapp: https://opig.stats.ox.ac.uk/webapps/oas/
- **[S6] HCDR3 hypervariability** — Frontiers in Immunology 2018: https://www.frontiersin.org/journals/immunology/articles/10.3389/fimmu.2018.00395/full
- **[S7] AntPack** — per-residue scoring tutorial: https://antpackdocumentationlatest.pages.dev/scoring_tutorial · **Sapiens** (Merck): https://github.com/Merck/Sapiens

---

## 6. Implementation-fidelity caveats (read before trusting numbers)

These are gaps between **our promb-based implementation** and the **authoritative BioPhi/OASis**
definition. They do not change the requirements (§2) but matter for interpreting output:

- **C1 (scale, = D5):** we emit raw OASis *identity* × 100, not the OASis *percentile*. Do not
  compare our numbers to published "% human" percentiles without converting. Tracked in
  [`TODO.md`](./TODO.md) (D5).
- **C2 (chain reference, = D6):** **confirmed** — promb's bundled `human-oas` is a single pooled
  set (`resources/OASis_9mers_v1_10perc_subjects.txt.gz`, ~5.7M 9-mers) and
  `compute_peptide_content(seq)` takes no chain-type argument, so it does **not** split the
  reference by chain type the way BioPhi does (R2). Light-chain scores carry a systematic but
  unmeasured bias. Tracked in [`TODO.md`](./TODO.md) (D6), including a cheap step to quantify it.
- **C3 (min length):** the 9-residue floor (R6) is inferred from the method, **not** documented
  in promb/BioPhi. Verify directly against the code; our implementation already nulls `<9 aa`.
- **C4 (threshold):** OASis identity depends on a tunable per-subject prevalence threshold
  (loose 1% / relaxed 10% / medium 50% / strict 90%). promb's `human-oas` is built at **≥10%**.
  A claim that 10% is a *fixed default* was **refuted** in research — it is a parameter. If we
  ever expose stringency, this is the knob.
