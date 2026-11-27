"""VIN 字面量必须被隐私形状拒绝：嵌入、大小写，以及每一个非抽象类。"""
from __future__ import annotations

from pathlib import Path

import pytest
from pyshacl import validate
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
LABEL = "<http://www.w3.org/2000/01/rdf-schema#label>"

def synthetic_vin() -> str:
    return "JH4KA" + "8260MC000000"
def _class_names() -> list[str]:
    pytest.importorskip("linkml_runtime")
    from linkml_runtime.utils.schemaview import SchemaView
    view = SchemaView(str(ROOT / "src" / "linkml" / "catalog.yaml"))
    return [name for name, cls in view.all_classes().items() if not cls.abstract]

def shapes_graph(schema_gen):
    shapes = Graph()
    shapes.parse(schema_gen.artifacts()["shacl"], format="turtle")
    for path in sorted((ROOT / "src" / "shacl" / "extras").glob("*.ttl")):
        shapes.parse(path, format="turtle")
    return shapes
shapes_graph = pytest.fixture(scope="module")(shapes_graph)

def pytest_generate_tests(metafunc):
    if "class_name" in metafunc.fixturenames:
        metafunc.parametrize("class_name", _class_names())

def outcome(shapes: Graph, turtle: str) -> tuple[bool, str]:
    data = Graph()
    data.parse(data=turtle, format="turtle")
    conforms, _, report = validate(
        data_graph=data, shacl_graph=shapes, inference="none", abort_on_first=False, advanced=True,
    )
    return bool(conforms), report

def complaint(line: str) -> str:
    head = '@prefix core: <https://w3id.org/poc-kb/core/> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n'
    body = '<urn:veh> a core:VehicleModelYear ; core:make "HONDA" ; core:model "CR-V" ; core:modelYear "2018" .\n'
    return head + body + f'<urn:c> a core:Complaint ; core:odino "1" ; core:vehicle <urn:veh> ; {line} .\n'

def flagged(shapes: Graph, turtle: str) -> None:
    conforms, report = outcome(shapes, turtle)
    assert not conforms and "17-character VIN" in report, report

def test_vin_embedded_with_spaces_rejected(shapes_graph: Graph) -> None:
    vin = synthetic_vin()
    flagged(shapes_graph, complaint(f'{LABEL} "编号 {vin} 结束"'))

def test_vin_embedded_with_chinese_punctuation_rejected(shapes_graph: Graph) -> None:
    vin = synthetic_vin()
    flagged(shapes_graph, complaint(f'{LABEL} "编号：{vin}。"'))

def test_vin_lowercase_rejected(shapes_graph: Graph) -> None:
    flagged(shapes_graph, complaint(f'{LABEL} "{synthetic_vin().lower()}"'))

def test_vin_mixed_case_rejected(shapes_graph: Graph) -> None:
    vin = synthetic_vin()
    mixed = vin[:4].lower() + vin[4:8].upper() + vin[8:].lower()
    flagged(shapes_graph, complaint(f'{LABEL} "{mixed}"'))

def test_sixteen_and_eighteen_character_tokens_not_flagged(shapes_graph: Graph) -> None:
    token = synthetic_vin()
    for literal in (token[:-1], token + "A"):
        conforms, report = outcome(shapes_graph, complaint(f'{LABEL} "{literal}"'))
        assert conforms and "17-character VIN" not in report, report

def test_digit_prefixed_eighteen_not_flagged(shapes_graph: Graph) -> None:
    """数字开头的 18 位字母数字串不是识别号。"""
    literal = "1" + synthetic_vin()
    conforms, report = outcome(shapes_graph, complaint(f'{LABEL} "{literal}"'))
    assert conforms and "17-character VIN" not in report, report

def test_token_containing_i_not_flagged(shapes_graph: Graph) -> None:
    """含 I、O、Q 的 17 位串不是识别号。"""
    token = synthetic_vin()
    literal = token[:4] + "I" + token[5:]
    conforms, report = outcome(shapes_graph, complaint(f'{LABEL} "{literal}"'))
    assert conforms and "17-character VIN" not in report, report

def test_typed_and_language_tagged_vin_rejected(shapes_graph: Graph) -> None:
    vin = synthetic_vin()
    flagged(shapes_graph, complaint(f'{LABEL} "{vin}"^^xsd:string'))
    flagged(shapes_graph, complaint(f'{LABEL} "{vin}"@en'))

def test_untyped_node_with_vin_is_not_targeted(shapes_graph: Graph) -> None:
    """无类型 IRI 上的识别号字面量也必须拒绝。原先把「不覆盖」钉成预期，现已反转。"""
    flagged(shapes_graph, f'<urn:bare> {LABEL} "{synthetic_vin()}" .')

def test_untyped_blank_node_with_vin_rejected(shapes_graph: Graph) -> None:
    """挂在有类型投诉上的无类型空白节点，其字面量也必须拒绝。"""
    vin = synthetic_vin()
    turtle = (
        "@prefix core: <https://w3id.org/poc-kb/core/> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        f'<urn:c> a core:Complaint ; core:vehicle [ rdfs:label "{vin}" ] .\n'
    )
    flagged(shapes_graph, turtle)

def test_forbidden_predicate_rejected_on_unlisted_class(shapes_graph: Graph) -> None:
    turtle = '@prefix diag: <https://w3id.org/poc-kb/diag/> .\n<urn:d> a diag:DTC ; diag:narrative "synthetic" .\n'
    _conforms, report = outcome(shapes_graph, turtle)
    assert "forbidden PII/narrative" in report, report

def test_vin_rejected_on_every_class(shapes_graph: Graph, schema_gen, class_name: str) -> None:
    from linkml_runtime.utils.schemaview import SchemaView
    view = SchemaView(str(schema_gen.catalog_path()))
    iri = view.get_uri(view.get_class(class_name), expand=True)
    conforms, report = outcome(shapes_graph, f'<{iri}/node> a <{iri}> ; {LABEL} "{synthetic_vin()}" .')
    assert not conforms and "17-character VIN" in report, class_name
