#!/usr/bin/env python3
"""Antibody-mode entry point for humanness scoring.

Contract (one chain in, one score out). The input Parquet carries a key column
(`clonotypeKey`), optionally a chain-identifier column (carried through
unchanged), and the variable-region sequence in ONE of two accepted shapes:

1. Full-domain shape (fast path): **exactly one** amino-acid sequence column
   (its name ends with " aa", e.g. "VDJRegion aa"). Each row is already the
   complete variable domain of one chain (FR1-CDR1-FR2-CDR2-FR3-CDR3-FR4 in
   natural order). It is scored row-by-row with `humanness()` verbatim.

2. Region shape (assembled path): **multiple** amino-acid sequence columns, all
   of which MUST be recognized canonical variable-region columns ("FR1 aa",
   "CDR1 aa", "FR2 aa", "CDR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"). This is the
   CDR3-assembled / partial-domain case where no fully assembled VDJRegion
   column exists. Each row is assembled per `assemble_and_score()`: regions are
   concatenated in canonical order, but ONLY over a single contiguous (gap-free)
   run of present regions — contiguity is judged against the full canonical
   template, so a region that is absent as a column (not just sentinel-valued) is
   a hole and breaks the run — and only when at least 3 framework regions are
   present in that run (the coverage gate). Otherwise the row scores null.

Output Parquet: the key column(s) + any chain-identifier column + a
`humanness_score` column (Float, 0..100, may be null).

`humanness()` uses promb's `compute_peptide_content` over the `human-oas` DB
(fraction of overlapping 9-mers found in human antibody repertoires), rescaled
to [0, 100]. Higher = more human.

We never concatenate across CHAINS (the workflow emits one table per chain, so a
table never mixes chains) and never bridge a NON-ADJACENT region gap (that would
fabricate 9-mer junctions that never occur in nature). Any unexpected ' aa'
column that is neither a key nor a canonical region is a **contract violation**
and we fail fast rather than silently concatenating.

Short sequences (<9 aa, the promb 9-mer window) and any scoring exceptions yield a
null score so the pipeline never fails on a single bad data row. The only fast
failure is the contract violation about the sequence-column set.
"""
import argparse
import sys
from functools import lru_cache

import polars as pl

# Minimum window length used by promb on the human-oas DB. Sequences shorter
# than this cannot produce a single 9-mer and are unscoreable.
_MIN_WINDOW = 9

# The 20 standard amino acids plus X (ambiguous). Upstream emits uppercase
# amino-acid sequences; any other character (underscore, "*", "-", digits)
# marks an NA/sentinel value (e.g. "region_not_covered") that must not be scored.
_AA_ALPHABET = frozenset("ACDEFGHIKLMNPQRSTVWYX")

# Key columns that are carried through to the output unchanged. Anything matching
# is never treated as the sequence to score.
_KEY_COLUMNS = ("clonotypeKey", "scClonotypeKey")

# Canonical variable-region order. Assembly always walks this order, so a
# concatenated run is biologically adjacent (FR1->CDR1->FR2->...->FR4).
_CANONICAL_REGIONS = ("FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4")

# The four framework regions. Only these count toward the coverage gate (>=3).
_FR_REGIONS = frozenset(("FR1", "FR2", "FR3", "FR4"))

# Coverage gate: a row must carry at least this many framework regions (in a
# single contiguous run) to be scoreable; otherwise its score is null.
_MIN_FRAMEWORK_REGIONS = 3


@lru_cache(maxsize=1)
def _get_db():
    """Lazy-load the promb `human-oas` database (cached per process)."""
    from promb import init_db

    return init_db("human-oas")


def humanness(seq: str | None) -> float | None:
    """OASis-style humanness score in [0, 100] (None if unscoreable).

    Computes the fraction of 9-mer windows in `seq` that appear in the
    promb `human-oas` peptide set (curated human antibody repertoires)
    and rescales 0..1 -> 0..100. Higher = more human.

    Returns None for anything that is not a real amino-acid string: too short
    to window, or containing non-amino-acid characters. The latter guards the
    upstream NA/sentinel markers (e.g. "region_not_covered" for uncovered
    regions, stop-codon "*", gap "-"), which arrive as literal column values
    and must NOT be scored as if they were sequences.
    """
    if not isinstance(seq, str) or len(seq) < _MIN_WINDOW:
        return None
    if not set(seq) <= _AA_ALPHABET:
        return None
    try:
        frac = _get_db().compute_peptide_content(seq)
    except Exception:
        return None
    return round(float(frac) * 100.0, 2)


def _is_sequence_column(name: str) -> bool:
    """True if `name` denotes a sequence column to score.

    The robust rule: a column whose normalized name ends with " aa"
    (case-insensitive), and is not an annotation column. Key columns never match.
    """
    if name in _KEY_COLUMNS:
        return False
    nl = name.lower()
    return nl.endswith(" aa") and not nl.endswith("annotations")


def _region_of_column(name: str) -> str | None:
    """Return the canonical region token for a sequence column, else None.

    Strips the trailing " aa" suffix (case-insensitive; the name is assumed
    already whitespace-normalized) and returns the region token (e.g. "FR1") iff
    it is one of `_CANONICAL_REGIONS`. Any other ' aa' column (e.g. "VDJRegion
    aa", "sequence aa") returns None — it is not a per-region column.
    """
    if not _is_sequence_column(name):
        return None
    token = name[:-3].strip()  # drop trailing " aa" (3 chars: space + "aa")
    for region in _CANONICAL_REGIONS:
        if token.lower() == region.lower():
            return region
    return None


def _is_real_aa(value: str | None) -> bool:
    """True if `value` is a real amino-acid subsequence (not a null/sentinel).

    Mirrors the validity test in `humanness()`: a non-empty string drawn from the
    amino-acid alphabet. Sentinels ("region_not_covered", "*", "-", empty) are
    NOT real AA and count as absent for coverage purposes.
    """
    return isinstance(value, str) and len(value) >= 1 and set(value) <= _AA_ALPHABET


def identify_sequence_column(columns: list[str]) -> str:
    """Return the single sequence column to score, or raise on contract violation.

    Backward-compatible helper for the full-domain fast path: exactly one column
    may end in " aa" (case-insensitive, non-annotation). Zero or more than one is
    a contract violation. New callers should prefer `resolve_sequence_columns`,
    which additionally accepts the multi-region shape.
    """
    seq_cols = [c for c in columns if _is_sequence_column(c)]
    if len(seq_cols) == 1:
        return seq_cols[0]
    if len(seq_cols) == 0:
        raise ValueError(
            "Contract violation: input has no sequence column (expected exactly one "
            "column whose name ends in ' aa'). Each row must carry one full variable "
            f"domain to score. Columns present: {columns}"
        )
    raise ValueError(
        "Contract violation: input has multiple sequence columns "
        f"{seq_cols}; expected exactly one full-domain column, or canonical "
        "region columns only. Sequences must not be concatenated across chains; "
        "assemble within one chain upstream before scoring."
    )


def resolve_sequence_columns(columns: list[str]) -> tuple[str, object]:
    """Resolve which sequence column(s) to score and how.

    Returns one of:
    - ("single", col): exactly one sequence column -> score it verbatim (the
      full-domain fast path, unchanged behavior).
    - ("regions", ordered_region_cols): more than one sequence column, ALL of
      which are canonical region columns -> assemble per row in canonical order
      with the contiguity + coverage gate (see `assemble_and_score`). The
      returned list is ordered by `_CANONICAL_REGIONS`.

    Raises a contract violation when there is no sequence column, or when there
    are multiple sequence columns but at least one is not a canonical region
    (a stray ' aa' column, or a region mixed with a full-domain column — both
    would risk an incoherent cross-region/cross-chain concatenation).
    """
    seq_cols = [c for c in columns if _is_sequence_column(c)]
    if len(seq_cols) == 0:
        raise ValueError(
            "Contract violation: input has no sequence column (expected exactly one "
            "full-domain column whose name ends in ' aa', or multiple canonical "
            f"region columns). Columns present: {columns}"
        )
    if len(seq_cols) == 1:
        return ("single", seq_cols[0])

    # Multiple sequence columns: legal only if every one is a canonical region.
    region_of = {c: _region_of_column(c) for c in seq_cols}
    non_region = [c for c, r in region_of.items() if r is None]
    if non_region:
        raise ValueError(
            "Contract violation: input has multiple sequence columns "
            f"{seq_cols}, but {non_region} are not canonical region columns "
            f"(expected only {list(_CANONICAL_REGIONS)} suffixed with ' aa', or a "
            "single full-domain column). Sequences must not be concatenated across "
            "chains or with a full-domain column; assemble within one chain "
            "upstream before scoring."
        )
    ordered = [c for region in _CANONICAL_REGIONS for c in seq_cols if region_of[c] == region]
    return ("regions", ordered)


def assemble_and_score(row_values: dict, region_cols_in_canonical_order: list[str]) -> float | None:
    """Assemble one row's region columns and score the contiguous variable domain.

    `row_values` maps each region column name to its (possibly null/sentinel)
    value for one row; `region_cols_in_canonical_order` is that row's region
    columns already ordered by `_CANONICAL_REGIONS`.

    Presence is evaluated against the FULL canonical template (`_CANONICAL_REGIONS`),
    NOT merely the columns that happen to be in the table: a region counts as
    present iff it has a column AND that column's value is a real amino-acid
    subsequence (`_is_real_aa`). A canonical region that is missing as a column, or
    present only as a sentinel, is therefore a hole. This is what makes the
    contiguity check sound — a table carrying e.g. FR1/FR2/FR4 (FR3 absent) has a
    hole at FR3 and is rejected, rather than silently gluing FR2 onto FR4.

    The single contiguous (gap-free) run of present canonical regions is taken. If
    the present regions are NOT contiguous in canonical order (an internal gap), the
    row is incoherent -> None (we never bridge a gap, which would fabricate a
    junction 9-mer that never occurs in nature).

    The coverage gate then requires at least `_MIN_FRAMEWORK_REGIONS` framework
    regions in that contiguous run; below the floor -> None. Otherwise the run is
    concatenated in canonical order and scored with `humanness()`.
    """
    col_by_region = {_region_of_column(c): c for c in region_cols_in_canonical_order}
    # Index into the full canonical template, so an absent interior region (no
    # column at all) is detected as a hole, not skipped over.
    present_idx = [
        i for i, region in enumerate(_CANONICAL_REGIONS)
        if region in col_by_region and _is_real_aa(row_values.get(col_by_region[region]))
    ]
    if not present_idx:
        return None
    # Contiguity: present regions must form one gap-free run in canonical order.
    if present_idx != list(range(present_idx[0], present_idx[-1] + 1)):
        return None

    run_regions = _CANONICAL_REGIONS[present_idx[0]:present_idx[-1] + 1]
    fr_count = sum(1 for region in run_regions if region in _FR_REGIONS)
    if fr_count < _MIN_FRAMEWORK_REGIONS:
        return None

    assembled = "".join(row_values[col_by_region[region]] for region in run_regions)
    return humanness(assembled)


def main() -> None:
    p = argparse.ArgumentParser(description="Compute promb/OASis humanness score per clonotype.")
    p.add_argument("input_parquet", help="Input Parquet")
    p.add_argument("output_parquet", help="Output Parquet")
    args = p.parse_args()

    try:
        df = pl.read_parquet(args.input_parquet)
    except Exception as e:
        sys.exit(f"Error reading input Parquet '{args.input_parquet}': {e}")

    df.columns = [" ".join(col.strip().split()) for col in df.columns]

    # Contract enforcement: either one full-domain column (fast path) or multiple
    # canonical region columns (assembled path). Fail fast otherwise.
    try:
        mode, selected = resolve_sequence_columns(list(df.columns))
    except ValueError as e:
        sys.exit(str(e))

    if mode == "single":
        seq_col = selected
        score_series = (
            pl.col(seq_col)
            .cast(pl.Utf8)
            .map_elements(humanness, return_dtype=pl.Float64)
            .alias("humanness_score")
        )
        df_scored = df.with_columns(score_series)
        consumed = [seq_col]
    else:
        # Region shape: assemble the contiguous variable domain per row and score
        # it. The struct hands all region values of one row to assemble_and_score,
        # which enforces contiguity and the >=3-framework-region coverage gate.
        region_cols = selected
        score_series = (
            pl.struct([pl.col(c).cast(pl.Utf8) for c in region_cols])
            .map_elements(
                lambda s: assemble_and_score(s, region_cols),
                return_dtype=pl.Float64,
            )
            .alias("humanness_score")
        )
        df_scored = df.with_columns(score_series)
        consumed = region_cols

    # Carry through the key column(s) and any chain-identifier columns, plus the
    # score. Everything that is not a consumed sequence column and not the score is
    # passed through unchanged so the workflow can map scores back to chains.
    passthrough = [c for c in df.columns if c not in consumed]
    df_out = df_scored.select([*passthrough, "humanness_score"])

    try:
        df_out.write_parquet(args.output_parquet)
        print(f"Output table written to {args.output_parquet}")
    except Exception as e:
        print(f"Error writing output Parquet: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
