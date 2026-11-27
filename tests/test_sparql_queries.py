"""CQ1–CQ7：rdflib 解析、空图执行，代数里不得有 SERVICE。"""

from pathlib import Path

import pytest
from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

ROOT = Path(__file__).resolve().parents[1] / "src" / "sparql"
NAMES = (
    "CQ1_cross_jurisdiction_recall.rq",
    "CQ2_dtc_make_context_disambiguation.rq",
    "CQ3_component_to_mot_defect_stats.rq",
    "CQ4_component_to_can_vss.rq",
    "CQ5_dtc_to_obd_pid_vss.rq",
    "CQ6_ev_battery_fault_summary_vss.rq",
    "CQ7_multisource_closed_loop_chain.rq",
)


def _load(name: str, directory: Path = ROOT):
    """语法错误时，异常文本带查询文件名。"""
    path = directory / name
    if not path.is_file():
        raise AssertionError(f"{name}: 缺少查询文件")
    try:
        return prepareQuery(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AssertionError(f"{path.name}: {exc}") from exc


def _has_service(node) -> bool:
    # rdflib 7.6.0 把 SERVICE 子句标成 ServiceGraphPattern。
    if getattr(node, "name", None) == "ServiceGraphPattern":
        return True
    if isinstance(node, dict):
        return any(_has_service(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_has_service(v) for v in node)
    return False


def test_query_set_complete():
    found = sorted(p.name for p in ROOT.glob("CQ*.rq")) if ROOT.is_dir() else []
    assert len(found) == 7
    assert found == sorted(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_query_parses(name):
    _load(name)


@pytest.mark.parametrize("name", NAMES)
def test_query_runs_on_empty_graph(name):
    prepared = _load(name)
    assert not _has_service(prepared.algebra), name
    assert list(Graph().query(prepared)) == []


def test_syntax_error_names_file(tmp_path):
    name = "broken.rq"
    (tmp_path / name).write_text("SELECT WHERE {\n", encoding="utf-8")
    with pytest.raises(AssertionError, match=r"broken\.rq"):
        _load(name, tmp_path)


def test_service_clause_is_visible(tmp_path):
    name = "service.rq"
    (tmp_path / name).write_text(
        "SELECT ?s WHERE { SERVICE <http://example.invalid/sparql> { ?s ?p ?o } }\n",
        encoding="utf-8",
    )
    prepared = prepareQuery((tmp_path / name).read_text(encoding="utf-8"))
    assert _has_service(prepared.algebra)
