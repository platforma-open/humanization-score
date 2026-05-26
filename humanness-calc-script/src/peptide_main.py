#!/usr/bin/env python3
"""Peptide-mode entry point for humanness scoring.

STUB: replace with real scorer in next step.

Input TSV: one peptide per row keyed by `variantKey`, with column `sequence aa`.
Output TSV: `variantKey`, `peptide_aa`, `humanness_score` (Float, 0..100).
"""
import argparse
import json

import polars as pl

from main import humanness_stub  # share the stub formula across modalities


def run(input_tsv: str, output_tsv: str) -> None:
    df = pl.read_csv(input_tsv, separator="\t")

    if "variantKey" not in df.columns or "sequence aa" not in df.columns:
        raise ValueError(
            f"peptide_main: expected columns 'variantKey' and 'sequence aa'; got {df.columns}"
        )

    scores = [humanness_stub(s if isinstance(s, str) else "") for s in df["sequence aa"].to_list()]

    out = df.select(
        "variantKey",
        pl.col("sequence aa").alias("peptide_aa"),
    ).with_columns(pl.Series("humanness_score", scores, dtype=pl.Float64))
    out.write_csv(output_tsv, separator="\t")


def _load_json_list(path: str | None) -> list:
    if not path:
        return []
    with open(path) as f:
        value = json.load(f)
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a JSON list, got {type(value).__name__}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Peptide humanness scorer (stub).")
    parser.add_argument("--input_tsv", required=True)
    parser.add_argument("--output_tsv", required=True)
    # Compatibility flags — ignored by the stub.
    parser.add_argument("--use_predefined_liabilities", action="store_true")
    parser.add_argument("--disabled_predefined_liabilities", default=None)
    parser.add_argument("--custom_liabilities", default=None)
    args = parser.parse_args()

    # Load + ignore (validates JSON exists so workflow plumbing stays happy).
    _load_json_list(args.disabled_predefined_liabilities)
    _load_json_list(args.custom_liabilities)

    run(input_tsv=args.input_tsv, output_tsv=args.output_tsv)


if __name__ == "__main__":
    main()
