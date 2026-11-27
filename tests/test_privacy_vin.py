"""VIN 字面量必须被隐私形状拒绝：嵌入、大小写，以及每一个非抽象类。"""
from __future__ import annotations

from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"


def synthetic_vin() -> str:
    """两段拼成 17 位合成标记，仓库里不存放完整串。"""
    return "JH4KA" + "8260MC000000"


def _class_names() -> list[str]:
    pytest.importorskip("linkml_runtime")
    from linkml_runtime.utils.schemaview import SchemaView

    view = SchemaView(str(ROOT / "src" / "linkml" / "catalog.yaml"))
    return [name for name, cls in view.all_classes().items() if not cls.abstract]


@pytest.fixture(scope="module")
def shapes_graph(schema_gen):
    shapes = Graph()
    shapes.parse(schema_gen.artifacts()["shacl"], format="turtle")
    extras = ROOT / "src" / "shacl" / "extras"
    for path in sorted(extras.glob("*.ttl")):
        shapes.parse(path, format="turtle")
    return shapes


def outcome(shapes: Graph, turtle: str) -> tuple[bool, str]:
    data = Graph()
    data.parse(data=turtle, format="turtle")
    conforms, _, report = validate(
        data_graph=data, shacl_graph=shapes, inference="none", abort_on_first=False,
    )
    return bool(conforms), report


def complaint(predicate_line: str) -> str:
    return f"""
@prefix core: <https://w3id.org/poc-kb/core/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
<urn:veh> a core:VehicleModelYear ; core:make "HONDA" ; core:model "CR-V" ; core:modelYear "2018" .
<urn:c> a core:Complaint ; core:odino "1" ; core:vehicle <urn:veh> ; {predicate_line} .
"""


def assert_flagged(shapes: Graph, turtle: str) -> None:
    conforms, report = outcome(shapes, turtle)
    assert not conforms and "17-character VIN" in report, report


def test_vin_embedded_with_spaces_rejected(shapes_graph: Graph) -> None:
    """较长字面量中，两侧有空格的识别号必须命中。"""
    vin = synthetic_vin()
    assert_flagged(shapes_graph, complaint(f'{LABEL} "编号 {vin} 结束"'))


def test_vin_embedded_with_chinese_punctuation_rejected(shapes_graph: Graph) -> None:
    """两侧是中文标点时也必须命中。"""
    vin = synthetic_vin()
    assert_flagged(shapes_graph, complaint(f'{LABEL} "编号：{vin}。"'))


def test_vin_lowercase_rejected(shapes_graph: Graph) -> None:
    """全小写识别号必须命中。"""
    assert_flagged(shapes_graph, complaint(f'{LABEL} "{synthetic_vin().lower()}"'))


def test_vin_mixed_case_rejected(shapes_graph: Graph) -> None:
    """大小写混排识别号必须命中。"""
    vin = synthetic_vin()
    mixed = vin[:4].lower() + vin[4:8].upper() + vin[8:].lower()
    assert_flagged(shapes_graph, complaint(f'{LABEL} "{mixed}"'))


def test_sixteen_and_eighteen_character_tokens_not_flagged(shapes_graph: Graph) -> None:
    """16 位与 18 位字母数字串不是识别号。"""
    token = synthetic_vin()
    for literal in (token[:-1], token + "A"):
        conforms, report = outcome(shapes_graph, complaint(f'{LABEL} "{literal}"'))
        assert conforms and "17-character VIN" not in report, report


def test_typed_and_language_tagged_vin_rejected(shapes_graph: Graph) -> None:
    """类型化字面量与语言标签字面量都按词法形式检查。"""
    vin = synthetic_vin()
    assert_flagged(shapes_graph, complaint(f'{LABEL} "{vin}"^^xsd:string'))
    assert_flagged(shapes_graph, complaint(f'{LABEL} "{vin}"@en'))


def test_untyped_node_with_vin_is_not_targeted(shapes_graph: Graph) -> None:
    """没有 rdf:type 的节点不是任何类的实例，隐私形状不覆盖它。"""
    conforms, report = outcome(shapes_graph, f'<urn:bare> {LABEL} "{synthetic_vin()}" .')
    assert conforms and "17-character VIN" not in report, report


def test_forbidden_predicate_rejected_on_unlisted_class(shapes_graph: Graph) -> None:
    """禁谓词约束不弱于原来的 7 个类，未列入的 DTC 也要拒绝。"""
    turtle = """
@prefix diag: <https://w3id.org/poc-kb/diag/> .
<urn:d> a diag:DTC ; diag:narrative "synthetic" .
"""
    _conforms, report = outcome(shapes_graph, turtle)
    assert "forbidden PII/narrative" in report, report


@pytest.mark.parametrize("class_name", _class_names())
def test_vin_rejected_on_every_class(shapes_graph: Graph, schema_gen, class_name: str) -> None:
    """每个非抽象类的节点只要带上识别号字面量就必须被拒绝。"""
    from linkml_runtime.utils.schemaview import SchemaView

    view = SchemaView(str(schema_gen.catalog_path()))
    iri = view.get_uri(view.get_class(class_name), expand=True)
    turtle = f'<{iri}/node> a <{iri}> ; {LABEL} "{synthetic_vin()}" .'
    conforms, report = outcome(shapes_graph, turtle)
    assert not conforms and "17-character VIN" in report, class_name
