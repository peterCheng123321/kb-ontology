"""测试会话内生成 SHACL 与 OWL，只写临时目录，不依赖 make gen。"""
from pathlib import Path
import pytest
# 对齐 gen-owl 命令行。类默认把 metaclasses 与 type_objects 设为 True。
OWL_FLAGS = dict(metaclasses=False, type_objects=False, ontology_uri_suffix=".owl.ttl",
                 skip_vacuous_min_zero_cardinality_axioms=False, skip_vacuous_local_range_axioms=False,
                 consolidate_cardinality_axioms=False)
def catalog_path():
    return Path(__file__).resolve().parents[1] / "src" / "linkml" / "catalog.yaml"
def _generate(catalog, destination, factory):
    # 失败或结果为空时不写文件。
    if not Path(catalog).is_file():
        raise FileNotFoundError(catalog)
    text = factory()
    if not str(text).strip():
        raise RuntimeError(f"生成为空：{catalog}")
    destination.write_text(text, encoding="utf-8")
    return destination
def generate_shacl(catalog, destination):
    """与 gen-shacl --non-closed 相同。"""
    from linkml.generators.shaclgen import ShaclGenerator
    return _generate(catalog, destination, lambda: ShaclGenerator(str(catalog), closed=False).serialize())
def generate_owl(catalog, destination):
    """与 gen-owl --no-metaclasses --no-type-objects 相同。"""
    from linkml.generators.owlgen import OwlSchemaGenerator
    return _generate(catalog, destination, lambda: OwlSchemaGenerator(str(catalog), **OWL_FLAGS).serialize())
@pytest.fixture(scope="session")
def schema_gen(tmp_path_factory):
    """同一会话只生成一次，再次调用返回同一路径。"""
    directory, cache = tmp_path_factory.mktemp("linkml-gen"), {}
    def artifacts():
        if not cache:
            catalog = catalog_path()
            cache["shacl"] = generate_shacl(catalog, directory / "poc-kb.shacl.ttl")
            cache["owl"] = generate_owl(catalog, directory / "poc-kb.owl.ttl")
        return cache
    artifacts.catalog_path = catalog_path
    artifacts.generate_shacl = generate_shacl
    artifacts.generate_owl = generate_owl
    artifacts.artifacts = artifacts
    return artifacts
