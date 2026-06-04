#!/usr/bin/env python3
"""Antibody-mode entry point for humanness scoring.

Contract (one chain in, one score out):
- Input Parquet: one row per scoring unit, where each row already represents the
  **complete variable domain of one chain** (FR1-CDR1-FR2-CDR2-FR3-CDR3-FR4 in
  natural order). Each row carries a key column (`clonotypeKey`), optionally a
  chain-identifier column (carried through unchanged), and **exactly one**
  amino-acid sequence column (its name ends with " aa", e.g. "VDJRegion aa").
- Output Parquet: the key column(s) + any chain-identifier column + a
  `humanness_score` column (Float, 0..100, may be null).

We score that single sequence column row-by-row with `humanness()` using promb's
`compute_peptide_content` over the `human-oas` DB (fraction of overlapping 9-mers
found in human antibody repertoires), rescaled to [0, 100]. Higher = more human.

No cross-column concatenation is ever performed: gluing region/chain fragments
fabricates 9-mer windows that never occur in nature and corrupts the score. If the
input carries more than one sequence column that is a **contract violation** and we
fail fast rather than silently concatenating.

Short sequences (<9 aa, the promb 9-mer window) and any scoring exceptions yield a
null score so the pipeline never fails on a single bad data row. The only fast
failure is the contract violation about the sequence-column count.
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


def identify_sequence_column(columns: list[str]) -> str:
    """Return the single sequence column to score, or raise on contract violation.

    Exactly one column may end in " aa" (case-insensitive, non-annotation). Zero or
    more than one is a contract violation: each input row must be exactly one full
    variable domain of one chain, so there is never more than one sequence to score.
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
        f"{seq_cols}; expected exactly one. Each row must already be one full "
        "variable domain of one chain. Sequences must not be concatenated across "
        "regions or chains; assemble the full domain upstream before scoring."
    )


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

    # Contract enforcement: exactly one sequence column. Fail fast otherwise.
    try:
        seq_col = identify_sequence_column(list(df.columns))
    except ValueError as e:
        sys.exit(str(e))

    score_series = (
        pl.col(seq_col)
        .cast(pl.Utf8)
        .map_elements(humanness, return_dtype=pl.Float64)
        .alias("humanness_score")
    )
    df_scored = df.with_columns(score_series)

    # Carry through the key column(s) and any chain-identifier columns, plus the
    # score. Everything that is not the scored sequence column and not the score is
    # passed through unchanged so the workflow can map scores back to chains.
    passthrough = [c for c in df.columns if c != seq_col]
    df_out = df_scored.select([*passthrough, "humanness_score"])

    try:
        df_out.write_parquet(args.output_parquet)
        print(f"Output table written to {args.output_parquet}")
    except Exception as e:
        print(f"Error writing output Parquet: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
