#!/usr/bin/env python3
"""Antibody-mode entry point for humanness scoring.

STUB: replace with real scorer in next step.

Pipeline overview:
- Input TSV: one row per clonotype, keyed by `clonotypeKey`. Contains one or more
  amino-acid sequence columns (e.g. "CDR3 aa", "Heavy CDR3 aa", "FR1 aa", ...).
- Output TSV: two columns — `clonotypeKey` and `humanness_score` (Float, 0..100).

For each row we collect every column whose name ends with " aa" (case-insensitive)
and is not an annotation column, concatenate the sequences, then compute the stub
score as the percentage of characters that are standard amino acids.

The script tolerates extra CLI flags (`-m`, `-o`, `--numbering-schema`,
`--custom-liabilities`, `--use-predefined-liabilities`,
`--disabled-predefined-liabilities`, `--output-regions-found`) so the existing
workflow tengo template can call it without changes. Those flags are ignored
in the stub except `--output-regions-found`, which still writes an empty list
so downstream tengo logic doesn't break.
"""
import argparse
import json
import sys

import polars as pl


# Standard 20 amino acids — used to compute the stub humanness score.
_STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")


def humanness_stub(seq: str | None) -> float:
    """Detereministic stub humanness score in [0, 100].

    Returns the percentage of characters in `seq` that are standard amino
    acids (ACDEFGHIKLMNPQRSTVWY). Empty / non-string inputs map to 0.0.

    # STUB: replace with real scorer in next step.
    """
    if not seq or not isinstance(seq, str):
        return 0.0
    total = len(seq)
    if total == 0:
        return 0.0
    human_like = sum(1 for c in seq.upper() if c in _STANDARD_AA)
    return round(100.0 * human_like / total, 2)


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
    p = argparse.ArgumentParser(description="Compute stub humanness score per clonotype.")
    p.add_argument("input_tsv", help="Input TSV")
    p.add_argument("output_tsv", help="Output TSV")
    # The flags below are kept for CLI compatibility with the existing tengo
    # workflow. They are ignored in the stub.
    p.add_argument("-m", "--label-map", default=None)
    p.add_argument("-o", "--output-label-map", default=None)
    p.add_argument("--output-regions-found", default=None)
    p.add_argument("--numbering-schema", default=None)
    p.add_argument("--custom-liabilities", default=None)
    p.add_argument("--use-predefined-liabilities", default=None)
    p.add_argument("--disabled-predefined-liabilities", default=None)
    # Legacy flag still accepted for compatibility, ignored.
    p.add_argument("--include-liabilities", default=None)
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
        score_series = concat_expr.map_elements(humanness_stub, return_dtype=pl.Float64).alias("humanness_score")
        df_scored = df.with_columns(score_series)
    else:
        df_scored = df.with_columns(pl.lit(0.0).cast(pl.Float64).alias("humanness_score"))

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

    # Compatibility: tengo template subscribes to these output files. Write
    # empty-but-valid JSON so downstream rendering doesn't fail.
    if args.output_label_map:
        try:
            with open(args.output_label_map, "w") as f:
                json.dump({}, f)
        except IOError as e:
            print(f"Error writing label map: {e}", file=sys.stderr)
    if args.output_regions_found:
        try:
            with open(args.output_regions_found, "w") as f:
                json.dump([], f)
        except IOError as e:
            print(f"Error writing regions-found: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
