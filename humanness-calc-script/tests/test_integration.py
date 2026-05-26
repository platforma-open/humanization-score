"""Integration tests for the stub humanness scorer.

Run with:
    uv run pytest tests/
"""

import sys
from pathlib import Path

import polars as pl

import main as m

DATA = Path(__file__).parent / "data" / "sequences.tsv"


def run_main(tmp_path: Path, data_path: Path | None = None) -> pl.DataFrame:
    out = tmp_path / "out.tsv"
    argv = ["main.py", str(data_path or DATA), str(out)]
    original = sys.argv
    sys.argv = argv
    try:
        m.main()
    finally:
        sys.argv = original
    return pl.read_csv(out, separator="\t")


def test_output_has_humanness_score_column(tmp_path):
    df = run_main(tmp_path)
    assert "humanness_score" in df.columns
    assert "clonotypeKey" in df.columns


def test_humanness_score_is_in_range(tmp_path):
    df = run_main(tmp_path)
    scores = df["humanness_score"].to_list()
    assert all(0.0 <= s <= 100.0 for s in scores), f"Expected scores in [0,100], got {scores}"


def test_clean_sequence_scores_100(tmp_path):
    """A row composed entirely of standard amino acids should score 100."""
    df = run_main(tmp_path)
    r = df.filter(pl.col("clonotypeKey") == "clone_clean").to_dicts()[0]
    assert r["humanness_score"] == 100.0


def test_stop_codon_lowers_score(tmp_path):
    """A row with a non-AA character ('*') must score strictly below 100."""
    df = run_main(tmp_path)
    r = df.filter(pl.col("clonotypeKey") == "clone_stop").to_dicts()[0]
    assert r["humanness_score"] < 100.0


def test_humanness_score_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    df1 = run_main(a)
    df2 = run_main(b)
    assert df1["humanness_score"].to_list() == df2["humanness_score"].to_list()


def test_stub_function_directly():
    """Unit-level: humanness_stub() matches the documented formula."""
    assert m.humanness_stub("ACDE") == 100.0
    assert m.humanness_stub("") == 0.0
    assert m.humanness_stub(None) == 0.0
    # 3/4 valid characters → 75.0
    assert m.humanness_stub("ACD*") == 75.0
