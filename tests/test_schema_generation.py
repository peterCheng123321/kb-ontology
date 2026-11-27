"""目录模式在测试进程内生成 SHACL / OWL。EXPECTED_MODULES 供后续模块追加。"""
import pytest
EXPECTED_MODULES = ("metadata", "core", "recall", "diagnostics", "inspection")
INFRA_IMPORTS = ("prefixes", "linkml:types")
def _require():
    pytest.importorskip("linkml"); pytest.importorskip("linkml_runtime"); pytest.importorskip("rdflib")
def _catalog(schema_gen):
    _require()
    catalog = schema_gen.catalog_path()
    assert catalog.is_file()
    return catalog
def _no_empty_file(schema_gen, catalog, destination, match=None):
    _require()
    kwargs = {} if match is None else {"match": match}
    for generate in (schema_gen.generate_shacl, schema_gen.generate_owl):
        with pytest.raises(FileNotFoundError, **kwargs):
            generate(catalog, destination)
        assert not destination.exists()
def test_shacl_and_owl_generate_offline(tmp_path, schema_gen):
    """离线生成可解析产物；会话内路径稳定，另行生成字节相同。"""
    from rdflib import Graph
    catalog = _catalog(schema_gen)
    first = schema_gen.artifacts()
    assert schema_gen.artifacts() == first
    fresh = tmp_path / "shacl.ttl"
    schema_gen.generate_shacl(catalog, fresh)
    assert fresh.read_bytes() == first["shacl"].read_bytes()
    assert all(len(Graph().parse(path, format="turtle")) > 0 for path in first.values())
def test_every_class_has_shape_and_owl_class(schema_gen):
    """非抽象、非 mixin 类均有非封闭 sh:NodeShape 与 owl:Class。"""
    from rdflib import RDF, OWL, Graph, Literal, Namespace, URIRef
    from linkml_runtime.utils.schemaview import SchemaView
    catalog = _catalog(schema_gen)
    arts = schema_gen.artifacts()
    view = SchemaView(str(catalog))
    shapes, owl = Graph(), Graph()
    shapes.parse(arts["shacl"], format="turtle")
    owl.parse(arts["owl"], format="turtle")
    ns, seen = Namespace("http://www.w3.org/ns/shacl#"), []
    for name, cls in view.all_classes().items():
        if cls.abstract or cls.mixin:
            continue
        iri = URIRef(view.get_uri(cls, expand=True))
        hits = [n for n in shapes.subjects(ns.targetClass, iri) if (n, RDF.type, ns.NodeShape) in shapes]
        assert hits and (hits[0], ns.closed, Literal(False)) in shapes and (iri, RDF.type, OWL.Class) in owl, name
        seen.append(name)
    terms = set(owl.subjects()) | set(owl.predicates()) | set(owl.objects())
    blocked = {URIRef("https://w3id.org/linkml/ClassDefinition"), URIRef("https://w3id.org/linkml/String")}
    assert seen and not (blocked & terms)
def test_catalog_imports_expected_modules(schema_gen):
    """直接导入恰好是 prefixes、linkml:types 加上 EXPECTED_MODULES。"""
    from linkml_runtime.utils.schemaview import SchemaView
    catalog = _catalog(schema_gen)
    assert list(SchemaView(str(catalog)).schema.imports) == [*INFRA_IMPORTS, *EXPECTED_MODULES]
def test_missing_catalog_raises(tmp_path, schema_gen):
    """目录不存在时抛错，不写空文件。"""
    _no_empty_file(schema_gen, tmp_path / "missing.yaml", tmp_path / "out.ttl")
def test_broken_import_does_not_write_empty_file(tmp_path, schema_gen):
    """缺失导入抛错，不写空文件。"""
    schema = tmp_path / "catalog.yaml"
    schema.write_text("id: https://example.org/broken\nname: broken\nimports:\n  - missing_module\n", encoding="utf-8")
    _no_empty_file(schema_gen, schema, tmp_path / "out.ttl", "missing_module")
