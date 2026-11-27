"""正例夹具对照测试时生成的 SHACL，补充形状目录存在时一并加载。"""
from __future__ import annotations

from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRAS_DIR = REPO_ROOT / "src" / "shacl" / "extras"
POSITIVE_DIR = REPO_ROOT / "tests" / "fixtures" / "positive"


def load_combined_shapes(schema_gen) -> Graph:
    """生成形状，并在 extras 目录存在时按文件名加载其中的 ttl。"""
    shapes = Graph()
    shapes.parse(schema_gen.artifacts()["shacl"], format="turtle")
    if EXTRAS_DIR.is_dir():
        for path in sorted(EXTRAS_DIR.glob("*.ttl")):
            shapes.parse(path, format="turtle")
    return shapes


def parse_data(path: Path, text: str | None = None) -> Graph:
    """解析夹具；失败时错误信息带上文件名。"""
    graph = Graph()
    try:
        if text is None:
            graph.parse(path, format="turtle")
        else:
            graph.parse(data=text, format="turtle")
    except Exception as exc:
        raise AssertionError(f"夹具无法解析：{path.name}：{exc}") from exc
    return graph


@pytest.fixture(scope="module")
def shapes_graph(schema_gen):
    return load_combined_shapes(schema_gen)


def _positive_paths() -> list[Path]:
    if not POSITIVE_DIR.is_dir():
        return []
    return sorted(POSITIVE_DIR.glob("*.ttl"))


def test_positive_fixture_set_not_empty() -> None:
    """正例目录至少有一份 ttl。"""
    assert _positive_paths(), "positive 目录没有 ttl 夹具"


@pytest.mark.parametrize(
    "fixture_path",
    _positive_paths() or [None],
    ids=lambda path: path.name if isinstance(path, Path) else "none",
)
def test_positive_fixtures_conform(shapes_graph: Graph, fixture_path: Path | None) -> None:
    """每份正例图符合生成形状；extras 目录不存在时仍只检查生成形状。"""
    assert fixture_path is not None, "没有正例夹具"
    conforms, _, report = validate(
        data_graph=parse_data(fixture_path),
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )
    assert conforms, f"正例 {fixture_path.name} 未通过 SHACL:\n{report}"


def test_empty_data_graph_conforms(shapes_graph: Graph) -> None:
    """空数据图没有类型节点，应当符合。"""
    conforms, _, report = validate(
        data_graph=Graph(),
        shacl_graph=shapes_graph,
        inference="none",
        abort_on_first=False,
    )
    assert conforms, report


def test_unparseable_fixture_names_file(tmp_path: Path) -> None:
    """无法解析的夹具在失败信息里带上文件名。"""
    bad = tmp_path / "broken.ttl"
    bad.write_text("@prefix x: <not-closed", encoding="utf-8")
    with pytest.raises(AssertionError, match="broken.ttl"):
        parse_data(bad)
