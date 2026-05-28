#!/usr/bin/env python3
"""Antibody-mode entry point for humanness scoring.

Pipeline overview:
- Input TSV: one row per clonotype, keyed by `clonotypeKey`. Contains one or more
  amino-acid sequence columns (e.g. "CDR3 aa", "Heavy CDR3 aa", "FR1 aa", ...).
- Output TSV: two columns — `clonotypeKey` and `humanness_score` (Float, 0..100,
  may be null for sequences too short to score).

For each row we collect every column whose name ends with " aa" (case-insensitive)
and is not an annotation column, concatenate the sequences, then compute the
humanness score via promb's `compute_peptide_content` over the `human-oas` DB
(fraction of overlapping 9-mers found in human antibody repertoires), rescaled
to [0, 100]. Higher = more human.

Short sequences (<9 aa, the promb 9-mer window) and any scoring exceptions
yield a null score so the pipeline never fails on a single bad row.
"""
import argparse
import sys
from functools import lru_cache

import polars as pl


# Minimum window length used by promb on the human-oas DB. Sequences shorter
# than this cannot produce a single 9-mer and are unscoreable.
_MIN_WINDOW = 9


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
    """
    if not isinstance(seq, str) or len(seq) < _MIN_WINDOW:
        return None
    try:
        frac = _get_db().compute_peptide_content(seq)
    except Exception:
        return None
    return round(float(frac) * 100.0, 2)


def _identify_sequence_columns(columns: list[str]) -> list[str]:
    """Return columns whose name ends with ' aa' (case-insensitive), excluding
    annotation-only columns. Order is preserved.
    """
    seq_cols: list[str] = []
    for c in columns:
        cl = c.lower()
        if cl.endswith(" aa") and not cl.endswith("annotations"):
            seq_cols.append(c)
    return seq_cols


def main() -> None:
    p = argparse.ArgumentParser(description="Compute promb/OASis humanness score per clonotype.")
    p.add_argument("input_tsv", help="Input TSV")
    p.add_argument("output_tsv", help="Output TSV")
    args = p.parse_args()

    try:
        df = pl.read_csv(args.input_tsv, separator="\t", ignore_errors=True, infer_schema_length=1000)
    except Exception as e:
        sys.exit(f"Error reading input TSV '{args.input_tsv}': {e}")

    df.columns = [" ".join(col.strip().split()) for col in df.columns]

    has_key = "clonotypeKey" in df.columns
    seq_cols = _identify_sequence_columns(list(df.columns))

    if seq_cols:
        # Concatenate all sequence columns into one string per row, then score.
        concat_expr = pl.concat_str(
            [pl.col(c).cast(pl.Utf8).fill_null("") for c in seq_cols],
            separator="",
        )
        score_series = concat_expr.map_elements(humanness, return_dtype=pl.Float64).alias("humanness_score")
        df_scored = df.with_columns(score_series)
    else:
        df_scored = df.with_columns(pl.lit(None).cast(pl.Float64).alias("humanness_score"))

    output_cols: list[str] = []
    if has_key:
        output_cols.append("clonotypeKey")
    output_cols.append("humanness_score")

    # If clonotypeKey isn't present (degenerate input), still write a one-column TSV.
    df_out = df_scored.select([c for c in output_cols if c in df_scored.columns])

    try:
        df_out.write_csv(args.output_tsv, separator="\t", quote_style="never")
        print(f"Output table written to {args.output_tsv}")
    except Exception as e:
        print(f"Error writing output TSV: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
