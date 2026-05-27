#!/usr/bin/env python3
"""Peptide-mode entry point for humanness scoring.

Input TSV: one peptide per row keyed by `variantKey`, with column `sequence aa`.
Output TSV: `variantKey`, `peptide_aa`, `humanness_score` (Float, 0..100; may
be null for sequences shorter than the promb 9-mer window).
"""
import argparse

import polars as pl

from main import humanness  # share the scorer across modalities


def run(input_tsv: str, output_tsv: str) -> None:
    df = pl.read_csv(input_tsv, separator="\t")

    if "variantKey" not in df.columns or "sequence aa" not in df.columns:
        raise ValueError(
            f"peptide_main: expected columns 'variantKey' and 'sequence aa'; got {df.columns}"
        )

    scores = [humanness(s if isinstance(s, str) else "") for s in df["sequence aa"].to_list()]

    out = df.select(
        "variantKey",
        pl.col("sequence aa").alias("peptide_aa"),
    ).with_columns(pl.Series("humanness_score", scores, dtype=pl.Float64))
    out.write_csv(output_tsv, separator="\t")


def main() -> None:
    parser = argparse.ArgumentParser(description="Peptide humanness scorer (promb / human-oas).")
    parser.add_argument("--input_tsv", required=True)
    parser.add_argument("--output_tsv", required=True)
    args = parser.parse_args()

    run(input_tsv=args.input_tsv, output_tsv=args.output_tsv)


if __name__ == "__main__":
    main()
