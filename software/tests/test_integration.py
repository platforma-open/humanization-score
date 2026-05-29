"""Integration tests for the promb-backed humanness scorer.

Run with:
    uv run pytest tests/
"""

import sys
from pathlib import Path

import polars as pl

import main as m

DATA = Path(__file__).parent / "data" / "sequences.tsv"

# Public reference sequences (FDA-approved / textbook examples).
TRASTUZUMAB_VH = (
    "EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFT"
    "ISADTSKNTAYLQMNSLRAEDTAVYYCSRWGGDGFYAMDYWGQGTLVTVSS"
)
# Murine 4D5 — parental of trastuzumab, clearly non-human.
MOUSE_4D5_VH = (
    "DVQLQESGPGLVAPSQSLSITCSVSGFSLTNYGVHWVRQSPGKGLEWLGVIWSGGNTDYNTPFTSRLSI"
    "NKDNSKSQVFFKMNSLQADDTAIYYCARNLGPSFYFDYWGQGTTLTVSS"
)
# Camelid VHH — used here only as an "other species" reference (some VHHs
# happen to score human-like because the framework is close to human VH3).
LLAMA_VHH = (
    "QVQLQESGGGLVQAGGSLRLSCAASGRTFSSYAMGWFRQAPGKEREFVAAISWSGGSTYYADSVKGRFT"
    "ISRDNAKNTVYLQMNSLKPEDTAVYYCAAVRSGGAGNVAVDGEYDYWGQGTQVTVSS"
)


def run_main(tmp_path: Path, data_path: Path | None = None) -> pl.DataFrame:
    # Fixtures are kept as human-readable TSV; the script now consumes Parquet,
    # so convert the fixture to a Parquet input before invoking the CLI.
    src = pl.read_csv(data_path or DATA, separator="\t")
    inp = tmp_path / "in.parquet"
    src.write_parquet(inp)

    out = tmp_path / "out.parquet"
    argv = ["main.py", str(inp), str(out)]
    original = sys.argv
    sys.argv = argv
    try:
        m.main()
    finally:
        sys.argv = original
    return pl.read_parquet(out)


# ---------- Unit-level tests on the humanness() function ----------


def test_humanness_in_range_for_known_sequences():
    for seq in (TRASTUZUMAB_VH, MOUSE_4D5_VH, LLAMA_VHH):
        score = m.humanness(seq)
        assert score is not None
        assert 0.0 <= score <= 100.0


def test_humanness_human_higher_than_mouse():
    """Humanized trastuzumab VH must score clearly above murine 4D5 VH."""
    h = m.humanness(TRASTUZUMAB_VH)
    nh = m.humanness(MOUSE_4D5_VH)
    assert h is not None and nh is not None
    assert h > nh + 5.0, f"expected human > mouse + 5, got human={h}, mouse={nh}"


def test_humanness_deterministic():
    """Same input -> same output across invocations."""
    a = m.humanness(TRASTUZUMAB_VH)
    b = m.humanness(TRASTUZUMAB_VH)
    assert a == b


def test_humanness_returns_none_for_short_or_empty():
    assert m.humanness("") is None
    assert m.humanness("ACDE") is None  # <9 aa
    assert m.humanness("ACDEFGHI") is None  # 8 aa, still <9
    assert m.humanness(None) is None  # type: ignore[arg-type]
    # exactly 9 — should produce a (possibly zero) numeric score
    s = m.humanness("ACDEFGHIK")
    assert s is None or (0.0 <= s <= 100.0)


# ---------- End-to-end CLI tests ----------


def test_output_has_humanness_score_column(tmp_path):
    df = run_main(tmp_path)
    assert "humanness_score" in df.columns
    assert "clonotypeKey" in df.columns


def test_humanness_score_is_in_range(tmp_path):
    df = run_main(tmp_path)
    scores = [s for s in df["humanness_score"].to_list() if s is not None]
    assert scores, "expected at least one non-null score"
    assert all(0.0 <= s <= 100.0 for s in scores), f"Expected scores in [0,100], got {scores}"


def test_cli_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    df1 = run_main(a)
    df2 = run_main(b)
    assert df1["humanness_score"].to_list() == df2["humanness_score"].to_list()
