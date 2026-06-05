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
DATA_PARTIAL_3FR = DATA_DIR / "sequences_partial_3fr.tsv"
DATA_2FR = DATA_DIR / "sequences_2fr.tsv"
DATA_NONCONTIGUOUS = DATA_DIR / "sequences_noncontiguous.tsv"

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


def test_mixed_region_and_nonregion_is_contract_violation():
    """A region column mixed with a non-region ' aa' column is still a violation.

    (Multiple canonical region columns alone are now VALID region-mode; the
    violation is reserved for a stray / full-domain ' aa' column mixed in, which
    would risk an incoherent cross-region/cross-chain concatenation.)
    """
    with pytest.raises(ValueError, match="Contract violation"):
        m.resolve_sequence_columns(["clonotypeKey", "CDR3 aa", "sequence aa"])


def test_no_sequence_column_is_contract_violation():
    with pytest.raises(ValueError, match="no sequence column"):
        m.resolve_sequence_columns(["clonotypeKey", "annotations"])


def test_single_sequence_column_resolves_to_single():
    assert m.resolve_sequence_columns(["clonotypeKey", "VDJRegion aa"]) == (
        "single",
        "VDJRegion aa",
    )


def test_multiple_region_columns_resolve_to_regions_mode():
    """Multiple canonical region columns now resolve to region-mode (not a
    violation), ordered by canonical FR1->...->FR4 regardless of input order."""
    mode, cols = m.resolve_sequence_columns(
        ["clonotypeKey", "FR3 aa", "CDR1 aa", "FR1 aa"]
    )
    assert mode == "regions"
    assert cols == ["FR1 aa", "CDR1 aa", "FR3 aa"]


def test_cli_exits_on_mixed_region_and_nonregion(tmp_path):
    """A region column mixed with a non-region ' aa' column must fail fast."""
    src = pl.DataFrame(
        {
            "clonotypeKey": ["c1"],
            "CDR3 aa": ["CARYALD"],
            "sequence aa": [TRASTUZUMAB_VH],
        }
    )
    with pytest.raises(SystemExit) as exc:
        run_main_from_df(tmp_path, src)
    assert "Contract violation" in str(exc.value)


# ---------- Assembly: contiguity + coverage gate ----------

_REGION_COLS = ["FR1 aa", "CDR1 aa", "FR2 aa", "CDR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"]

# Split of TRASTUZUMAB_VH into contiguous region pieces (concatenation == VH).
_T_FR1 = "EVQLVESGGGLVQPGGSLRL"
_T_CDR1 = "SCAASGFNIKDTYIHWVRQA"
_T_FR2 = "PGKGLEWVARIYPTNGYTRY"
_T_CDR2 = "ADSVKGRFTISADTSKNTAYLQMNSLRAED"
_T_FR3 = "TAVYYCSRWGGDGFYAMDYW"
_T_FR4 = "GQGTLVTVSS"


def test_assemble_three_fr_scores_equals_humanness_of_concat():
    """FR2..FR4 present (3 FRs), contiguous CDR1->FR4 run -> scores == humanness(concat)."""
    row = {
        "CDR1 aa": _T_FR1,
        "FR2 aa": _T_CDR1,
        "CDR2 aa": _T_FR2,
        "FR3 aa": _T_CDR2,
        "CDR3 aa": _T_FR3,
        "FR4 aa": _T_FR4,
    }
    cols = ["CDR1 aa", "FR2 aa", "CDR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"]
    score = m.assemble_and_score(row, cols)
    assert score is not None
    assert 0.0 <= score <= 100.0
    assert score == m.humanness(TRASTUZUMAB_VH)


def test_assemble_full_seven_regions_canonical_order():
    row = {
        "FR1 aa": "EVQLVESGGG",
        "CDR1 aa": "LVQPGGSLRL",
        "FR2 aa": "SCAASGFNIK",
        "CDR2 aa": "DTYIHWVRQA",
        "FR3 aa": "PGKGLEWVAR",
        "CDR3 aa": "IYPTNGYTRY",
        "FR4 aa": "ADSVKGRFTI",
    }
    expected = "".join(row[c] for c in _REGION_COLS)
    score = m.assemble_and_score(row, _REGION_COLS)
    assert score == m.humanness(expected)


def test_assemble_two_fr_below_floor_is_none():
    """Only FR3,FR4 framework regions present (2 FRs) -> coverage gate nulls it."""
    row = {
        "CDR2 aa": _T_FR2,
        "FR3 aa": _T_CDR2,
        "CDR3 aa": _T_FR3,
        "FR4 aa": _T_FR4,
    }
    cols = ["CDR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"]
    assert m.assemble_and_score(row, cols) is None


def test_assemble_noncontiguous_is_none():
    """FR1 + FR3 present, interior gap -> incoherent stitch -> None."""
    row = {"FR1 aa": _T_FR1, "FR3 aa": _T_CDR2}
    cols = ["FR1 aa", "FR3 aa"]
    assert m.assemble_and_score(row, cols) is None


def test_assemble_interior_region_absent_as_column_is_none():
    """Regression: an interior canonical region absent AS A COLUMN is a hole.

    Contiguity must be judged against the full canonical template, not merely the
    columns present in the table. These cases each carry >=3 framework regions, so
    the coverage gate does NOT null them — only the contiguity rule does. Before
    the template-aware fix they spuriously scored by gluing non-adjacent regions
    (FR2 onto FR4, FR2 onto FR3), fabricating junction 9-mers (spec §3a).
    """
    # FR3 absent as a column: FR1,FR2,FR4 present (3 FRs) but a hole at FR3.
    row_a = {"FR1 aa": _T_FR1, "FR2 aa": _T_FR2, "FR4 aa": _T_FR4}
    cols_a = ["FR1 aa", "FR2 aa", "FR4 aa"]
    assert m.assemble_and_score(row_a, cols_a) is None

    # CDR2 absent as a column: CDR1,FR2,FR3,CDR3,FR4 present (3 FRs) but hole at CDR2.
    row_b = {
        "CDR1 aa": _T_CDR1,
        "FR2 aa": _T_FR2,
        "FR3 aa": _T_FR3,
        "CDR3 aa": _T_CDR2,
        "FR4 aa": _T_FR4,
    }
    cols_b = ["CDR1 aa", "FR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"]
    assert m.assemble_and_score(row_b, cols_b) is None


def test_assemble_sentinel_region_treated_as_absent():
    """A sentinel region value drops FR coverage below the floor -> None."""
    row = {
        "FR1 aa": _T_FR1,
        "CDR1 aa": _T_CDR1,
        "FR2 aa": "region_not_covered",  # sentinel -> absent -> breaks contiguity
        "CDR2 aa": _T_CDR2,
        "FR3 aa": _T_FR3,
        "FR4 aa": _T_FR4,
    }
    cols = ["FR1 aa", "CDR1 aa", "FR2 aa", "CDR2 aa", "FR3 aa", "FR4 aa"]
    # FR2 absent makes the present set {FR1,CDR1 | CDR2,FR3,FR4} non-contiguous.
    assert m.assemble_and_score(row, cols) is None


# ---------- End-to-end CLI: region-assembled fixtures ----------


def test_cli_partial_3fr_scores_non_null(tmp_path):
    df = run_main(tmp_path, DATA_PARTIAL_3FR)
    by_key = dict(zip(df["clonotypeKey"].to_list(), df["humanness_score"].to_list()))
    score = by_key["clone_partial"]
    assert score is not None
    assert 0.0 <= score <= 100.0
    # The six contiguous region pieces concatenate to the full trastuzumab VH.
    assert score == m.humanness(TRASTUZUMAB_VH)
    # The consumed region columns must not be passed through.
    for c in ("CDR1 aa", "FR2 aa", "CDR2 aa", "FR3 aa", "CDR3 aa", "FR4 aa"):
        assert c not in df.columns


def test_cli_2fr_is_null(tmp_path):
    df = run_main(tmp_path, DATA_2FR)
    assert df["humanness_score"].to_list() == [None]


def test_cli_noncontiguous_is_null(tmp_path):
    df = run_main(tmp_path, DATA_NONCONTIGUOUS)
    assert df["humanness_score"].to_list() == [None]


# ---------- End-to-end CLI tests (new contract) ----------


def test_output_has_expected_columns(tmp_path):
    # Behavior-sanity check (passes on old and new code): the actual regression
    # guards against the concatenation bug are the contract-violation tests
    # (test_cli_exits_on_mixed_region_and_nonregion) and the single-cell
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
    test_cli_exits_on_mixed_region_and_nonregion and
    test_mixed_region_and_nonregion_is_contract_violation, which DO diverge
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
