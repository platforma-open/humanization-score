# Antibody Humanization Score

**One-liner:** Score antibody sequences for humanness so candidates can be ranked and triaged by humanization burden.

**Status:** Planning Brief

**Urgency:** 5. Preferred timing; therapeutic-antibody clients want it but no hard deadline.

**Importance:** 7. Enables therapeutic-antibody discovery as a credible end-to-end workflow on the platform.

**Size:** S

---

## Overview

**Problem:** Most antibody candidates emerging from discovery campaigns are non-human (mouse, rabbit, llama, chicken, or other animal hosts). Before such a candidate can become a therapeutic, it must be humanized so the human immune system does not recognize it as foreign and mount an anti-drug-antibody (ADA) response. The platform currently has no metric describing how human-like a candidate sequence already is, so humanization burden cannot be factored into lead triage. Candidates that look good on binding and developability get carried forward even when their framework regions sit far from any human germline, and the problem only surfaces later when humanization work begins.

**Value:** Scientists see a humanness score on every antibody sequence in the candidate panel and can rank, filter, and triage by it. Panels of dozens to thousands of post-screening binders can be prioritized by how easy each candidate will be to humanize, alongside existing developability and liability scores. The score is informational at v1 (used for ranking, not hard filtering), which matches how lead optimization teams actually treat humanness: as one factor among several, not a gate.

**Business impact:** Therapeutic-antibody discovery clients expect humanness scoring as part of any antibody discovery workflow. Without it, the platform looks incomplete for that use case. Adding the score closes a visible capability gap and makes the antibody discovery pipeline credible end-to-end.

### Connections

- **Blocks:** `antibody-tcr-lead-selection` (gains a new ranking column), any future antibody-engineering or humanization-assist block.
- **Related:** [sequence-liability-fixability-scoring](../sequence-liability-fixability-scoring/README.md). Same scoring-and-triage shape, same downstream block.

---

## Technical Notes

**Subsystem map:**

- **NEW**: `humanization-score` block (this brief).
- **UNCHANGED**: `antibody-tcr-lead-selection`. Consumes the new score via PColumn discovery; no code changes needed if the score is annotated correctly.
- **UNCHANGED**: upstream sequence sources (MiXCR-derived blocks and `import-vdj-data`). The block consumes the existing antibody amino acid sequence PColumn shape.

### Method Selection Criteria

The chosen scoring method must satisfy:

- **License compatibility** with the platform. Open source preferred; permissive license required for redistribution.
- **Dependency footprint**. Containerization complexity, model weights, and runtime requirements all factor in.
- **Score interpretability** for biologists. A single 0 to 100 humanness percentage is the most legible output; method-specific scales should be rescaled or accompanied by a reference scale.
- **Validation quality**. Methods with published validation against immunogenicity outcomes are preferred, since this determines whether the resulting score can carry `pl7.app/isScore: "true"` (see Open Questions).
- **Modality coverage**. The method, or the block's orchestration around it, must score VHH, mAb, and scFv inputs.
- **Throughput**. The method's per-sequence cost determines whether the block can operate on full repertoires or only on pre-filtered candidate panels (see Open Questions).

The chosen method, its license, the score scale, modality coverage, and any alternatives considered are documented in the block's `description.md`.

### Input Contract

Input is the existing antibody amino acid sequence PColumn produced by MiXCR-derived blocks, `import-vdj-data`, and single-cell B-cell pipelines. The block consumes the same input shape as `antibody-sequence-liabilities` and should follow that block's input handling as the structural precedent (see Related Files).

The block must support all antibody modalities currently available on the platform: VHH, mAb, and scFv.

### Output Contract

One score PColumn per scored chain (heavy, light, or both), value type `Float`, scale chosen so higher means more human (rescale tool output if needed). PColumn naming, axes, and annotations mirror the existing per-sequence score columns in `antibody-sequence-liabilities` and the patterns documented in `sequence-liability-fixability-scoring/pcolumn-spec.md`. Whether the score carries `pl7.app/isScore: "true"` depends on the chosen method's validation status (see Open Questions).

### Related Files (Precedent to Mirror)

| Pattern | File |
|---------|------|
| Per-sequence scoring block structure | `blocks/antibody-sequence-liabilities/` |
| Score PColumn conventions, isScore, defaultCutoff | `docs/text/work/projects/sequence-liability-fixability-scoring/pcolumn-spec.md` |
| Lead Selection integration via PColumn annotations | `blocks/antibody-tcr-lead-selection/model/src/util.ts` |

The new block must use BlockModelV3 (the current workspace convention for new blocks).

---

## Scope

**In scope:**
- Single block that consumes antibody sequence PColumns and emits humanness score PColumn(s).
- Support for VHH, mAb, and scFv input.
- One scoring method, selected and documented by the implementor.
- Score integrated into Lead Selection as a default ranking criterion (auto-applied when the column is present).
- BlockModelV3 scaffolding.
- `description.md` documenting the chosen method, license, score scale, and modality coverage.

**Out of scope:**
- Per-residue humanness output (which positions drag the score down). Requires antibody numbering; deferred to a separate lead-optimization brief.
- Mutation suggestions (back-mutation toward human germline). Same numbering prerequisite, same deferral.
- Multi-method side-by-side scoring. Implementor picks one for v1.
- Hard filtering by humanness score in Lead Selection. Score is exposed as a ranking criterion only.

**Open questions:**
- Does the chosen method's validation justify `pl7.app/isScore: "true"`? Per workspace convention, isScore is reserved for metrics with published validation linking the score to a biological outcome. The implementor sets this based on whether the chosen method carries such validation.
- Throughput and input scale. Whether the chosen method scales to a full repertoire (millions of clonotypes) or requires pre-filtering to a candidate panel upstream via Lead Selection. The implementor benchmarks the chosen method and documents the practical input size limit.
- Score normalization. Recommendation: rescale tool output to a 0 to 100 (or 0 to 1) range so the column stays interpretable independent of the underlying method, since the method may change in v2.

---

## Success Criteria

*Draft. Refined at Specification stage.*

- [ ] Block builds, installs, and runs against a sample antibody dataset.
- [ ] Block produces a humanness score PColumn per scored chain.
- [ ] Score column is wired into Lead Selection as a default ranking criterion (auto-applied when the column is present).
- [ ] Block runs successfully on each supported modality: VHH, mAb, and scFv.
- [ ] On a panel mixing known human and known non-human antibodies, human sequences score higher than non-human sequences as a group.
- [ ] `description.md` documents the chosen method, license, and scale.
- [ ] Block passes `pnpm build` and integration tests.

---

## References

- Related project: [sequence-liability-fixability-scoring](../sequence-liability-fixability-scoring/README.md)
- Structural precedent block: `blocks/antibody-sequence-liabilities/`
- Lead Selection block: `blocks/antibody-tcr-lead-selection/`