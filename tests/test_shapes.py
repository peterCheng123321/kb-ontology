from __future__ import annotations

from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_SHACL = REPO_ROOT / "gen" / "shacl" / "poc-kb.shacl.ttl"
EXTRAS_DIR = REPO_ROOT / "src" / "shacl" / "extras"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def load_combined_shapes() -> Graph:
    assert GEN_SHACL.exists(), f"Missing generated SHACL: {GEN_SHACL}; run `make gen` first."
    sg = Graph()
    sg.parse(GEN_SHACL, format="turtle")
    for p in sorted(EXTRAS_DIR.glob("*.ttl")):
        sg.parse(p, format="turtle")
    return sg


@pytest.fixture(scope="module")
def shapes_graph() -> Graph:
    return load_combined_shapes()


@pytest.mark.parametrize(
    "fixture_path",
    sorted((FIXTURES_DIR / "positive").glob("*.ttl")),
    ids=lambda p: p.name,
)
def test_positive_fixtures_conform(shapes_graph: Graph, fixture_path: Path) -> None:
    dg = Graph()
    dg.parse(fixture_path, format="turtle")
    conforms, _, report_text = validate(
        data_graph=dg,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )
    assert conforms, f"Positive fixture {fixture_path.name} failed SHACL:\n{report_text}"


NEGATIVE_EXPECTATIONS = {
    "neg_privacy_vin.ttl": "17-character VIN",
    "neg_privacy_predicate.ttl": "forbidden PII/narrative",
    "neg_mot_unsuppressed_small_cell.ttl": "defectCount >= 5",
    "neg_candidate_score_oob.ttl": "score must be xsd:decimal in [0.0, 1.0]",
    "neg_dtc_def_missing_make.ttl": "makeContext",
}


@pytest.mark.parametrize("filename,expected_substr", sorted(NEGATIVE_EXPECTATIONS.items()))
def test_negative_fixtures_fail_with_expected_reason(
    shapes_graph: Graph, filename: str, expected_substr: str
) -> None:
    fixture_path = FIXTURES_DIR / "negative" / filename
    assert fixture_path.exists(), f"Missing negative fixture: {fixture_path}"
    dg = Graph()
    dg.parse(fixture_path, format="turtle")
    conforms, _, report_text = validate(
        data_graph=dg,
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )
    assert not conforms, f"Negative fixture {filename} unexpectedly conformed!"
    assert expected_substr in report_text, (
        f"Negative fixture {filename} failed, but expected '{expected_substr}' in:\n{report_text}"
    )
