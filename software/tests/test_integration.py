"""Integration tests for the promb-backed humanness scorer.

Run with:
    uv run pytest tests/
"""

import sys
from pathlib import Path

import polars as pl
import pytest

import main as m

DATA_DIR = Path(__file__).parent / "data"
DATA = DATA_DIR / "sequences.tsv"
DATA_SC = DATA_DIR / "sequences_sc.tsv"
DATA_CDR3 = DATA_DIR / "sequences_cdr3_only.tsv"

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
    # Fixtures are kept as human-readable TSV; the script consumes Parquet, so
    # convert the fixture to a Parquet input before invoking the CLI.
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


def run_main_from_df(tmp_path: Path, src: pl.DataFrame) -> pl.DataFrame:
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


# ---------- Unit-level tests on the humanness() function (unchanged) ----------


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


def test_humanness_returns_none_for_na_sentinels():
    """Upstream NA/sentinel markers arrive as literal column values and must
    NOT be scored as sequences (they are long enough to pass the window guard).
    """
    assert m.humanness("region_not_covered") is None  # producer's naRegex marker
    assert m.humanness("EVQLVESGG*GLVQPGG") is None  # stop-codon
    assert m.humanness("EVQLV-ESGGGLVQ") is None  # gap
    assert m.humanness("EVQLVESGG2GLVQPGG") is None  # stray digit


# ---------- Contract: exactly one sequence column ----------


def test_identify_single_sequence_column():
    assert m.identify_sequence_column(["clonotypeKey", "VDJRegion aa"]) == "VDJRegion aa"


def test_identify_ignores_annotation_and_key_columns():
    cols = ["clonotypeKey", "scClonotypeChain", "annotations", "sequence aa"]
    assert m.identify_sequence_column(cols) == "sequence aa"


def test_multiple_sequence_columns_is_contract_violation():
    with pytest.raises(ValueError, match="multiple sequence columns"):
        m.identify_sequence_column(["clonotypeKey", "CDR3 aa", "FR1 aa"])


def test_no_sequence_column_is_contract_violation():
    with pytest.raises(ValueError, match="no sequence column"):
        m.identify_sequence_column(["clonotypeKey", "annotations"])


def test_cli_exits_on_multiple_sequence_columns(tmp_path):
    """The old code silently concatenated; the new code must fail fast."""
    src = pl.DataFrame(
        {
            "clonotypeKey": ["c1"],
            "CDR1 aa": ["GYTFTRY"],
            "CDR3 aa": ["CARYALD"],
            "FR1 aa": [TRASTUZUMAB_VH],
        }
    )
    with pytest.raises(SystemExit) as exc:
        run_main_from_df(tmp_path, src)
    assert "Contract violation" in str(exc.value)


# ---------- End-to-end CLI tests (new contract) ----------


def test_output_has_expected_columns(tmp_path):
    # Behavior-sanity check (passes on old and new code): the actual regression
    # guards against the concatenation bug are the contract-violation tests
    # (test_cli_exits_on_multiple_sequence_columns) and the single-cell
    # per-chain passthrough test.
    df = run_main(tmp_path)
    assert "humanness_score" in df.columns
    assert "clonotypeKey" in df.columns
    # The scored sequence column is consumed, not passed through.
    assert "VDJRegion aa" not in df.columns


def test_score_equals_direct_humanness_no_duplication(tmp_path):
    """Each row's score must equal scoring that one full domain directly.

    Asserts each row's score equals scoring its single full-domain column
    directly (no passthrough/mangling/duplication of the sequence column). This
    is a correctness sanity check, not the anti-concatenation guard: with a
    single ' aa' column the old concat-all-' aa'-columns code is a no-op and
    produces the same score, so this test passes on both old and new code. The
    anti-concatenation guarantee itself is proven by
    test_cli_exits_on_multiple_sequence_columns and
    test_multiple_sequence_columns_is_contract_violation, which DO diverge
    between old and new code.
    """
    df = run_main(tmp_path)
    by_key = dict(zip(df["clonotypeKey"].to_list(), df["humanness_score"].to_list()))
    assert by_key["TRASTUZUMAB_VH"] == m.humanness(TRASTUZUMAB_VH)
    assert by_key["MOUSE_4D5_VH"] == m.humanness(MOUSE_4D5_VH)
    assert by_key["LLAMA_VHH"] == m.humanness(LLAMA_VHH)


def test_human_scores_above_mouse_end_to_end(tmp_path):
    df = run_main(tmp_path)
    by_key = dict(zip(df["clonotypeKey"].to_list(), df["humanness_score"].to_list()))
    assert by_key["TRASTUZUMAB_VH"] > by_key["MOUSE_4D5_VH"] + 5.0


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


# ---------- Single-cell: per-chain rows, chain identity carried through ----------


def test_single_cell_chain_identity_passthrough(tmp_path):
    df = run_main(tmp_path, DATA_SC)
    # Chain-identifier columns are carried through unchanged.
    assert "scClonotypeChain" in df.columns
    assert "scClonotypeChainIndex" in df.columns
    assert "scClonotypeKey" in df.columns
    assert "humanness_score" in df.columns

    rows = df.to_dicts()

    def find(chain, index):
        return next(r for r in rows if r["scClonotypeChain"] == chain and r["scClonotypeChainIndex"] == index)

    heavy_primary = find("A", "primary")
    light_primary = find("B", "primary")
    heavy_secondary = find("A", "secondary")

    # Heavy-primary and Light-primary carry full domains -> real scores.
    assert heavy_primary["humanness_score"] is not None
    assert light_primary["humanness_score"] is not None
    # Heavy and Light are scored independently (different sequences -> not merged).
    assert heavy_primary["humanness_score"] != light_primary["humanness_score"]
    # Heavy-primary equals scoring the full VH directly (no chain merging).
    assert heavy_primary["humanness_score"] == m.humanness(TRASTUZUMAB_VH)
    # Secondary-rank rearrangement is CDR3-only -> null (too short to score).
    assert heavy_secondary["humanness_score"] is None


# ---------- CDR3-only / short sequence -> null ----------


def test_cdr3_only_is_null(tmp_path):
    # Behavior-sanity check (passes on old and new code): a single short ' aa'
    # column is unscoreable either way. The regression guards are the
    # contract-violation and single-cell passthrough tests.
    df = run_main(tmp_path, DATA_CDR3)
    assert df["humanness_score"].to_list() == [None]
